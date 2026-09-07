from pathlib import Path

from src.airfare_ml.data.profiling import load_dataset
from src.airfare_ml.data.cleaning import (
    clean_airfare_data,
    cleaning_summary,
    print_cleaning_summary,
)


INPUT_PATH = Path(
    "data/synthetic/synthetic_airfare_observations.csv"
)

OUTPUT_PATH = Path(
    "data/processed/clean_airfare_observations.csv"
)


def main():
    print("Loading airfare dataset...")

    df = load_dataset(INPUT_PATH)

    print(f"Loaded {len(df):,} rows.")

    clean_df = clean_airfare_data(df)

    summary = cleaning_summary(
        df,
        clean_df,
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    clean_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print_cleaning_summary(summary)

    print(
        f"\nSaved cleaned dataset to:"
        f"\n{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
    