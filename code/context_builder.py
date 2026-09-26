from data_loader import load_data


def build_request_context(data, request_id):
    """
    Build the complete financial context for one request.
    """

    requests = data["requests"]
    profiles = data["profiles"]
    events = data["events"]
    messages = data["messages"]
    images = data["images"]
    payment_options = data["payment_options"]

    # ---------------------------------------------------------
    # 1. Find request
    # ---------------------------------------------------------

    request_rows = requests[
        requests["request_id"] == request_id
    ]

    if request_rows.empty:
        raise ValueError(
            f"Request not found: {request_id}"
        )

    request = request_rows.iloc[0]

    user_id = request["user_id"]

    # ---------------------------------------------------------
    # 2. Find user's financial profile
    # ---------------------------------------------------------

    profile_rows = profiles[
        profiles["user_id"] == user_id
    ]

    if profile_rows.empty:
        raise ValueError(
            f"Financial profile not found for {user_id}"
        )

    profile = profile_rows.iloc[0]

    # ---------------------------------------------------------
    # 3. Find financial events
    # ---------------------------------------------------------

    user_events = events[
        events["user_id"] == user_id
    ].copy()

    # ---------------------------------------------------------
    # 4. Find messages
    # ---------------------------------------------------------

    user_messages = messages[
        messages["user_id"] == user_id
    ].copy()

    # ---------------------------------------------------------
    # 5. Find payment options
    # ---------------------------------------------------------

    request_options = payment_options[
        payment_options["request_id"] == request_id
    ].copy()

    # ---------------------------------------------------------
    # 6. Find related images
    # ---------------------------------------------------------

    request_images = images[
        images["request_id"] == request_id
    ].copy()

    # ---------------------------------------------------------
    # 7. Build context
    # ---------------------------------------------------------

    context = {
        "request": request.to_dict(),

        "profile": profile.to_dict(),

        "financial_events": user_events.to_dict(
            orient="records"
        ),

        "messages": user_messages.to_dict(
            orient="records"
        ),

        "payment_options": request_options.to_dict(
            orient="records"
        ),

        "images": request_images.to_dict(
            orient="records"
        ),
    }

    return context


def print_context_summary(context):

    request = context["request"]

    print("\n" + "=" * 60)
    print("REQUEST CONTEXT")
    print("=" * 60)

    print(
        f"Request ID       : "
        f"{request.get('request_id')}"
    )

    print(
        f"User ID          : "
        f"{request.get('user_id')}"
    )

    print(
        f"Request Type     : "
        f"{request.get('request_type')}"
    )

    print(
        f"Requested Amount : "
        f"{request.get('requested_amount')}"
    )

    print(
        f"Request Date     : "
        f"{request.get('request_date')}"
    )

    print(
        f"Completion Date  : "
        f"{request.get('desired_completion_date')}"
    )

    print("\nFinancial Information")
    print("-" * 60)

    print(
        f"Current Balance  : "
        f"{context['profile'].get('current_available_balance')}"
    )

    print(
        f"Minimum Balance  : "
        f"{context['profile'].get('minimum_balance_to_keep')}"
    )

    print("\nRelated Data")
    print("-" * 60)

    print(
        f"Financial Events : "
        f"{len(context['financial_events'])}"
    )

    print(
        f"Messages         : "
        f"{len(context['messages'])}"
    )

    print(
        f"Payment Options  : "
        f"{len(context['payment_options'])}"
    )

    print(
        f"Images           : "
        f"{len(context['images'])}"
    )

    print("=" * 60)


def main():

    print("Loading dataset...")

    data = load_data()

    # Test with first request
    first_request_id = data["requests"].iloc[0]["request_id"]

    print(
        f"\nBuilding context for: "
        f"{first_request_id}"
    )

    context = build_request_context(
        data,
        first_request_id
    )

    print_context_summary(context)


if __name__ == "__main__":
    main()