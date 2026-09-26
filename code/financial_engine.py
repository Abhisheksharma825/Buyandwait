
import pandas as pd

from cashflow import (
    evaluate_payment_safety,
    calculate_max_safe_amount,
    find_earliest_full_payment_date,
)


def calculate_safe_amount(
    profile,
    events,
    request_date,
    requested_amount,
    forecast_days=90,
):
    """
    Compatibility wrapper around the cashflow engine.

    Returns stable keys used by decision_engine.py.
    """

    requested_amount = float(
        requested_amount or 0
    )

    # ---------------------------------------------------------
    # Full request safety check
    # ---------------------------------------------------------

    try:

        full_check = evaluate_payment_safety(
            profile=profile,
            events=events,
            request_date=request_date,
            requested_amount=requested_amount,
            forecast_days=forecast_days,
        )

    except TypeError:

        # Positional fallback for older cashflow signature
        full_check = evaluate_payment_safety(
            profile,
            events,
            request_date,
            requested_amount,
            forecast_days,
        )

    # ---------------------------------------------------------
    # Maximum amount safely payable
    # ---------------------------------------------------------

    try:

        safe_amount = calculate_max_safe_amount(
            profile=profile,
            events=events,
            request_date=request_date,
            requested_amount=requested_amount,
            forecast_days=forecast_days,
        )

    except TypeError:

        safe_amount = calculate_max_safe_amount(
            profile,
            events,
            request_date,
            requested_amount,
            forecast_days,
        )

    # ---------------------------------------------------------
    # Normalize safe amount
    # ---------------------------------------------------------

    if isinstance(safe_amount, dict):

        safe_value = (
            safe_amount.get("safe_amount")
            or safe_amount.get("amount_safe_to_pay")
            or 0
        )

    else:

        safe_value = safe_amount or 0

    safe_value = float(safe_value)

    safe_value = max(
        0.0,
        min(
            safe_value,
            requested_amount
        )
    )

    # ---------------------------------------------------------
    # Minimum balance
    # ---------------------------------------------------------

    minimum_balance = (
        full_check.get("minimum_balance", 0)
        if isinstance(full_check, dict)
        else 0
    )

    try:
        minimum_balance = float(
            minimum_balance or 0
        )
    except (
        TypeError,
        ValueError
    ):
        minimum_balance = 0.0

    # ---------------------------------------------------------
    # Lowest projected balance
    # ---------------------------------------------------------

    lowest_balance = (
        full_check.get("lowest_balance")
        if isinstance(full_check, dict)
        else None
    )

    if lowest_balance is None:

        lowest_balance = (
            full_check.get("min_balance")
            if isinstance(full_check, dict)
            else None
        )

    try:

        lowest_balance = (
            float(lowest_balance)
            if lowest_balance is not None
            else 0.0
        )

    except (
        TypeError,
        ValueError
    ):

        lowest_balance = 0.0

    # ---------------------------------------------------------
    # Full amount safe?
    # ---------------------------------------------------------

    full_amount_safe = (
        safe_value >= requested_amount - 0.01
    )

    if isinstance(full_check, dict):

        if "full_amount_safe" in full_check:

            full_amount_safe = bool(
                full_check["full_amount_safe"]
            )

        elif "safe" in full_check:

            full_amount_safe = bool(
                full_check["safe"]
            )

    # ---------------------------------------------------------
    # Earliest full-payment date
    # ---------------------------------------------------------

    try:

        earliest_date = (
            find_earliest_full_payment_date(
                profile=profile,
                events=events,
                request_date=request_date,
                requested_amount=requested_amount,
                forecast_days=forecast_days,
            )
        )

    except TypeError:

        earliest_date = (
            find_earliest_full_payment_date(
                profile,
                events,
                request_date,
                requested_amount,
                forecast_days,
            )
        )

    # ---------------------------------------------------------
    # Normalize date
    # ---------------------------------------------------------

    if earliest_date is None:

        earliest_date_value = ""

    else:

        try:

            earliest_date_value = (
                pd.to_datetime(
                    earliest_date
                ).strftime("%Y-%m-%d")
            )

        except Exception:

            earliest_date_value = str(
                earliest_date
            )

    # ---------------------------------------------------------
    # Stable result
    # ---------------------------------------------------------

    return {

        "safe_amount":
            round(safe_value, 2),

        "amount_safe_to_pay":
            round(safe_value, 2),

        "lowest_balance":
            round(lowest_balance, 2),

        "minimum_balance":
            round(minimum_balance, 2),

        "full_amount_safe":
            full_amount_safe,

        "earliest_date_for_full_payment":
            earliest_date_value,

        "full_check":
            full_check,
    }


if __name__ == "__main__":

    print("=" * 60)
    print("FINANCIAL ENGINE TEST")
    print("=" * 60)

    print(
        "Financial engine loaded successfully."
    )

    print(
        "No dataset test is executed automatically."
    )