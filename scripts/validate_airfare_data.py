from src.airfare_ml.data.profiling import load_dataset
from src.airfare_ml.data.validation import (
    validate_fares,
    validation_summary,
    print_validation_summary,
)


DATA_PATH = "data/synthetic/synthetic_airfare_observations.csv"


def main():

    df = load_dataset(DATA_PATH)

    validated_df = validate_fares(df)

    summary = validation_summary(validated_df)

    print_validation_summary(summary)


if __name__ == "__main__":
    main()
    