import pandas as pd
from datetime import date, datetime, timedelta
from calendar import monthrange


# ============================================================
# CONSTANTS
# ============================================================

FORECAST_DAYS = 90


# ============================================================
# DATE HELPERS
# ============================================================

def to_date(value):
    """Fast, safe conversion to datetime.date."""
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Dataset dates are predominantly ISO formatted.
        if len(value) >= 10:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except ValueError:
                pass

    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


# ============================================================
# NUMERIC HELPERS
# ============================================================

def safe_float(value, default=0.0):

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


def normalize_amount(value):
    return safe_float(value, 0.0)


def format_amount(value):
    """Format monetary values without unnecessary trailing zeros."""
    value = round(safe_float(value, 0.0), 2)
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


# ============================================================
# EVENT HELPERS
# ============================================================

def event_value(event, key, default=None):

    try:
        if isinstance(event, dict):
            return event.get(
                key,
                default
            )

        return event[key]

    except Exception:
        return default


def is_valid_event(event):
    """
    Decide whether an event may affect the safety forecast.

    Challenge-safe interpretation:
      - settled events are realized cash flow
      - scheduled/confirmed events are known future commitments/income
      - pending DEBITS are commitments and should be protected
      - pending CREDITS are NOT guaranteed income, so ignore them
      - cancelled/failed/rejected/unrealized events are ignored
    """
    status = str(event_value(event, "status", "") or "").strip().lower()

    if status in {"cancelled", "canceled", "failed", "rejected", "unrealized"}:
        return False

    if status in {"settled", "scheduled", "confirmed"}:
        return True

    if status == "pending":
        # Pending incoming money must not make an unaffordable purchase
        # look affordable. Pending outgoing payments still reduce cash.
        return not is_credit(event)

    return status == ""


def get_event_date(event):
    """
    Prefer settlement_date.
    Fall back to event_date.
    """

    settlement_date = to_date(
        event_value(
            event,
            "settlement_date"
        )
    )

    if settlement_date is not None:
        return settlement_date

    return to_date(
        event_value(
            event,
            "event_date"
        )
    )


def get_event_amount(event):
    return normalize_amount(
        event_value(
            event,
            "amount",
            0
        )
    )


def get_event_direction(event):

    return str(
        event_value(
            event,
            "direction",
            ""
        )
    ).strip().lower()


def get_event_type(event):

    return str(
        event_value(
            event,
            "event_type",
            ""
        )
    ).strip().lower()


def get_category(event):

    return str(
        event_value(
            event,
            "category",
            ""
        )
    ).strip().lower()


def get_description(event):

    return str(
        event_value(
            event,
            "description",
            ""
        )
    ).strip().lower()


def is_debit(event):

    return get_event_direction(
        event
    ) == "debit"


def is_credit(event):

    return get_event_direction(
        event
    ) == "credit"


# ============================================================
# DATAFRAME / EVENT CONVERSION
# ============================================================

def events_to_records(events):

    if events is None:
        return []

    if isinstance(
        events,
        pd.DataFrame
    ):

        return events.to_dict(
            orient="records"
        )

    if isinstance(
        events,
        list
    ):

        return events

    try:
        return list(events)
    except Exception:
        return []


# ============================================================
# RECURRING EVENT DETECTION
# ============================================================

def event_pattern(event):
    """
    Pattern used to identify recurring events.
    """

    return (
        get_event_type(event),
        get_category(event),
        get_description(event),
        get_event_direction(event)
    )


def detect_recurring_patterns(events):
    """
    Detect approximate monthly recurring patterns.

    Optimized version:
    - converts each event date once
    - converts each amount once
    - groups lightweight prepared records
    - requires at least 3 occurrences and 2 monthly-like gaps
    """
    records = events_to_records(events)
    groups = {}

    for event in records:
        if not is_valid_event(event):
            continue

        event_date = get_event_date(event)
        if event_date is None:
            continue

        pattern = event_pattern(event)
        groups.setdefault(pattern, []).append({
            "event": event,
            "date": event_date,
            "amount": get_event_amount(event)
        })

    recurring = []

    for pattern, items in groups.items():
        if len(items) < 3:
            continue

        items.sort(key=lambda x: x["date"])
        dates = [x["date"] for x in items]

        gaps = [
            (dates[i] - dates[i - 1]).days
            for i in range(1, len(dates))
        ]

        monthly_like = sum(25 <= gap <= 35 for gap in gaps)
        if monthly_like < 2:
            continue

        amounts = [x["amount"] for x in items if x["amount"] > 0]
        if not amounts:
            continue

        last_event = items[-1]["event"]
        flexibility = str(
            event_value(last_event, "flexibility", "fixed") or "fixed"
        ).strip().lower()

        minimum_amount = safe_float(
            event_value(last_event, "minimum_allowed_amount", 0)
        )

        recurring.append({
            "pattern": pattern,
            "events": [x["event"] for x in items],
            "occurrences": len(items),
            "average_amount": sum(amounts) / len(amounts),
            "last_date": dates[-1],
            "day_of_month": dates[-1].day,
            "flexibility": flexibility,
            "minimum_allowed_amount": minimum_amount
        })

    return recurring


# ============================================================
# MONTH DATE HELPER
# ============================================================

def safe_month_date(
    year,
    month,
    day
):
    """
    Return requested day if available.
    Otherwise use last day of month.
    """

    last_day = monthrange(
        year,
        month
    )[1]

    return date(
        year,
        month,
        min(day, last_day)
    )


def add_months(
    source_date,
    months
):

    month_index = (
        source_date.year * 12
        + source_date.month
        - 1
        + months
    )

    year = month_index // 12

    month = (
        month_index % 12
    ) + 1

    return safe_month_date(
        year,
        month,
        source_date.day
    )


# ============================================================
# ACTUAL EVENT CHECK
# ============================================================

def has_actual_event(events, pattern, target_date):
    """Return True when an actual valid event already exists on target_date."""
    target_date = to_date(target_date)
    if target_date is None:
        return False

    for event in events_to_records(events):
        if not is_valid_event(event):
            continue
        if event_pattern(event) != pattern:
            continue
        if get_event_date(event) == target_date:
            return True

    return False


# ============================================================
# BALANCE INITIALIZATION
# ============================================================

def get_current_balance(profile):

    return normalize_amount(
        profile.get(
            "current_available_balance",
            0
        )
    )


def get_minimum_balance(profile):

    return normalize_amount(
        profile.get(
            "minimum_balance_to_keep",
            0
        )
    )


# ============================================================
# HISTORICAL EVENTS
# ============================================================

def apply_historical_events(
    events,
    request_date
):
    """
    Calculate net realized cash-flow occurring
    between request_date and a target forecast date.
    """

    records = events_to_records(
        events
    )

    result = {}

    for event in records:

        if not is_valid_event(event):
            continue

        event_date = get_event_date(
            event
        )

        if event_date is None:
            continue

        if event_date < request_date:
            continue

        amount = get_event_amount(
            event
        )

        if amount <= 0:
            continue

        if is_credit(event):
            signed_amount = amount

        elif is_debit(event):
            signed_amount = -amount

        else:
            continue

        if event_date not in result:
            result[event_date] = 0.0

        result[event_date] += signed_amount

    return result


# ============================================================
# RECURRING PROJECTION
# ============================================================

def project_recurring_events(
    forecast,
    events,
    recurring_patterns,
    start_date,
    end_date,
    spending_reductions=None
):
    """Project monthly recurring income/expenses into the forecast."""
    spending_reductions = spending_reductions or {}
    records = events_to_records(events)

    actual_keys = set()
    for event in records:
        if not is_valid_event(event):
            continue
        event_date = get_event_date(event)
        if event_date is not None:
            actual_keys.add((event_pattern(event), event_date))

    for recurring in recurring_patterns:
        pattern = recurring["pattern"]

        # Use the latest known occurrence on/before the request date as the
        # projection anchor. This avoids projecting from a later scheduled
        # event and accidentally pulling a future recurring payment forward.
        prepared_occurrences = []
        for e in recurring.get("events", []):
            d = get_event_date(e)
            if d is not None:
                prepared_occurrences.append((d, e))

        eligible_occurrences = [
            (d, e) for d, e in prepared_occurrences
            if d <= start_date
        ]

        if eligible_occurrences:
            last_date, last_event = max(
                eligible_occurrences, key=lambda x: x[0]
            )
            base_amount = get_event_amount(last_event)
        else:
            last_date = recurring["last_date"]
            base_amount = recurring["average_amount"]

        amount = safe_float(
            spending_reductions.get(pattern, base_amount)
        )

        if amount <= 0:
            continue

        for month_offset in range(1, 5):
            projected_date = add_months(last_date, month_offset)

            if projected_date < start_date or projected_date > end_date:
                continue

            if (pattern, projected_date) in actual_keys:
                continue

            direction = pattern[3]
            if direction == "credit":
                forecast[projected_date] = forecast.get(projected_date, 0.0) + amount
            elif direction == "debit":
                forecast[projected_date] = forecast.get(projected_date, 0.0) - amount


# ============================================================
# ACTUAL FUTURE EVENTS
# ============================================================

def add_actual_future_events(
    forecast,
    events,
    start_date,
    end_date
):
    """
    Add actual settled events that fall inside
    the forecast window.
    """

    records = events_to_records(
        events
    )

    for event in records:

        if not is_valid_event(event):
            continue

        event_date = get_event_date(
            event
        )

        if event_date is None:
            continue

        if event_date < start_date:
            continue

        if event_date > end_date:
            continue

        amount = get_event_amount(
            event
        )

        if amount <= 0:
            continue

        if is_credit(event):

            signed_amount = amount

        elif is_debit(event):

            signed_amount = -amount

        else:

            continue

        forecast[event_date] = (
            forecast.get(
                event_date,
                0.0
            )
            + signed_amount
        )


# ============================================================
# EXTRA PAYMENT
# ============================================================

def add_extra_payment(
    forecast,
    payment_date,
    payment_amount
):

    payment_date = to_date(
        payment_date
    )

    payment_amount = normalize_amount(
        payment_amount
    )

    if payment_date is None:
        return

    if payment_amount <= 0:
        return

    forecast[payment_date] = (
        forecast.get(
            payment_date,
            0.0
        )
        - payment_amount
    )


# ============================================================
# CASHFLOW FORECAST
# ============================================================

def build_cashflow(
    profile,
    events,
    request_date,
    forecast_days=FORECAST_DAYS,
    payment_date=None,
    payment_amount=0.0,
    spending_reductions=None, recurring_patterns=None
):
    """
    Build a 90-day running balance forecast.

    Returns:

        forecast list
        minimum projected balance
    """

    request_date = to_date(
        request_date
    )

    if request_date is None:
        raise ValueError(
            "Invalid request_date"
        )

    end_date = (
        request_date
        + timedelta(
            days=forecast_days
        )
    )

    current_balance = get_current_balance(
        profile
    )

    minimum_balance = get_minimum_balance(
        profile
    )

    # date -> net cashflow
    daily_cashflow = {}

    # Actual future events
    add_actual_future_events(
        daily_cashflow,
        events,
        request_date,
        end_date
    )

    # Recurring patterns. Reuse a caller-provided result when available.
    if recurring_patterns is None:
        recurring_patterns = detect_recurring_patterns(events)

    project_recurring_events(
        forecast=daily_cashflow,
        events=events,
        recurring_patterns=recurring_patterns,
        start_date=request_date,
        end_date=end_date,
        spending_reductions=spending_reductions
    )

    # Requested payment
    if (
        payment_date is not None
        and
        payment_amount > 0
    ):

        add_extra_payment(
            daily_cashflow,
            payment_date,
            payment_amount
        )

    # Build running forecast
    forecast = []

    balance = current_balance

    minimum_projected_balance = balance

    current_date = request_date

    while current_date <= end_date:

        net_change = daily_cashflow.get(
            current_date,
            0.0
        )

        balance += net_change

        minimum_projected_balance = min(
            minimum_projected_balance,
            balance
        )

        forecast.append({
            "date": current_date,
            "cashflow": round(
                net_change,
                2
            ),
            "balance": round(
                balance,
                2
            ),
            "safe": (
                balance >= minimum_balance
            )
        })

        current_date += timedelta(
            days=1
        )

    return (
        forecast,
        minimum_projected_balance
    )


# ============================================================
# SAFETY CHECK
# ============================================================

def check_safety(
    profile,
    events,
    request_date,
    payment_date=None,
    payment_amount=0.0,
    forecast_days=FORECAST_DAYS,
    spending_reductions=None, recurring_patterns=None
):
    """
    Check whether a payment is safe over the
    complete forecast period.
    """

    forecast, minimum_balance = build_cashflow(
        profile=profile,
        events=events,
        request_date=request_date,
        forecast_days=forecast_days,
        payment_date=payment_date,
        payment_amount=payment_amount,
        spending_reductions=spending_reductions,
        recurring_patterns=recurring_patterns
    )

    required_minimum = get_minimum_balance(
        profile
    )

    safe = (
        minimum_balance >= required_minimum
    )

    return {
        "safe": safe,
        "minimum_projected_balance": round(
            minimum_balance,
            2
        ),
        "required_minimum_balance": round(
            required_minimum,
            2
        ),
        "forecast": forecast
    }


# ============================================================
# FIND EARLIEST FULL PAYMENT DATE
# ============================================================

def find_earliest_full_payment_date(
    profile,
    events,
    request_date,
    requested_amount,
    forecast_days=FORECAST_DAYS
):
    """
    Find earliest date on which the full amount can safely be paid.
    Uses one base forecast instead of rebuilding a 90-day forecast
    for every candidate date.
    """
    request_date = to_date(request_date)
    requested_amount = normalize_amount(requested_amount)

    if request_date is None:
        return None

    if requested_amount <= 0:
        return request_date

    recurring_patterns = detect_recurring_patterns(events)

    forecast, _ = build_cashflow(
        profile=profile,
        events=events,
        request_date=request_date,
        forecast_days=forecast_days,
        recurring_patterns=recurring_patterns
    )

    required_minimum = get_minimum_balance(profile)

    # Payment on a candidate date subtracts requested_amount from that
    # day's end balance. Because all other cash flows are unchanged,
    # the payment is safe iff balance before payment >= minimum + amount.
    for row in forecast:
        if round(row["balance"] - requested_amount, 2) >= round(required_minimum, 2):
            return row["date"]

    return None


# ============================================================
# MAXIMUM SAFE AMOUNT NOW
# ============================================================

def calculate_max_safe_amount(
    profile,
    events,
    request_date,
    requested_amount,
    forecast_days=FORECAST_DAYS
):
    """
    Binary search the maximum amount that can be
    paid on request_date without dropping below
    the required minimum during the forecast.
    """

    request_date = to_date(
        request_date
    )

    requested_amount = normalize_amount(
        requested_amount
    )

    if requested_amount <= 0:
        return 0.0

    # Detect recurring patterns once instead of once per binary-search iteration.
    recurring_patterns = detect_recurring_patterns(events)

    # First check zero payment.
    base = check_safety(
        profile=profile,
        events=events,
        request_date=request_date,
        payment_date=None,
        payment_amount=0,
        forecast_days=forecast_days,
        recurring_patterns=recurring_patterns
    )

    if not base["safe"]:
        return 0.0

    low = 0.0
    high = requested_amount

    for _ in range(45):

        mid = (
            low + high
        ) / 2.0

        result = check_safety(
            profile=profile,
            events=events,
            request_date=request_date,
            payment_date=request_date,
            payment_amount=mid,
            forecast_days=forecast_days,
            recurring_patterns=recurring_patterns
        )

        if result["safe"]:
            low = mid
        else:
            high = mid

    return min(
        requested_amount,
        max(0.0, round(low, 2))
    )


# ============================================================
# MAIN SAFETY FUNCTION
# ============================================================

def evaluate_payment_safety(
    profile,
    events,
    request_date,
    requested_amount,
    forecast_days=FORECAST_DAYS
):
    """
    Complete safety evaluation.
    """

    request_date = to_date(
        request_date
    )

    requested_amount = normalize_amount(
        requested_amount
    )

    safe_amount = calculate_max_safe_amount(
        profile=profile,
        events=events,
        request_date=request_date,
        requested_amount=requested_amount,
        forecast_days=forecast_days
    )

    earliest_date = find_earliest_full_payment_date(
        profile=profile,
        events=events,
        request_date=request_date,
        requested_amount=requested_amount,
        forecast_days=forecast_days
    )

    return {
        "amount_safe_to_pay": safe_amount,
        "earliest_date_for_full_payment": earliest_date
    }


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def calculate_safe_amount(
    profile,
    events,
    request_date,
    requested_amount
):
    """
    Function used by financial_engine.py.
    """

    result = evaluate_payment_safety(
        profile=profile,
        events=events,
        request_date=request_date,
        requested_amount=requested_amount,
        forecast_days=FORECAST_DAYS
    )

    return result


# ============================================================
# DEBUG / TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("CASHFLOW ENGINE TEST")
    print("=" * 60)

    print(
        "\nModule loaded successfully."
    )

    print(
        f"Forecast period: {FORECAST_DAYS} days"
    )

    print(
        "\nFunctions available:"
    )

    print(
        "  build_cashflow()"
    )

    print(
        "  check_safety()"
    )

    print(
        "  calculate_max_safe_amount()"
    )

    print(
        "  find_earliest_full_payment_date()"
    )

    print(
        "  calculate_safe_amount()"
    )