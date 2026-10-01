import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


PROJECT_ROOT = Path(__file__).resolve().parents[1]

R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = os.environ["R2_BUCKET"]

R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)


FILES = {
    "data/raw/airfare_index.json": "raw/airfare_index.json",
    "data/processed/real/clean_airfare_observations.parquet":
        "processed/clean_airfare_observations.parquet",

    "data/processed/real/index/real_coverage_report.csv":
        "index/real_coverage_report.csv",

    "data/processed/real/index/real_daily_airfare_index.csv":
        "index/real_daily_airfare_index.csv",

    "data/processed/real/index/real_daily_route_fares.csv":
        "index/real_daily_route_fares.csv",

    "data/processed/real/index/real_index_metadata.json":
        "index/real_index_metadata.json",

    "data/processed/real/index/real_lead_time_contributions.csv":
        "index/real_lead_time_contributions.csv",

    "data/processed/real/index/real_route_contributions.csv":
        "index/real_route_contributions.csv",

    "data/processed/real/index/real_route_indices.csv":
        "index/real_route_indices.csv",

    "data/processed/real/index/real_stratum_indices.csv":
        "index/real_stratum_indices.csv",
}


def upload(local_path: Path, remote_key: str):
    if not local_path.exists():
        print(f"SKIP  {local_path} — file not found")
        return

    size_mb = local_path.stat().st_size / (1024 * 1024)

    print(f"\nUploading:")
    print(f"  Local : {local_path}")
    print(f"  R2    : {remote_key}")
    print(f"  Size  : {size_mb:.2f} MB")

    s3.upload_file(
        str(local_path),
        R2_BUCKET,
        remote_key,
    )

    print("  ✓ Uploaded")


def main():
    print("AirFareX → Cloudflare R2")
    print(f"Bucket: {R2_BUCKET}")

    # Verify bucket access first.
    try:
        s3.head_bucket(Bucket=R2_BUCKET)
    except ClientError as exc:
        print("ERROR: Cannot access R2 bucket.")
        print(exc)
        raise SystemExit(1)

    for relative_path, remote_key in FILES.items():
        upload(PROJECT_ROOT / relative_path, remote_key)

    print("\nAll uploads completed.")


if __name__ == "__main__":
    main()
