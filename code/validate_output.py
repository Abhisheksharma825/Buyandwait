import pandas as pd
import os


EXPECTED_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation"
]

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

    output = pd.read_csv(
        output_path
    )

    requests = pd.read_csv(
        requests_path
    )

    print("=" * 60)
    print("OUTPUT VALIDATION")
    print("=" * 60)

    # ----------------------------------------
    # Row count
    # ----------------------------------------

    print(
        f"\nOutput rows: {len(output)}"
    )

    print(
        f"Request rows: {len(requests)}"
    )

    print(
        "Row count:",
        "PASS" if len(output) == len(requests)
        else "FAIL"
    )

    # ----------------------------------------
    # Columns
    # ----------------------------------------

    print("\nColumns:")

    print(
        list(output.columns)
    )

    print(
        "Column schema:",
        "PASS"
        if list(output.columns) == EXPECTED_COLUMNS
        else "FAIL"
    )

    # ----------------------------------------
    # Duplicate request IDs
    # ----------------------------------------

    duplicates = output[
        output["request_id"].duplicated()
    ]

    print(
        "\nDuplicate request IDs:",
        len(duplicates)
    )

    print(
        "Duplicates:",
        "PASS"
        if len(duplicates) == 0
        else "FAIL"
    )

    # ----------------------------------------
    # Missing request IDs
    # ----------------------------------------

    missing = set(
        requests["request_id"]
    ) - set(
        output["request_id"]
    )

    extra = set(
        output["request_id"]
    ) - set(
        requests["request_id"]
    )

    print(
        "\nMissing requests:",
        len(missing)
    )

    print(
        "Extra requests:",
        len(extra)
    )

    # ----------------------------------------
    # Status validation
    # ----------------------------------------

    invalid_status = output[
        ~output["affordability_status"].isin(
            ALLOWED_STATUS
        )
    ]

    print(
        "\nInvalid statuses:",
        len(invalid_status)
    )

    print(
        "Status values:",
        "PASS"
        if len(invalid_status) == 0
        else "FAIL"
    )

    # ----------------------------------------
    # Payment method validation
    # ----------------------------------------

    invalid_methods = output[
        ~output[
            "recommended_payment_method"
        ].isin(
            ALLOWED_METHODS
        )
    ]

    print(
        "\nInvalid payment methods:",
        len(invalid_methods)
    )

    print(
        "Payment methods:",
        "PASS"
        if len(invalid_methods) == 0
        else "FAIL"
    )

    # ----------------------------------------
    # Amount validation
    # ----------------------------------------

    invalid_amounts = output[
        pd.to_numeric(
            output["amount_safe_to_pay"],
            errors="coerce"
        ).isna()
    ]

    print(
        "\nInvalid safe amounts:",
        len(invalid_amounts)
    )

    print(
        "Safe amounts:",
        "PASS"
        if len(invalid_amounts) == 0
        else "FAIL"
    )

    # ----------------------------------------
    # Required text fields
    # ----------------------------------------

    text_columns = [
        "payment_plan",
        "spending_changes_needed",
        "decision_explanation"
    ]

    print("\nEmpty required text fields:")

    for column in text_columns:

        empty_count = (
            output[column]
            .isna()
            .sum()
        )

        print(
            f"  {column}: {empty_count}"
        )

    # ----------------------------------------
    # Status distribution
    # ----------------------------------------

    print("\nStatus distribution:")

    print(
        output[
            "affordability_status"
        ].value_counts()
    )

    # ----------------------------------------
    # Method distribution
    # ----------------------------------------

    print("\nPayment method distribution:")

    print(
        output[
            "recommended_payment_method"
        ].value_counts()
    )

    # ----------------------------------------
    # Sample output
    # ----------------------------------------

    print("\nFirst 5 rows:")

    print(
        output.head(5).to_string(
            index=False
        )
    )

    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()