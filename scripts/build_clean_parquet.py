from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CSV_PATH = PROJECT_ROOT / "data/processed/real/clean_airfare_observations.csv"
PARQUET_PATH = PROJECT_ROOT / "data/processed/real/clean_airfare_observations.parquet"


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Clean CSV not found: {CSV_PATH}")

    print("========================================")
    print("BUILDING CLEAN AIRFARE PARQUET")
    print("========================================")
    print(f"Source : {CSV_PATH}")
    print(f"Output : {PARQUET_PATH}")

    df = pd.read_csv(CSV_PATH)

    print(f"Rows   : {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(
        PARQUET_PATH,
        engine="pyarrow",
        index=False,
    )

    size_mb = PARQUET_PATH.stat().st_size / (1024 * 1024)

    print(f"Size   : {size_mb:.2f} MB")
    print("✓ Parquet generated successfully.")
    print("========================================")


if __name__ == "__main__":
    main()
