import pandas as pd

from data_loader import load_data


# ============================================================
# CONFIGURATION
# ============================================================

MAX_CHANGES = 3


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):

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


# ============================================================
# FIND FLEXIBLE EVENTS
# ============================================================

def get_flexible_events(events):
    """
    Return recurring expenses that the user is allowed
    to reduce or stop.
    """

    events = events.copy()

    events["flexibility"] = (
        events["flexibility"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    flexible = events[
        events["flexibility"]
        == "reducible_or_stoppable"
    ].copy()

    # Only settled expenses
    flexible = flexible[
        flexible["status"]
        .astype(str)
        .str.lower()
        .eq("settled")
    ]

    # Only debit/outgoing events
    flexible = flexible[
        flexible["direction"]
        .astype(str)
        .str.lower()
        .eq("debit")
    ]

    # Amount must exist
    flexible = flexible[
        flexible["amount"].notna()
    ]

    return flexible


# ============================================================
# DETECT RECURRING FLEXIBLE EXPENSES
# ============================================================

def detect_flexible_recurring_events(events):

    flexible = get_flexible_events(
        events
    )

    if flexible.empty:
        return []

    flexible["event_date_parsed"] = pd.to_datetime(
        flexible["event_date"],
        errors="coerce"
    )

    flexible = flexible[
        flexible["event_date_parsed"].notna()
    ]

    recurring = []

    group_columns = [
        "event_type",
        "category",
        "description",
        "direction",
    ]

    for _, group in flexible.groupby(
        group_columns
    ):

        group = group.sort_values(
            "event_date_parsed"
        )

        if len(group) < 2:
            continue

        dates = (
            group[
                "event_date_parsed"
            ]
            .dt.date
            .tolist()
        )

        # Check approximately monthly recurrence
        monthly_count = 0

        for i in range(
            1,
            len(dates)
        ):

            gap = (
                dates[i]
                - dates[i - 1]
            ).days

            if 25 <= gap <= 35:
                monthly_count += 1

        if monthly_count == 0:
            continue

        latest = group.iloc[-1]

        amount = safe_float(
            latest["amount"]
        )

        minimum_amount = safe_float(
            latest.get(
                "minimum_allowed_amount"
            )
        )

        recurring.append({
            "event_id":
                latest["event_id"],

            "event_type":
                latest["event_type"],

            "category":
                latest["category"],

            "description":
                latest["description"],

            "amount":
                amount,

            "minimum_allowed_amount":
                minimum_amount,

            "flexibility":
                latest["flexibility"],

            "recurring_day":
                latest[
                    "event_date_parsed"
                ].day,

            "occurrences":
                len(group),
        })

    return recurring


# ============================================================
# GENERATE STOP OPTIONS
# ============================================================

def generate_stop_changes(
    recurring_events
):
    """
    Generate possible stop:<event_id> changes.
    """

    changes = []

    for event in recurring_events:

        changes.append({
            "type": "stop",
            "event_id":
                event["event_id"],
            "change":
                f"stop:{event['event_id']}",
            "monthly_saving":
                event["amount"],
            "description":
                event["description"],
        })

    return changes


# ============================================================
# GENERATE REDUCTION OPTIONS
# ============================================================

def generate_reduce_changes(
    recurring_events
):
    """
    Generate reduce_to:<event_id>:<amount> changes.

    If a minimum allowed amount exists, don't go below it.

    Otherwise reduce the expense by 50%.
    """

    changes = []

    for event in recurring_events:

        amount = event[
            "amount"
        ]

        minimum = event[
            "minimum_allowed_amount"
        ]

        if amount <= 0:
            continue

        # ----------------------------------------------------
        # Determine reduced amount
        # ----------------------------------------------------

        if minimum > 0:

            new_amount = max(
                minimum,
                amount * 0.50
            )

        else:

            new_amount = (
                amount * 0.50
            )

        # If reduction gives no saving, skip
        if new_amount >= amount:
            continue

        changes.append({
            "type": "reduce",
            "event_id":
                event["event_id"],
            "new_amount":
                round(
                    new_amount,
                    2
                ),
            "change":
                (
                    f"reduce_to:"
                    f"{event['event_id']}:"
                    f"{new_amount:.2f}"
                ),
            "monthly_saving":
                round(
                    amount - new_amount,
                    2
                ),
            "description":
                event["description"],
        })

    return changes


# ============================================================
# RANK CHANGES
# ============================================================

def rank_spending_changes(
    recurring_events
):
    """
    Rank flexible spending changes.

    Highest monthly saving first.
    """

    stop_changes = generate_stop_changes(
        recurring_events
    )

    reduce_changes = generate_reduce_changes(
        recurring_events
    )

    all_changes = (
        stop_changes
        + reduce_changes
    )

    all_changes.sort(
        key=lambda x: (
            -x["monthly_saving"],
            x["event_id"],
        )
    )

    return all_changes


# ============================================================
# SELECT TOP 3
# ============================================================

def select_best_changes(
    recurring_events,
    max_changes=MAX_CHANGES,
):
    """
    Return up to 3 useful spending changes.
    """

    ranked = rank_spending_changes(
        recurring_events
    )

    selected = []

    used_events = set()

    for change in ranked:

        event_id = change[
            "event_id"
        ]

        # Don't use stop and reduce for
        # the same event.
        if event_id in used_events:
            continue

        selected.append(change)

        used_events.add(
            event_id
        )

        if len(selected) >= max_changes:
            break

    return selected


# ============================================================
# MAIN
# ============================================================

def main():

    print("Loading dataset...")

    data = load_data()

    events = data[
        "events"
    ]

    user_id = "user_26"

    user_events = events[
        events["user_id"]
        == user_id
    ].copy()

    # --------------------------------------------------------
    # Detect
    # --------------------------------------------------------

    recurring_events = (
        detect_flexible_recurring_events(
            user_events
        )
    )

    print()
    print("=" * 70)
    print("FLEXIBLE RECURRING EXPENSES")
    print("=" * 70)

    if not recurring_events:

        print(
            "No flexible recurring expenses found."
        )

        return

    for event in recurring_events:

        print()
        print(
            f"Event ID       : "
            f"{event['event_id']}"
        )

        print(
            f"Description    : "
            f"{event['description']}"
        )

        print(
            f"Category       : "
            f"{event['category']}"
        )

        print(
            f"Current Amount : "
            f"{event['amount']:.2f}"
        )

        print(
            f"Minimum Amount : "
            f"{event['minimum_allowed_amount']:.2f}"
        )

        print(
            f"Occurrences    : "
            f"{event['occurrences']}"
        )

    # --------------------------------------------------------
    # Best changes
    # --------------------------------------------------------

    changes = select_best_changes(
        recurring_events
    )

    print()
    print("=" * 70)
    print("RECOMMENDED SPENDING CHANGES")
    print("=" * 70)

    if not changes:

        print(
            "No spending changes available."
        )

    else:

        for change in changes:

            print()
            print(
                f"Change         : "
                f"{change['change']}"
            )

            print(
                f"Description    : "
                f"{change['description']}"
            )

            print(
                f"Monthly Saving : "
                f"{change['monthly_saving']:.2f}"
            )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()