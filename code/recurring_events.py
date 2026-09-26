import pandas as pd
from data_loader import load_data


def detect_recurring_events(events):
    """
    Detect recurring financial events from historical data.

    Events are grouped using:
    event_type + category + description + direction

    A pattern is considered recurring when it appears
    multiple times with roughly monthly spacing.
    """

    events = events.copy()

    events["event_date"] = pd.to_datetime(
        events["event_date"],
        errors="coerce"
    )

    events = events[
        events["status"].astype(str).str.lower() == "settled"
    ]

    events = events[
        events["amount"].notna()
    ]

    groups = []

    group_columns = [
        "event_type",
        "category",
        "description",
        "direction",
    ]

    for keys, group in events.groupby(group_columns):

        group = group.sort_values("event_date")

        if len(group) < 3:
            continue

        dates = group["event_date"].tolist()

        gaps = []

        for i in range(1, len(dates)):
            gap = (dates[i] - dates[i - 1]).days
            gaps.append(gap)

        # Monthly patterns are approximately 28–31 days.
        monthly_gaps = [
            gap for gap in gaps
            if 25 <= gap <= 35
        ]

        if len(monthly_gaps) >= 2:

            avg_amount = group["amount"].mean()

            groups.append({
                "event_type": keys[0],
                "category": keys[1],
                "description": keys[2],
                "direction": keys[3],
                "occurrences": len(group),
                "average_amount": float(avg_amount),
                "last_date": dates[-1],
                "gaps": gaps,
                "flexibility": group["flexibility"].iloc[-1],
            })

    return pd.DataFrame(groups)


def main():

    data = load_data()

    events = data["events"]

    user_id = "user_26"

    user_events = events[
        events["user_id"] == user_id
    ].copy()

    recurring = detect_recurring_events(
        user_events
    )

    print("\n" + "=" * 70)
    print("RECURRING EVENT DETECTION")
    print("=" * 70)

    if recurring.empty:
        print("No recurring events detected.")
        return

    for _, row in recurring.iterrows():

        print(
            f"\n{row['event_type']} | "
            f"{row['category']} | "
            f"{row['direction']}"
        )

        print(
            f"Description : {row['description']}"
        )

        print(
            f"Occurrences : {row['occurrences']}"
        )

        print(
            f"Average amount : "
            f"{row['average_amount']:.2f}"
        )

        print(
            f"Last date : "
            f"{row['last_date'].date()}"
        )

        print(
            f"Flexibility : "
            f"{row['flexibility']}"
        )


if __name__ == "__main__":
    main()