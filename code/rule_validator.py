import pandas as pd
import re
import os


ALLOWED_STATUS = {
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable"
}

ALLOWED_METHODS = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended"
}

DATE_AMOUNT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}:\d+(\.\d{1,2})?$"
)


def parse_payment_plan(plan):

    if pd.isna(plan):
        return []

    plan = str(plan).strip()

    if plan.lower() == "none" or plan == "":
        return []

    payments = []

    for item in plan.split("|"):

        parts = item.split(":")

        if len(parts) != 2:
            return None

        try:
            date_value = pd.to_datetime(
                parts[0],
                errors="raise"
            ).date()

            amount = float(parts[1])

        except Exception:
            return None

        payments.append(
            (date_value, amount)
        )

    return payments


def main():

    root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    output_path = os.path.join(
        root,
        "output.csv"
    )

    requests_path = os.path.join(
        root,
        "dataset",
        "requests.csv"
    )

    profiles_path = os.path.join(
        root,
        "dataset",
        "financial_profiles.csv"
    )

    output = pd.read_csv(output_path)
    requests = pd.read_csv(requests_path)
    profiles = pd.read_csv(profiles_path)

    print("=" * 70)
    print("BUY OR WAIT - RULE VALIDATION")
    print("=" * 70)

    errors = []

    # --------------------------------------------------
    # 1. Row count
    # --------------------------------------------------

    if len(output) != len(requests):

        errors.append(
            f"Row count mismatch: "
            f"{len(output)} vs {len(requests)}"
        )

    # --------------------------------------------------
    # 2. Request IDs
    # --------------------------------------------------

    if output["request_id"].duplicated().any():

        errors.append(
            "Duplicate request_id found."
        )

    missing_ids = (
        set(requests["request_id"])
        -
        set(output["request_id"])
    )

    if missing_ids:

        errors.append(
            f"Missing request IDs: "
            f"{sorted(missing_ids)}"
        )

    # --------------------------------------------------
    # 3. Allowed status
    # --------------------------------------------------

    for _, row in output.iterrows():

        status = str(
            row["affordability_status"]
        )

        if status not in ALLOWED_STATUS:

            errors.append(
                f"{row['request_id']}: "
                f"invalid status '{status}'"
            )

    # --------------------------------------------------
    # 4. Allowed methods
    # --------------------------------------------------

    for _, row in output.iterrows():

        method = str(
            row["recommended_payment_method"]
        )

        if method not in ALLOWED_METHODS:

            errors.append(
                f"{row['request_id']}: "
                f"invalid payment method '{method}'"
            )

    # --------------------------------------------------
    # 5. Safe amount
    # --------------------------------------------------

    requests_indexed = requests.set_index(
        "request_id"
    )

    for _, row in output.iterrows():

        request_id = row["request_id"]

        try:
            safe_amount = float(
                row["amount_safe_to_pay"]
            )

            requested_amount = float(
                requests_indexed.loc[
                    request_id,
                    "requested_amount"
                ]
            )

            if safe_amount < -0.01:

                errors.append(
                    f"{request_id}: "
                    f"negative safe amount"
                )

            if safe_amount > requested_amount + 0.01:

                errors.append(
                    f"{request_id}: "
                    f"safe amount exceeds requested amount"
                )

        except Exception as e:

            errors.append(
                f"{request_id}: "
                f"invalid safe amount"
            )

    # --------------------------------------------------
    # 6. Payment plan syntax
    # --------------------------------------------------

    for _, row in output.iterrows():

        request_id = row["request_id"]

        plan = row["payment_plan"]

        parsed = parse_payment_plan(
            plan
        )

        if parsed is None:

            errors.append(
                f"{request_id}: "
                f"invalid payment_plan format"
            )

    # --------------------------------------------------
    # 7. Partial-payment rule
    # --------------------------------------------------

    for _, row in output.iterrows():

        if (
            row["recommended_payment_method"]
            != "partial_payment"
        ):
            continue

        request_id = row["request_id"]

        request = requests_indexed.loc[
            request_id
        ]

        allows_partial = str(
            request["allows_partial_payment"]
        ).lower()

        if allows_partial not in {
            "true",
            "1",
            "yes"
        }:

            errors.append(
                f"{request_id}: "
                f"partial payment used when "
                f"request does not allow it"
            )

        payments = parse_payment_plan(
            row["payment_plan"]
        )

        if payments is None:

            continue

        if len(payments) != 2:

            errors.append(
                f"{request_id}: "
                f"partial payment must contain "
                f"exactly two payments"
            )

        else:

            requested_amount = float(
                request["requested_amount"]
            )

            total = sum(
                amount
                for _, amount in payments
            )

            if abs(
                total - requested_amount
            ) > 0.01:

                errors.append(
                    f"{request_id}: "
                    f"partial payments do not sum "
                    f"to requested amount"
                )

    # --------------------------------------------------
    # 8. Spending change limit
    # --------------------------------------------------

    for _, row in output.iterrows():

        changes = str(
            row["spending_changes_needed"]
        ).strip()

        if changes.lower() == "none":
            continue

        count = len(
            changes.split("|")
        )

        if count > 3:

            errors.append(
                f"{row['request_id']}: "
                f"more than 3 spending changes"
            )

    # --------------------------------------------------
    # 9. Date validation
    # --------------------------------------------------

    for _, row in output.iterrows():

        value = str(
            row["earliest_date_for_full_payment"]
        ).strip()

        if value == "" or value.lower() == "nan":
            continue

        try:

            pd.to_datetime(
                value,
                errors="raise"
            )

        except Exception:

            errors.append(
                f"{row['request_id']}: "
                f"invalid earliest full-payment date"
            )

    # --------------------------------------------------
    # 10. Status/method consistency
    # --------------------------------------------------

    for _, row in output.iterrows():

        request_id = row["request_id"]

        status = row[
            "affordability_status"
        ]

        method = row[
            "recommended_payment_method"
        ]

        safe_amount = float(
            row["amount_safe_to_pay"]
        )

        requested_amount = float(
            requests_indexed.loc[
                request_id,
                "requested_amount"
            ]
        )

        if (
            status == "affordable_now"
            and safe_amount + 0.01 < requested_amount
        ):

            errors.append(
                f"{request_id}: "
                f"affordable_now but safe amount "
                f"is less than requested amount"
            )

        if (
            method == "partial_payment"
            and not (
                0 < safe_amount < requested_amount
            )
        ):

            errors.append(
                f"{request_id}: "
                f"invalid safe amount for partial payment"
            )

    # --------------------------------------------------
    # RESULT
    # --------------------------------------------------

    print(
        f"\nRows checked: {len(output)}"
    )

    print(
        f"Rules violated: {len(errors)}"
    )

    if not errors:

        print("\n✅ ALL BASIC RULES PASSED")

    else:

        print("\n❌ RULE VIOLATIONS:\n")

        for error in errors[:100]:

            print(
                " -",
                error
            )

        if len(errors) > 100:

            print(
                f"\n... and "
                f"{len(errors) - 100} more."
            )

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()