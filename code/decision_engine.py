import pandas as pd
from datetime import datetime, timedelta

from financial_engine import calculate_safe_amount
from payment_optimizer import rank_options


# ============================================================
# CONSTANTS
# ============================================================

AFFORDABLE_NOW = "affordable_now"
AFFORDABLE_WITH_PLAN = "affordable_with_plan"
AFFORDABLE_LATER = "affordable_later"
NOT_AFFORDABLE = "not_affordable"

FULL_PAYMENT = "full_payment"
PARTIAL_PAYMENT = "partial_payment"
INSTALLMENTS = "installments"
WAIT = "wait"
NOT_RECOMMENDED = "not_recommended"


# ============================================================
# BASIC HELPERS
# ============================================================

def to_date(value):
    """
    Convert pandas/string/datetime values to date.
    """

    if value is None:
        return None

    if pd.isna(value):
        return None

    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            pass

    if isinstance(value, datetime):
        return value.date()

    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def safe_float(value, default=0.0):
    """
    Safely convert a value to float.
    """

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        return float(value)
    except Exception:
        return default


def parse_bool(value):
    """
    Convert common boolean representations.
    """

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()

    return text in {
        "true",
        "1",
        "yes",
        "y",
        "allowed"
    }


def money(value):
    return round(
        safe_float(value),
        2
    )


# ============================================================
# USER PAYMENT PREFERENCES
# ============================================================

def parse_payment_methods(profile):
    """
    Read payment_methods_user_will_consider.

    Handles values such as:

    ['full_payment', 'installments']

    or

    full_payment,installments
    """

    value = profile.get(
        "payment_methods_user_will_consider",
        ""
    )

    if value is None:
        return []

    text = str(value).strip()

    # Remove brackets
    text = text.replace(
        "[",
        ""
    ).replace(
        "]",
        ""
    )

    # Remove quotes
    text = text.replace(
        "'",
        ""
    ).replace(
        '"',
        ""
    )

    # Support comma / pipe / semicolon
    for separator in ["|", ";"]:
        text = text.replace(
            separator,
            ","
        )

    methods = []

    for item in text.split(","):

        item = item.strip().lower()

        if item:
            methods.append(item)

    return methods


def accepts_method(profile, method):

    methods = parse_payment_methods(
        profile
    )

    return method.lower() in methods


# ============================================================
# PAYMENT PLAN HELPERS
# ============================================================

def build_payment_plan(payments):
    """
    Convert:

        [(date, amount), (date, amount)]

    into:

        YYYY-MM-DD:amount|YYYY-MM-DD:amount
    """

    if not payments:
        return "none"

    normalized = []

    for date_value, amount in payments:

        date_value = to_date(
            date_value
        )

        if date_value is None:
            continue

        normalized.append(
            (
                date_value,
                money(amount)
            )
        )

    normalized.sort(
        key=lambda x: x[0]
    )

    if not normalized:
        return "none"

    return "|".join(
        f"{date_value.strftime('%Y-%m-%d')}:{amount:.2f}"
        for date_value, amount in normalized
    )


def make_full_payment_plan(
    request_date,
    amount
):

    return [
        (
            to_date(request_date),
            money(amount)
        )
    ]


def make_partial_payment_plan(
    request_date,
    safe_amount,
    requested_amount,
    earliest_full_date
):
    """
    Strict partial payment:

    Payment 1:
        safe amount on request date

    Payment 2:
        remaining amount on earliest full payment date
    """

    request_date = to_date(
        request_date
    )

    earliest_full_date = to_date(
        earliest_full_date
    )

    safe_amount = money(
        safe_amount
    )

    requested_amount = money(
        requested_amount
    )

    if request_date is None:
        return None

    if earliest_full_date is None:
        return None

    if safe_amount <= 0:
        return None

    if safe_amount >= requested_amount:
        return None

    remaining = money(
        requested_amount - safe_amount
    )

    return [
        (
            request_date,
            safe_amount
        ),
        (
            earliest_full_date,
            remaining
        )
    ]


# ============================================================
# SAFE AMOUNT
# ============================================================

def get_safe_amount(
    profile,
    events,
    request_date,
    requested_amount
):
    """
    Call the existing financial_engine without
    using unsupported keyword arguments.

    The existing project version expects positional
    arguments.
    """

    request_date = to_date(
        request_date
    )

    requested_amount = money(
        requested_amount
    )

    try:

        result = calculate_safe_amount(
            profile,
            events,
            request_date,
            requested_amount
        )

    except TypeError:

        # Compatibility fallback:
        # some versions may have a different positional order.

        try:

            result = calculate_safe_amount(
                events,
                profile,
                request_date,
                requested_amount
            )

        except Exception:

            return {
                "amount_safe_to_pay": 0.0,
                "earliest_date_for_full_payment": None
            }

    except Exception:

        return {
            "amount_safe_to_pay": 0.0,
            "earliest_date_for_full_payment": None
        }

    # ----------------------------------------
    # Result is dictionary
    # ----------------------------------------

    if isinstance(result, dict):

        safe_amount = result.get(
            "amount_safe_to_pay",
            result.get(
                "safe_amount",
                result.get(
                    "max_safe_amount",
                    0
                )
            )
        )

        earliest_date = result.get(
            "earliest_date_for_full_payment",
            result.get(
                "earliest_full_payment_date",
                None
            )
        )

        return {
            "amount_safe_to_pay": min(
                money(safe_amount),
                requested_amount
            ),
            "earliest_date_for_full_payment":
                to_date(earliest_date)
        }

    # ----------------------------------------
    # Result is numeric
    # ----------------------------------------

    if isinstance(
        result,
        (int, float)
    ):

        return {
            "amount_safe_to_pay": min(
                money(result),
                requested_amount
            ),
            "earliest_date_for_full_payment":
                None
        }

    return {
        "amount_safe_to_pay": 0.0,
        "earliest_date_for_full_payment": None
    }


# ============================================================
# PAYMENT OPTION EXTRACTION
# ============================================================

def get_option_value(option, key, default=None):

    if isinstance(option, dict):
        return option.get(
            key,
            default
        )

    try:
        return option[key]
    except Exception:
        return default


def normalize_option(option):

    return {
        "payment_option_id":
            get_option_value(
                option,
                "payment_option_id"
            ),

        "payment_method":
            str(
                get_option_value(
                    option,
                    "payment_method",
                    ""
                )
            ).strip().lower(),

        "payment_amount":
            money(
                get_option_value(
                    option,
                    "payment_amount",
                    0
                )
            ),

        "number_of_payments":
            int(
                safe_float(
                    get_option_value(
                        option,
                        "number_of_payments",
                        1
                    ),
                    1
                )
            ),

        "first_payment_date":
            to_date(
                get_option_value(
                    option,
                    "first_payment_date"
                )
            ),

        "payment_frequency_days":
            safe_float(
                get_option_value(
                    option,
                    "payment_frequency_days"
                ),
                0
            ),

        "financing_fee":
            money(
                get_option_value(
                    option,
                    "financing_fee",
                    0
                )
            ),

        "total_payable_amount":
            money(
                get_option_value(
                    option,
                    "total_payable_amount",
                    0
                )
            )
    }


def option_payments(
    option,
    requested_amount
):
    """
    Construct chronological payments from a payment option.
    """

    option = normalize_option(
        option
    )

    first_date = option[
        "first_payment_date"
    ]

    if first_date is None:
        return []

    number_of_payments = max(
        1,
        option["number_of_payments"]
    )

    amount = option[
        "payment_amount"
    ]

    frequency = option[
        "payment_frequency_days"
    ]

    # Full payment / one payment
    if number_of_payments == 1:

        return [
            (
                first_date,
                money(
                    requested_amount
                )
            )
        ]

    payments = []

    for index in range(
        number_of_payments
    ):

        payment_date = first_date + timedelta(
            days=int(
                frequency * index
            )
        )

        payments.append(
            (
                payment_date,
                amount
            )
        )

    # Correct final rounding difference
    total = sum(
        amount
        for _, amount in payments
    )

    difference = money(
        requested_amount - total
    )

    if abs(difference) > 0.01:

        last_date, last_amount = payments[-1]

        payments[-1] = (
            last_date,
            money(
                last_amount + difference
            )
        )

    return payments


# ============================================================
# RANK PAYMENT OPTIONS
# ============================================================

def get_valid_payment_options(
    request,
    profile,
    payment_options
):
    """
    Return payment options that the user accepts.
    """

    if payment_options is None:
        return []

    if isinstance(
        payment_options,
        pd.DataFrame
    ):

        options = payment_options.to_dict(
            orient="records"
        )

    elif isinstance(
        payment_options,
        list
    ):

        options = payment_options

    else:

        try:
            options = list(
                payment_options
            )
        except Exception:
            options = []

    valid = []

    for option in options:

        normalized = normalize_option(
            option
        )

        method = normalized[
            "payment_method"
        ]

        if not accepts_method(
            profile,
            method
        ):
            continue

        valid.append(
            normalized
        )

    return valid


# ============================================================
# DETERMINE PLAN
# ============================================================

def find_best_payment_option(
    request,
    profile,
    events,
    payment_options
):
    """
    Use payment_optimizer when possible.

    If its interface differs, safely fall back to
    local option ranking.
    """

    try:

        ranked = rank_options(
            request,
            profile,
            events,
            payment_options
        )

        if ranked:

            return ranked[0]

    except Exception:
        pass

    options = get_valid_payment_options(
        request,
        profile,
        payment_options
    )

    if not options:
        return None

    # Basic deterministic ranking
    options.sort(
        key=lambda option: (
            option["total_payable_amount"]
            if option["total_payable_amount"] > 0
            else float("inf"),

            option["number_of_payments"],

            str(
                option["payment_option_id"]
            )
        )
    )

    return options[0]


# ============================================================
# SPENDING CHANGES
# ============================================================

def get_spending_changes(
    request,
    profile,
    events
):
    """
    Safely call spending_changes module.

    If unavailable, return none rather than inventing changes.
    """

    try:

        from spending_changes import (
            get_recommended_changes
        )

        result = get_recommended_changes(
            request=request,
            profile=profile,
            events=events
        )

        if result is None:
            return []

        if isinstance(
            result,
            str
        ):
            if result.lower() == "none":
                return []
            return [result]

        return list(result)[:3]

    except Exception:

        return []


# ============================================================
# STATUS
# ============================================================

def determine_status(
    requested_amount,
    safe_now,
    valid_plan,
    earliest_full_date,
    desired_completion_date
):
    """
    Determine one of the four allowed statuses.
    """

    requested_amount = money(
        requested_amount
    )

    safe_now = money(
        safe_now
    )

    earliest_full_date = to_date(
        earliest_full_date
    )

    desired_completion_date = to_date(
        desired_completion_date
    )

    # Full amount safe today
    if safe_now >= requested_amount:
        return AFFORDABLE_NOW

    # A valid plan exists
    if valid_plan:
        return AFFORDABLE_WITH_PLAN

    # Full amount becomes safe later
    if earliest_full_date is not None:

        if earliest_full_date > to_date(
            datetime.now()
        ):

            return AFFORDABLE_LATER

    return NOT_AFFORDABLE


# ============================================================
# EXPLANATION
# ============================================================

def build_explanation(
    requested_amount,
    safe_now,
    status,
    method,
    earliest_date,
    spending_changes
):

    requested_amount = money(
        requested_amount
    )

    safe_now = money(
        safe_now
    )

    text = (
        f"Requested amount: {requested_amount:.2f}. "
        f"Safe amount available now: {safe_now:.2f}. "
    )

    if status == AFFORDABLE_NOW:

        text += (
            "The full requested amount is affordable now "
            "while maintaining the required financial safety buffer."
        )

    elif status == AFFORDABLE_WITH_PLAN:

        text += (
            "The full amount is not safely payable immediately, "
            "but a payment plan can complete the purchase."
        )

    elif status == AFFORDABLE_LATER:

        text += (
            "The full amount is not safely payable now but "
            "becomes affordable at a later date."
        )

    else:

        text += (
            "The request cannot be safely completed within "
            "the available financial forecast."
        )

    if method != NOT_RECOMMENDED:

        text += (
            f" Recommended payment method: {method}."
        )

    if earliest_date:

        text += (
            f" Earliest full-payment date: "
            f"{earliest_date.strftime('%Y-%m-%d')}."
        )

    if spending_changes:

        text += (
            " Flexible spending changes may be used "
            "where permitted by the user's preferences."
        )

    return text


# ============================================================
# MAIN DECISION FUNCTION
# ============================================================

def make_decision(
    request,
    profile,
    events,
    payment_options,
    messages=None,
    images=None
):
    """
    Main financial decision engine.

    Returns exactly the required eight fields.
    """

    request_id = request.get(
        "request_id"
    )

    request_date = to_date(
        request.get(
            "request_date"
        )
    )

    desired_completion_date = to_date(
        request.get(
            "desired_completion_date"
        )
    )

    requested_amount = money(
        request.get(
            "requested_amount",
            0
        )
    )

    # --------------------------------------------------------
    # 1. SAFE AMOUNT
    # --------------------------------------------------------

    safe_result = get_safe_amount(
        profile=profile,
        events=events,
        request_date=request_date,
        requested_amount=requested_amount
    )

    safe_now = money(
        safe_result.get(
            "amount_safe_to_pay",
            0
        )
    )

    earliest_full_date = to_date(
        safe_result.get(
            "earliest_date_for_full_payment"
        )
    )

    # Never exceed requested amount
    safe_now = min(
        safe_now,
        requested_amount
    )

    # --------------------------------------------------------
    # 2. PAYMENT OPTIONS
    # --------------------------------------------------------

    best_option = find_best_payment_option(
        request=request,
        profile=profile,
        events=events,
        payment_options=payment_options
    )

    valid_plan = (
        best_option is not None
    )

    # --------------------------------------------------------
    # 3. SPENDING CHANGES
    # --------------------------------------------------------

    spending_changes = get_spending_changes(
        request=request,
        profile=profile,
        events=events
    )

    # --------------------------------------------------------
    # 4. STATUS
    # --------------------------------------------------------

    status = determine_status(
        requested_amount=requested_amount,
        safe_now=safe_now,
        valid_plan=valid_plan,
        earliest_full_date=earliest_full_date,
        desired_completion_date=desired_completion_date
    )

    # --------------------------------------------------------
    # 5. PAYMENT METHOD
    # --------------------------------------------------------

    method = NOT_RECOMMENDED
    payment_plan = "none"

    # --------------------------------------------------------
    # CASE A: AFFORDABLE NOW
    # --------------------------------------------------------

    if (
        status == AFFORDABLE_NOW
        and
        accepts_method(
            profile,
            FULL_PAYMENT
        )
    ):

        method = FULL_PAYMENT

        payments = make_full_payment_plan(
            request_date,
            requested_amount
        )

        payment_plan = build_payment_plan(
            payments
        )

    # --------------------------------------------------------
    # CASE B: INSTALLMENT PLAN
    # --------------------------------------------------------

    elif (
        best_option is not None
    ):

        option = normalize_option(
            best_option
        )

        option_method = option[
            "payment_method"
        ]

        if accepts_method(
            profile,
            option_method
        ):

            method = option_method

            payments = option_payments(
                option,
                requested_amount
            )

            payment_plan = build_payment_plan(
                payments
            )

    # --------------------------------------------------------
    # CASE C: STRICT PARTIAL PAYMENT
    # --------------------------------------------------------

    if (
        method == NOT_RECOMMENDED
        and
        parse_bool(
            request.get(
                "allows_partial_payment",
                False
            )
        )
        and
        safe_now > 0
        and
        safe_now < requested_amount
        and
        accepts_method(
            profile,
            PARTIAL_PAYMENT
        )
        and
        earliest_full_date is not None
        and
        desired_completion_date is not None
        and
        earliest_full_date <= desired_completion_date
    ):

        partial_plan = make_partial_payment_plan(
            request_date=request_date,
            safe_amount=safe_now,
            requested_amount=requested_amount,
            earliest_full_date=earliest_full_date
        )

        if partial_plan:

            method = PARTIAL_PAYMENT

            payment_plan = build_payment_plan(
                partial_plan
            )

            status = AFFORDABLE_WITH_PLAN

    # --------------------------------------------------------
    # CASE D: WAIT
    # --------------------------------------------------------

    if (
        method == NOT_RECOMMENDED
        and
        status == AFFORDABLE_LATER
        and
        accepts_method(
            profile,
            FULL_PAYMENT
        )
        and
        earliest_full_date is not None
    ):

        method = WAIT

        payment_plan = build_payment_plan(
            [
                (
                    earliest_full_date,
                    requested_amount
                )
            ]
        )

    # --------------------------------------------------------
    # 6. IF FULL PAYMENT NOW
    # --------------------------------------------------------

    if (
        safe_now >= requested_amount
        and
        accepts_method(
            profile,
            FULL_PAYMENT
    )):

        status = AFFORDABLE_NOW

        method = FULL_PAYMENT

        payment_plan = build_payment_plan(
            make_full_payment_plan(
                request_date,
                requested_amount
            )
        )

    # --------------------------------------------------------
    # 7. EXPLANATION
    # --------------------------------------------------------

    explanation = build_explanation(
        requested_amount=requested_amount,
        safe_now=safe_now,
        status=status,
        method=method,
        earliest_date=earliest_full_date,
        spending_changes=spending_changes
    )

    # --------------------------------------------------------
    # 8. FINAL OUTPUT
    # --------------------------------------------------------

    return {
        "request_id": request_id,

        "amount_safe_to_pay": money(
            safe_now
        ),

        "affordability_status": status,

        "recommended_payment_method": method,

        "payment_plan": payment_plan,

        "earliest_date_for_full_payment": (
            earliest_full_date.strftime(
                "%Y-%m-%d"
            )
            if earliest_full_date
            else ""
        ),

        "spending_changes_needed": (
            "|".join(
                spending_changes[:3]
            )
            if spending_changes
            else "none"
        ),

        "decision_explanation": explanation
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "decision_engine.py loaded successfully."
    )