import sys
sys.path.append("code")

from data_loader import load_data

data = load_data()

events = data["events"]

user_id = "user_26"

user_events = events[
    events["user_id"] == user_id
].copy()

print("\n" + "=" * 70)
print("EVENT DIAGNOSTIC")
print("=" * 70)

print("\nTotal events:", len(user_events))

print("\n--- DIRECTION VALUES ---")
print(user_events["direction"].value_counts(dropna=False))

print("\n--- STATUS VALUES ---")
print(user_events["status"].value_counts(dropna=False))

print("\n--- EVENT TYPE VALUES ---")
print(user_events["event_type"].value_counts(dropna=False))

print("\n--- FLEXIBILITY VALUES ---")
print(user_events["flexibility"].value_counts(dropna=False))

print("\n--- SAMPLE EVENTS ---")
print(
    user_events[
        [
            "event_id",
            "event_type",
            "description",
            "category",
            "direction",
            "amount",
            "currency",
            "event_date",
            "settlement_date",
            "status",
            "flexibility",
        ]
    ].head(20).to_string(index=False)
)

print("\n" + "=" * 70)