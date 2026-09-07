import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


# -----------------------------
# Configuration
# -----------------------------

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

OUTPUT_PATH = "data/synthetic/synthetic_airfare_observations.csv"

N_ROWS = 50000

ROUTES = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL"),
    ("BOM", "DEL"),
    ("BLR", "DEL"),
    ("HYD", "DEL"),
    ("CCU", "DEL"),
]

AIRLINES = [
    "IndiGo",
    "Air India",
    "Air India Express",
    "Akasa Air",
    "SpiceJet",
]

SOURCES = [
    "makemytrip",
    "goibibo",
    "ixigo",
    "cleartrip",
    "indigo",
    "air_india",
    "easemytrip",
]

FARE_CLASSES = [
    "Economy",
    "Economy Flex",
]

ADVANCE_WINDOWS = [1, 7, 15, 30, 45]

START_DATE = datetime(2026, 7, 1)
END_DATE = datetime(2026, 9, 3)


# -----------------------------
# Helper functions
# -----------------------------

def random_collection_date():
    days = (END_DATE - START_DATE).days
    return START_DATE + timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def generate_flight_number(airline):
    prefixes = {
        "IndiGo": "6E",
        "Air India": "AI",
        "Air India Express": "IX",
        "Akasa Air": "QP",
        "SpiceJet": "SG",
    }

    return f"{prefixes[airline]}{random.randint(100, 9999)}"


def route_base_price(origin, destination):
    route_prices = {
        ("DEL", "BOM"): 5500,
        ("DEL", "BLR"): 6200,
        ("BOM", "BLR"): 4800,
        ("DEL", "CCU"): 5800,
        ("BLR", "HYD"): 3500,
        ("MAA", "DEL"): 6500,
        ("BOM", "DEL"): 5500,
        ("BLR", "DEL"): 6200,
        ("HYD", "DEL"): 5000,
        ("CCU", "DEL"): 5800,
    }

    return route_prices.get((origin, destination), 5500)


def airline_multiplier(airline):
    return {
        "IndiGo": 1.00,
        "Air India": 1.08,
        "Air India Express": 0.95,
        "Akasa Air": 0.97,
        "SpiceJet": 0.92,
    }[airline]


def lead_time_multiplier(advance_days):
    return {
        1: 1.65,
        7: 1.30,
        15: 1.10,
        30: 0.95,
        45: 0.90,
    }[advance_days]


def fare_components(base_fare):
    taxes = base_fare * np.random.uniform(0.15, 0.22)
    fees = np.random.uniform(150, 450)

    total = base_fare + taxes + fees

    return (
        round(base_fare, 2),
        round(taxes, 2),
        round(fees, 2),
        round(total, 2),
    )


# -----------------------------
# Generate observations
# -----------------------------

rows = []

for _ in range(N_ROWS):

    origin, destination = random.choice(ROUTES)

    airline = random.choice(AIRLINES)

    source = random.choice(SOURCES)

    fare_class = random.choice(FARE_CLASSES)

    advance_days = random.choice(ADVANCE_WINDOWS)

    collection_timestamp = random_collection_date()

    travel_date = collection_timestamp + timedelta(days=advance_days)

    base_price = route_base_price(origin, destination)

    price = (
        base_price
        * airline_multiplier(airline)
        * lead_time_multiplier(advance_days)
    )

    # Weekend effect
    if travel_date.weekday() >= 5:
        price *= 1.10

    # Random market noise
    price *= np.random.normal(1.0, 0.08)

    # Economy Flex is more expensive
    if fare_class == "Economy Flex":
        price *= 1.15

    base_fare, taxes, fees, total_fare = fare_components(price)

    availability = "available"

    # Some flights are sold out
    if random.random() < 0.03:
        availability = "sold_out"

    rows.append({
        "collection_timestamp": collection_timestamp,
        "source": source,
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "airline": airline,
        "flight_number": generate_flight_number(airline),
        "fare_class": fare_class,
        "advance_days": advance_days,
        "base_fare": base_fare,
        "taxes": taxes,
        "fees": fees,
        "total_fare": total_fare,
        "currency": "INR",
        "availability": availability,
    })


df = pd.DataFrame(rows)


# -----------------------------
# Inject realistic data problems
# -----------------------------

# Missing total fares
missing_total = np.random.choice(
    df.index,
    size=int(len(df) * 0.012),
    replace=False
)

df.loc[missing_total, "total_fare"] = np.nan


# Missing base fares
missing_base = np.random.choice(
    df.index,
    size=int(len(df) * 0.008),
    replace=False
)

df.loc[missing_base, "base_fare"] = np.nan


# Negative fares
negative_indices = np.random.choice(
    df.index,
    size=int(len(df) * 0.003),
    replace=False
)

df.loc[negative_indices, "total_fare"] *= -1


# Inject price shocks / anomalies
shock_indices = np.random.choice(
    df.index,
    size=int(len(df) * 0.025),
    replace=False
)

df.loc[shock_indices, "total_fare"] *= np.random.uniform(
    1.25,
    2.10,
    size=len(shock_indices)
)


# -----------------------------
# Add duplicates
# -----------------------------

duplicate_indices = np.random.choice(
    df.index,
    size=int(len(df) * 0.015),
    replace=False
)

duplicates = df.loc[duplicate_indices].copy()

df = pd.concat(
    [df, duplicates],
    ignore_index=True
)


# -----------------------------
# Shuffle
# -----------------------------

df = df.sample(
    frac=1,
    random_state=SEED
).reset_index(drop=True)


# -----------------------------
# Save
# -----------------------------

os.makedirs(
    os.path.dirname(OUTPUT_PATH),
    exist_ok=True
)

df.to_csv(
    OUTPUT_PATH,
    index=False
)

print("=" * 60)
print("Synthetic airfare dataset generated")
print("=" * 60)
print(f"Rows: {len(df):,}")
print(f"Columns: {len(df.columns)}")
print(f"Saved to: {OUTPUT_PATH}")
print()
print(df.head())