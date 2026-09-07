from src.airfare_ml.data.profiling import (
    load_dataset,
    check_schema,
    profile_dataset,
    print_profile,
)


DATA_PATH = "data/synthetic/synthetic_airfare_observations.csv"


def main():
    df = load_dataset(DATA_PATH)

    schema = check_schema(df)

    print("\nSchema valid:", schema["valid"])

    if schema["missing_columns"]:
        print(
            "Missing columns:",
            schema["missing_columns"],
        )

    if schema["extra_columns"]:
        print(
            "Extra columns:",
            schema["extra_columns"],
        )

    profile = profile_dataset(df)

    print_profile(profile)


if __name__ == "__main__":
    main()
    