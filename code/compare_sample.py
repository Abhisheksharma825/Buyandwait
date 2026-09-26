import os
import sys
import pandas as pd


def main():

    # =========================================================
    # PROJECT ROOT
    # =========================================================

    root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    code_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    if code_dir not in sys.path:
        sys.path.insert(0, code_dir)

    # =========================================================
    # IMPORT PROJECT MODULES
    # =========================================================

    from data_loader import load_data
    from decision_engine import make_decision

    # =========================================================
    # HEADER
    # =========================================================

    print("=" * 70)
    print("SAMPLE REQUEST BENCHMARK")
    print("=" * 70)

    # =========================================================
    # LOAD DATA
    # =========================================================

    data = load_data()

    sample = data["sample_requests"].copy()

    print(
        f"\nSample requests: {len(sample)}"
    )

    # =========================================================
    # GENERATE DECISIONS
    # =========================================================

    generated_rows = []

    for _, request in sample.iterrows():

        request_id = request["request_id"]

        try:

            # -------------------------------------------------
            # Find user's profile
            # -------------------------------------------------

            profiles = data["profiles"]

            if "user_id" in profiles.columns:

                profile_matches = profiles[
                    profiles["user_id"]
                    ==
                    request["user_id"]
                ]

            else:

                profile_matches = profiles

            if profile_matches.empty:

                raise ValueError(
                    f"No profile found for "
                    f"user_id={request['user_id']}"
                )

            profile = profile_matches.iloc[0]

            # -------------------------------------------------
            # Events for this user
            # -------------------------------------------------

            events = data["events"]

            if "user_id" in events.columns:

                user_events = events[
                    events["user_id"]
                    ==
                    request["user_id"]
                ].copy()

            else:

                user_events = events.copy()

            # -------------------------------------------------
            # Payment options for this request
            # -------------------------------------------------

            payment_options = data["payment_options"]

            if "request_id" in payment_options.columns:

                request_options = payment_options[
                    payment_options["request_id"]
                    ==
                    request_id
                ].copy()

            else:

                request_options = payment_options.copy()

            # -------------------------------------------------
            # Messages
            # -------------------------------------------------

            messages = data.get(
                "messages",
                None
            )

            if messages is not None:

                if (
                    "user_id" in messages.columns
                ):

                    user_messages = messages[
                        messages["user_id"]
                        ==
                        request["user_id"]
                    ].copy()

                else:

                    user_messages = messages.copy()

            else:

                user_messages = None

            # -------------------------------------------------
            # Images
            # -------------------------------------------------

            images = data.get(
                "images",
                None
            )

            if images is not None:

                # Keep request/user related images
                # if the columns exist.

                user_images = images.copy()

                if (
                    "user_id" in images.columns
                ):

                    user_images = images[
                        images["user_id"]
                        ==
                        request["user_id"]
                    ].copy()

            else:

                user_images = None

            # -------------------------------------------------
            # CALL DECISION ENGINE
            # -------------------------------------------------

            result = make_decision(
                request,
                profile,
                user_events,
                request_options,
                user_messages,
                user_images
            )

            # -------------------------------------------------
            # Normalize result
            # -------------------------------------------------

            if isinstance(result, dict):

                row = result.copy()

            else:

                row = dict(result)

            row["request_id"] = request_id

            generated_rows.append(row)

        except Exception as e:

            print(
                f"ERROR - {request_id}: "
                f"{type(e).__name__}: {e}"
            )

            generated_rows.append({

                "request_id": request_id,

                "amount_safe_to_pay": 0,

                "affordability_status":
                    "not_affordable",

                "recommended_payment_method":
                    "not_recommended",

                "payment_plan":
                    "none",

                "earliest_date_for_full_payment":
                    "",

                "spending_changes_needed":
                    "none",

                "decision_explanation":
                    f"Engine error: {e}"
            })

    generated = pd.DataFrame(
        generated_rows
    )

    print(
        f"\nGenerated sample decisions: "
        f"{len(generated)}"
    )

    # =========================================================
    # DISPLAY COLUMNS
    # =========================================================

    print("\nSample columns:")
    print(
        list(sample.columns)
    )

    print("\nGenerated columns:")
    print(
        list(generated.columns)
    )

    # =========================================================
    # MERGE
    # =========================================================

    merged = generated.merge(
        sample,
        on="request_id",
        how="inner",
        suffixes=(
            "_generated",
            "_expected"
        )
    )

    print(
        f"\nCommon sample requests: "
        f"{len(merged)}"
    )

    if merged.empty:

        print(
            "\nERROR: Could not match "
            "sample requests."
        )

        return

    # =========================================================
    # FIELDS
    # =========================================================

    fields = [

        "amount_safe_to_pay",

        "affordability_status",

        "recommended_payment_method",

        "payment_plan",

        "earliest_date_for_full_payment",

        "spending_changes_needed"
    ]

    # =========================================================
    # FIELD ACCURACY
    # =========================================================

    print("\n" + "-" * 70)
    print("FIELD ACCURACY")
    print("-" * 70)

    for field in fields:

        gen_col = (
            field
            +
            "_generated"
        )

        exp_col = (
            field
            +
            "_expected"
        )

        if gen_col not in merged.columns:

            print(
                f"{field}: "
                "generated column unavailable"
            )

            continue

        if exp_col not in merged.columns:

            print(
                f"{field}: "
                "expected column unavailable"
            )

            continue

        # -----------------------------------------------------
        # Numeric field
        # -----------------------------------------------------

        if field == "amount_safe_to_pay":

            generated_values = pd.to_numeric(
                merged[gen_col],
                errors="coerce"
            )

            expected_values = pd.to_numeric(
                merged[exp_col],
                errors="coerce"
            )

            matches = (
                (
                    generated_values
                    -
                    expected_values
                ).abs()
                <= 0.01
            )

        # -----------------------------------------------------
        # Text fields
        # -----------------------------------------------------

        else:

            generated_values = (
                merged[gen_col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            expected_values = (
                merged[exp_col]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            matches = (
                generated_values
                ==
                expected_values
            )

        count = int(
            matches.sum()
        )

        total = len(matches)

        accuracy = (
            count
            /
            total
            *
            100
            if total
            else 0
        )

        print(
            f"{field}: "
            f"{count}/{total} "
            f"({accuracy:.2f}%)"
        )

    # =========================================================
    # REQUEST LEVEL COMPARISON
    # =========================================================

    print("\n" + "-" * 70)
    print("REQUEST-LEVEL COMPARISON")
    print("-" * 70)

    mismatch_count = 0

    for _, row in merged.iterrows():

        request_id = row[
            "request_id"
        ]

        mismatches = []

        for field in fields:

            gen_col = (
                field
                +
                "_generated"
            )

            exp_col = (
                field
                +
                "_expected"
            )

            if (
                gen_col not in merged.columns
                or
                exp_col not in merged.columns
            ):

                continue

            # -------------------------------------------------
            # Numeric comparison
            # -------------------------------------------------

            if field == "amount_safe_to_pay":

                try:

                    gen_value = float(
                        row[gen_col]
                    )

                    exp_value = float(
                        row[exp_col]
                    )

                    match = (
                        abs(
                            gen_value
                            -
                            exp_value
                        )
                        <= 0.01
                    )

                except (
                    ValueError,
                    TypeError
                ):

                    match = False

            # -------------------------------------------------
            # Text comparison
            # -------------------------------------------------

            else:

                gen_value = (
                    ""
                    if pd.isna(
                        row[gen_col]
                    )
                    else str(
                        row[gen_col]
                    ).strip()
                )

                exp_value = (
                    ""
                    if pd.isna(
                        row[exp_col]
                    )
                    else str(
                        row[exp_col]
                    ).strip()
                )

                match = (
                    gen_value
                    ==
                    exp_value
                )

            if not match:

                mismatches.append(
                    field
                )

        # -----------------------------------------------------
        # Print result
        # -----------------------------------------------------

        if mismatches:

            mismatch_count += 1

            print(
                f"\n❌ {request_id}"
            )

            print(
                "   Mismatch:",
                ", ".join(
                    mismatches
                )
            )

            for field in mismatches:

                gen_col = (
                    field
                    +
                    "_generated"
                )

                exp_col = (
                    field
                    +
                    "_expected"
                )

                print(
                    f"   {field}:"
                )

                print(
                    f"      Generated: "
                    f"{row[gen_col]}"
                )

                print(
                    f"      Expected:  "
                    f"{row[exp_col]}"
                )

        else:

            print(
                f"✅ {request_id}"
            )

    # =========================================================
    # STATUS COMPARISON
    # =========================================================

    print("\n" + "-" * 70)
    print("STATUS COMPARISON")
    print("-" * 70)

    if (
        "affordability_status_generated"
        in merged.columns
        and
        "affordability_status_expected"
        in merged.columns
    ):

        status_comparison = pd.crosstab(
            merged[
                "affordability_status_generated"
            ],
            merged[
                "affordability_status_expected"
            ],
            rownames=["Generated"],
            colnames=["Expected"]
        )

        print(
            status_comparison
        )

    # =========================================================
    # PAYMENT METHOD COMPARISON
    # =========================================================

    print("\n" + "-" * 70)
    print("PAYMENT METHOD COMPARISON")
    print("-" * 70)

    if (
        "recommended_payment_method_generated"
        in merged.columns
        and
        "recommended_payment_method_expected"
        in merged.columns
    ):

        method_comparison = pd.crosstab(
            merged[
                "recommended_payment_method_generated"
            ],
            merged[
                "recommended_payment_method_expected"
            ],
            rownames=["Generated"],
            colnames=["Expected"]
        )

        print(
            method_comparison
        )

    # =========================================================
    # SAVE DETAILED COMPARISON
    # =========================================================

    comparison_path = os.path.join(
        root,
        "sample_comparison.csv"
    )

    merged.to_csv(
        comparison_path,
        index=False
    )

    # =========================================================
    # SUMMARY
    # =========================================================

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)

    print(
        f"Requests tested: "
        f"{len(merged)}"
    )

    print(
        f"Requests matched: "
        f"{len(merged) - mismatch_count}"
    )

    print(
        f"Requests with mismatch: "
        f"{mismatch_count}"
    )

    print(
        "\nDetailed comparison saved to:"
    )

    print(
        comparison_path
    )

    print("\n" + "=" * 70)
    print("COMPARISON COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()