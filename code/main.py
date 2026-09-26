import os
import sys
import pandas as pd

# Make sure code/ modules can import each other
CODE_DIR = os.path.dirname(os.path.abspath(__file__))

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

from data_loader import load_data
from context_builder import build_request_context
from decision_engine import make_decision


OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation"
]


def get_user_events(events, user_id):
    return events[
        events["user_id"] == user_id
    ].copy()


def get_user_messages(messages, user_id):
    if messages is None or messages.empty:
        return messages

    return messages[
        messages["user_id"] == user_id
    ].copy()


def get_user_images(images, user_id):
    if images is None or images.empty:
        return images

    return images[
        images["user_id"] == user_id
    ].copy()


def get_user_payment_options(payment_options, request_id):
    if payment_options is None or payment_options.empty:
        return payment_options

    return payment_options[
        payment_options["request_id"] == request_id
    ].copy()


def get_user_profile(profiles, user_id):
    result = profiles[
        profiles["user_id"] == user_id
    ]

    if result.empty:
        return None

    return result.iloc[0].to_dict()


def process_request(
    request,
    profiles,
    events,
    messages,
    images,
    payment_options
):
    """
    Process one request and return exactly
    the required output columns.
    """

    request_dict = request.to_dict()

    request_id = request_dict["request_id"]
    user_id = request_dict["user_id"]

    # -----------------------------
    # Profile
    # -----------------------------

    profile = get_user_profile(
        profiles,
        user_id
    )

    if profile is None:
        raise ValueError(
            f"Profile not found for {user_id}"
        )

    # -----------------------------
    # User-specific data
    # -----------------------------

    user_events = get_user_events(
        events,
        user_id
    )

    user_messages = get_user_messages(
        messages,
        user_id
    )

    user_images = get_user_images(
        images,
        user_id
    )

    request_options = get_user_payment_options(
        payment_options,
        request_id
    )

    # -----------------------------
    # Build context
    # -----------------------------

    try:

        context = build_request_context(
            request_dict,
            profile,
            user_events,
            user_messages,
            user_images,
            request_options
        )

    except TypeError:

        # Compatibility fallback
        context = {
            "request": request_dict,
            "profile": profile,
            "events": user_events,
            "messages": user_messages,
            "images": user_images,
            "payment_options": request_options
        }

    # -----------------------------
    # Extract context
    # -----------------------------

    request_data = context.get(
        "request",
        request_dict
    )

    profile_data = context.get(
        "profile",
        profile
    )

    events_data = context.get(
        "events",
        user_events
    )

    messages_data = context.get(
        "messages",
        user_messages
    )

    images_data = context.get(
        "images",
        user_images
    )

    options_data = context.get(
        "payment_options",
        request_options
    )

    # -----------------------------
    # Make decision
    # -----------------------------

    decision = make_decision(
        request=request_data,
        profile=profile_data,
        events=events_data,
        payment_options=options_data,
        messages=messages_data,
        images=images_data
    )

    # -----------------------------
    # Enforce exact output schema
    # -----------------------------

    result = {}

    for column in OUTPUT_COLUMNS:
        result[column] = decision.get(
            column,
            ""
        )

    return result


def main():

    print("=" * 60)
    print("BUY OR WAIT - FINANCIAL AGENT")
    print("=" * 60)

    # -----------------------------
    # Load dataset
    # -----------------------------

    print("\nLoading dataset...")

    data = load_data()

    # DEBUG: show actual keys
    print("\nDATA LOADER KEYS:")
    print(data.keys())

    # -----------------------------
    # Get datasets
    # -----------------------------

    requests = data["requests"]
    profiles = data["profiles"]
    events = data["events"]
    messages = data["messages"]
    images = data["images"]
    payment_options = data["payment_options"]

    print(
        f"\nRequests: {len(requests)}"
    )

    print(
        f"Profiles: {len(profiles)}"
    )

    print(
        f"Financial events: {len(events)}"
    )

    print(
        f"Messages: {len(messages)}"
    )

    print(
        f"Images: {len(images)}"
    )

    print(
        f"Payment options: {len(payment_options)}"
    )

    # -----------------------------
    # Process requests
    # -----------------------------

    results = []

    total = len(requests)

    print("\nProcessing requests...\n")

    for index, (_, request) in enumerate(
        requests.iterrows(),
        start=1
    ):

        request_id = request["request_id"]

        try:

            result = process_request(
                request=request,
                profiles=profiles,
                events=events,
                messages=messages,
                images=images,
                payment_options=payment_options
            )

            results.append(result)

            print(
                f"[{index}/{total}] "
                f"{request_id} -> "
                f"{result['affordability_status']}"
            )

        except Exception as error:

            print(
                f"[{index}/{total}] "
                f"{request_id} -> ERROR: {error}"
            )

            # Keep one output row even if
            # an individual request fails.

            results.append({
                "request_id": request_id,
                "amount_safe_to_pay": 0,
                "affordability_status": "not_affordable",
                "recommended_payment_method": "not_recommended",
                "payment_plan": "none",
                "earliest_date_for_full_payment": "",
                "spending_changes_needed": "none",
                "decision_explanation":
                    f"Unable to safely evaluate request: {error}"
            })

    # -----------------------------
    # Create DataFrame
    # -----------------------------

    output = pd.DataFrame(
        results,
        columns=OUTPUT_COLUMNS
    )

    # -----------------------------
    # Save output
    # -----------------------------

    project_root = os.path.dirname(
        CODE_DIR
    )

    output_path = os.path.join(
        project_root,
        "output.csv"
    )

    output.to_csv(
        output_path,
        index=False
    )

    # -----------------------------
    # Summary
    # -----------------------------

    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)

    print(
        f"\nOutput file: {output_path}"
    )

    print(
        f"Rows generated: {len(output)}"
    )

    print("\nStatus distribution:")

    print(
        output[
            "affordability_status"
        ].value_counts()
    )

    print("\nPayment method distribution:")

    print(
        output[
            "recommended_payment_method"
        ].value_counts()
    )

    print("\nFirst 5 results:")

    print(
        output.head(5).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()