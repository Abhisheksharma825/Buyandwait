from datetime import timedelta
import pandas as pd

from data_loader import load_data
from financial_engine import calculate_safe_amount
from cashflow import check_safety, to_date


# ============================================================
# CONFIGURATION
# ============================================================

FORECAST_DAYS = 90

VALID_METHODS = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
}


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_method(value):
    return str(value).strip().lower()


def safe_float(value, default=0.0):
    """
    Convert a value to float safely.
    Handles NaN / blank values.
    """

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass

    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """
    Convert a value to integer safely.
    """

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass

    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# ============================================================
# USER PAYMENT PREFERENCES
# ============================================================

def get_allowed_payment_methods(profile):
    """
    Extract payment methods the user is willing to consider.
    """

    value = profile.get(
        "payment_methods_user_will_consider",
        ""
    )

    if pd.isna(value):
        return set()

    text = str(value).lower()

    # Handle common separators
    text = text.replace("|", ",")
    text = text.replace(";", ",")
    text = text.replace("/", ",")

    methods = set()

    for item in text.split(","):

        item = item.strip()

        if item:
            methods.add(
                normalize_method(item)
            )

    return methods


# ============================================================
# OPTION VALIDATION
# ============================================================

def option_is_allowed(
    option,
    profile,
    request,
):
    """
    Check whether the payment option matches
    the user's allowed payment methods.
    """

    method = normalize_method(
        option["payment_method"]
    )

    allowed_methods = get_allowed_payment_methods(
        profile
    )

    # If the dataset has explicit preferences,
    # enforce them.
    if allowed_methods:

        if method not in allowed_methods:
            return False

    # --------------------------------------------------------
    # Installment limit
    # --------------------------------------------------------

    if method == "installments":

        number_of_payments = safe_int(
            option.get(
                "number_of_payments"
            )
        )

        max_months = safe_int(
            profile.get(
                "max_installment_months"
            )
        )

        if (
            max_months > 0
            and number_of_payments > max_months
        ):
            return False

    return True


# ============================================================
# OPTION TOTAL COST
# ============================================================

def option_total_cost(option):
    """
    Return total amount eventually paid.
    """

    total = option.get(
        "total_payable_amount"
    )

    if total is not None:

        try:
            if not pd.isna(total):
                return float(total)
        except (TypeError, ValueError):
            pass

    return safe_float(
        option.get("payment_amount")
    )


# ============================================================
# FINAL PAYMENT DATE
# ============================================================

def get_final_payment_date(option):
    """
    Calculate the date of the final payment.

    For full payment:
        frequency can be blank because there is
        only one payment.

    For installments:
        payment_frequency_days must exist.
    """

    first_payment_date = to_date(
        option.get("first_payment_date")
    )

    if first_payment_date is None:
        return None

    number_of_payments = safe_int(
        option.get(
            "number_of_payments"
        ),
        default=1,
    )

    if number_of_payments <= 1:
        return first_payment_date

    frequency_value = option.get(
        "payment_frequency_days"
    )

    if frequency_value is None:

        return None

    try:
        if pd.isna(frequency_value):
            return None
    except (TypeError, ValueError):
        return None

    frequency = safe_int(
        frequency_value
    )

    if frequency <= 0:
        return None

    return (
        first_payment_date
        + timedelta(
            days=(
                number_of_payments - 1
            ) * frequency
        )
    )


# ============================================================
# FULL PAYMENT SAFETY
# ============================================================

def is_full_payment_safe(
    profile,
    events,
    request_date,
    requested_amount,
):
    """
    Check whether the entire requested amount
    can safely be paid immediately.
    """

    result = check_safety(
        profile=profile,
        events=events,
        request_date=request_date,
        payment_amount=float(
            requested_amount
        ),
        forecast_days=FORECAST_DAYS,
    )

    return result


# ============================================================
# INSTALLMENT PLAN SAFETY
# ============================================================

def is_installment_plan_safe(
    profile,
    events,
    option,
):
    """
    Check the complete installment schedule.

    Every installment must be affordable while
    preserving the minimum balance.
    """

    payment_amount = safe_float(
        option.get("payment_amount")
    )

    number_of_payments = safe_int(
        option.get(
            "number_of_payments"
        )
    )

    first_payment_date = to_date(
        option.get(
            "first_payment_date"
        )
    )

    frequency_value = option.get(
        "payment_frequency_days"
    )

    # Invalid installment data
    if payment_amount <= 0:
        return False

    if number_of_payments <= 0:
        return False

    if first_payment_date is None:
        return False

    if frequency_value is None:
        return False

    try:
        if pd.isna(frequency_value):
            return False
    except (TypeError, ValueError):
        return False

    frequency = safe_int(
        frequency_value
    )

    if frequency <= 0:
        return False

    # --------------------------------------------------------
    # Important:
    #
    # Build ONE combined 90-day forecast with every
    # installment added on its actual payment date.
    #
    # This prevents incorrectly resetting the balance
    # for every installment.
    # --------------------------------------------------------

    from cashflow import build_cashflow

    # Determine final payment date
    final_payment_date = (
        first_payment_date
        + timedelta(
            days=(
                number_of_payments - 1
            ) * frequency
        )
    )

    forecast_days = max(
        FORECAST_DAYS,
        (
            final_payment_date
            - first_payment_date
        ).days + 1,
    )

    # Base cash flow
    forecast, minimum_balance = build_cashflow(
        profile=profile,
        events=events,
        request_date=first_payment_date,
        forecast_days=forecast_days,
        extra_expense=0.0,
    )

    # --------------------------------------------------------
    # Add installments
    # --------------------------------------------------------

    for i in range(
        number_of_payments
    ):

        payment_date = (
            first_payment_date
            + timedelta(
                days=i * frequency
            )
        )

        mask = (
            forecast["date"]
            == payment_date
        )

        forecast.loc[
            mask,
            "extra_expense"
        ] += payment_amount

    # --------------------------------------------------------
    # Recalculate running balance
    # --------------------------------------------------------

    balance = safe_float(
        profile[
            "current_available_balance"
        ]
    )

    for _, row in forecast.iterrows():

        balance = (
            balance
            + row["income"]
            - row["expense"]
            - row["extra_expense"]
        )

        if balance < minimum_balance:

            return False

    return True


# ============================================================
# RANKING
# ============================================================

def rank_options(
    options,
    profile,
    request,
    events,
):
    """
    Select the best valid payment option.

    Ranking:

    1. Finish by desired completion date
    2. Lower total payable amount
    3. Earlier first payment
    4. Fewer payments
    5. Lowest payment_option_id
    """

    request_date = to_date(
        request["request_date"]
    )

    desired_date = to_date(
        request[
            "desired_completion_date"
        ]
    )

    requested_amount = safe_float(
        request[
            "requested_amount"
        ]
    )

    candidates = []

    for _, option in options.iterrows():

        method = normalize_method(
            option["payment_method"]
        )

        # ----------------------------------------------------
        # Supported method
        # ----------------------------------------------------

        if method not in VALID_METHODS:
            continue

        # ----------------------------------------------------
        # User preference
        # ----------------------------------------------------

        if not option_is_allowed(
            option,
            profile,
            request,
        ):
            continue

        first_payment_date = to_date(
            option.get(
                "first_payment_date"
            )
        )

        if first_payment_date is None:
            continue

        # Payment shouldn't start before request date
        if first_payment_date < request_date:
            continue

        # ----------------------------------------------------
        # Final payment date
        # ----------------------------------------------------

        final_payment_date = (
            get_final_payment_date(
                option
            )
        )

        if final_payment_date is None:
            continue

        # Must finish by desired date
        if (
            desired_date is not None
            and final_payment_date
            > desired_date
        ):
            continue

        # ----------------------------------------------------
        # Safety
        # ----------------------------------------------------

        if method == "full_payment":

            result = is_full_payment_safe(
                profile=profile,
                events=events,
                request_date=request_date,
                requested_amount=requested_amount,
            )

            safe = result["safe"]

        elif method == "installments":

            safe = is_installment_plan_safe(
                profile=profile,
                events=events,
                option=option,
            )

        else:

            # Partial payment and wait are handled
            # by decision_engine.
            safe = False

        if not safe:
            continue

        # ----------------------------------------------------
        # Candidate
        # ----------------------------------------------------

        candidates.append({
            "option": option,
            "final_payment_date":
                final_payment_date,
            "first_payment_date":
                first_payment_date,
            "total_cost":
                option_total_cost(option),
            "number_of_payments":
                safe_int(
                    option.get(
                        "number_of_payments"
                    ),
                    default=1,
                ),
        })

    # --------------------------------------------------------
    # No valid options
    # --------------------------------------------------------

    if not candidates:
        return None

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    candidates.sort(
        key=lambda item: (
            item["final_payment_date"],
            item["total_cost"],
            item["first_payment_date"],
            item["number_of_payments"],
            str(
                item["option"][
                    "payment_option_id"
                ]
            ),
        )
    )

    return candidates[0]


# ============================================================
# MAIN
# ============================================================

def main():

    print("Loading dataset...")

    data = load_data()

    requests = data["requests"]
    profiles = data["profiles"]
    events = data["events"]
    payment_options = data[
        "payment_options"
    ]

    request_id = "request_26"

    # --------------------------------------------------------
    # Request
    # --------------------------------------------------------

    request_rows = requests[
        requests["request_id"]
        == request_id
    ]

    if request_rows.empty:

        print(
            f"❌ Request not found: "
            f"{request_id}"
        )

        return

    request = request_rows.iloc[0]

    user_id = request[
        "user_id"
    ]

    # --------------------------------------------------------
    # Profile
    # --------------------------------------------------------

    profile_rows = profiles[
        profiles["user_id"]
        == user_id
    ]

    if profile_rows.empty:

        print(
            f"❌ Profile not found for "
            f"{user_id}"
        )

        return

    profile = profile_rows.iloc[0]

    # --------------------------------------------------------
    # User events
    # --------------------------------------------------------

    user_events = events[
        events["user_id"]
        == user_id
    ].copy()

    # --------------------------------------------------------
    # Payment options
    # --------------------------------------------------------

    options = payment_options[
        payment_options["request_id"]
        == request_id
    ].copy()

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("PAYMENT OPTIONS")
    print("=" * 70)

    for _, option in options.iterrows():

        print(
            f"ID: "
            f"{option['payment_option_id']} | "
            f"Method: "
            f"{option['payment_method']} | "
            f"Amount: "
            f"{option['payment_amount']} | "
            f"Payments: "
            f"{option['number_of_payments']} | "
            f"Frequency: "
            f"{option['payment_frequency_days']} | "
            f"Total: "
            f"{option['total_payable_amount']}"
        )

    # --------------------------------------------------------
    # User preferences
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("USER PAYMENT PREFERENCES")
    print("=" * 70)

    print(
        profile[
            "payment_methods_user_will_consider"
        ]
    )

    print(
        "Max installment months:",
        profile[
            "max_installment_months"
        ]
    )

    # --------------------------------------------------------
    # Rank
    # --------------------------------------------------------

    best = rank_options(
        options=options,
        profile=profile,
        request=request,
        events=user_events,
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BEST PAYMENT OPTION")
    print("=" * 70)

    if best is None:

        print(
            "❌ No valid payment option found."
        )

    else:

        option = best["option"]

        print(
            "Payment Option ID :",
            option[
                "payment_option_id"
            ]
        )

        print(
            "Method            :",
            option[
                "payment_method"
            ]
        )

        print(
            "Payment Amount    :",
            option[
                "payment_amount"
            ]
        )

        print(
            "Number of Payments:",
            option[
                "number_of_payments"
            ]
        )

        print(
            "Total Payable     :",
            option[
                "total_payable_amount"
            ]
        )

        print(
            "First Payment     :",
            option[
                "first_payment_date"
            ]
        )

        print(
            "Final Payment     :",
            best[
                "final_payment_date"
            ]
        )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()