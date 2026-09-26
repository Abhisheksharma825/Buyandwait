
from pathlib import Path
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset"


# ============================================================
# DATASET FILES
# ============================================================

DATA_FILES = {
    "requests": "requests.csv",
    "profiles": "financial_profiles.csv",
    "events": "financial_events.csv",
    "messages": "messages.csv",
    "images": "images.csv",
    "exchange_rates": "exchange_rates.csv",
    "payment_options": "request_payment_options.csv",
    "sample_requests": "sample_requests.csv",
}


# ============================================================
# LOAD CSV FILES
# ============================================================

def load_data():
    """
    Load all required CSV files from the dataset directory.

    Returns:
        dict: Dictionary containing all datasets as pandas DataFrames.
    """

    data = {}

    for name, filename in DATA_FILES.items():

        file_path = DATASET_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"\nDataset file not found:\n{file_path}\n"
            )

        try:
            df = pd.read_csv(file_path)

            data[name] = df

        except Exception as error:
            raise RuntimeError(
                f"Could not read {filename}: {error}"
            )

    return data


# ============================================================
# VALIDATE DATA
# ============================================================

def validate_data(data):
    """
    Check whether important columns exist in the datasets.
    """

    required_columns = {

        "requests": [
            "request_id",
            "user_id",
            "request_date",
            "request_type",
            "requested_amount",
            "desired_completion_date",
        ],

        "profiles": [
            "user_id",
            "current_available_balance",
            "minimum_balance_to_keep",
        ],

        "events": [
            "event_id",
            "user_id",
            "event_type",
            "amount",
            "currency",
            "event_date",
        ],

        "payment_options": [
            "request_id",
        ],
    }

    for dataset_name, columns in required_columns.items():

        df = data[dataset_name]

        missing_columns = [
            column
            for column in columns
            if column not in df.columns
        ]

        if missing_columns:

            raise ValueError(
                f"\n{dataset_name}.csv is missing columns: "
                f"{missing_columns}\n"
            )


# ============================================================
# CONVERT DATE COLUMNS
# ============================================================

def convert_dates(data):
    """
    Convert date columns into pandas datetime objects.
    """

    date_columns = {

        "requests": [
            "request_date",
            "desired_completion_date",
        ],

        "events": [
            "event_date",
            "settlement_date",
        ],

        "messages": [
            "message_date",
        ],

        "exchange_rates": [
            "rate_date",
        ],
    }

    for dataset_name, columns in date_columns.items():

        if dataset_name not in data:
            continue

        df = data[dataset_name]

        for column in columns:

            if column in df.columns:

                df[column] = pd.to_datetime(
                    df[column],
                    errors="coerce"
                )


# ============================================================
# DATASET SUMMARY
# ============================================================

def print_dataset_summary(data):

    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)

    for name, df in data.items():

        print(
            f"{name:<20} : "
            f"{len(df):>6} rows | "
            f"{len(df.columns):>3} columns"
        )

    print("=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    print("\nLoading financial dataset...")

    # Load
    data = load_data()

    # Validate
    validate_data(data)

    # Convert dates
    convert_dates(data)

    # Show summary
    print_dataset_summary(data)

    print("\n✅ Dataset loaded successfully!")
    print("✅ Required columns validated!")
    print("✅ Date columns converted!")

    print("\nAvailable datasets:")

    for name in data:
        print(f"  - {name}")

    print("\n")


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()

