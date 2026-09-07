from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.data_loader import (
    load_clean_data,
    load_daily_index,
    load_route_indices,
    load_advance_window_indices,
)

from dashboard.metrics import (
    latest_index,
    previous_index,
    index_change_percent,
    latest_collection_date,
    observation_count,
    route_count,
    airline_count,
    source_count,
)

from dashboard.charts import (
    create_overall_index_chart,
    create_route_index_chart,
    create_lead_time_chart,
    create_airline_fare_chart,
    create_source_chart,
)

from dashboard.components import (
    render_header,
    render_methodology_note,
    render_data_status,
)

from dashboard.monitoring import (
    calculate_data_quality,
    calculate_source_coverage,
    calculate_route_coverage,
    detect_fare_anomalies,
)


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Real-time Airfare Price Index",
    page_icon="✈️",
    layout="wide",
)


# =========================================================
# LOAD DATA
# =========================================================

clean_data = load_clean_data()
daily_index = load_daily_index()
route_indices = load_route_indices()
advance_indices = load_advance_window_indices()


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("Dashboard Controls")

st.sidebar.caption(
    "Statistical monitoring controls"
)


# ---------------------------------------------------------
# Date filter
# ---------------------------------------------------------

if not daily_index.empty:

    valid_dates = pd.to_datetime(
        daily_index["collection_date"],
        errors="coerce",
    ).dropna()

    if not valid_dates.empty:

        min_date = valid_dates.min().date()
        max_date = valid_dates.max().date()

        selected_dates = st.sidebar.date_input(
            "Collection Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    else:

        selected_dates = None

else:

    selected_dates = None


# ---------------------------------------------------------
# Route filter
# ---------------------------------------------------------

if not clean_data.empty:

    available_routes = sorted(
        (
            clean_data["origin"]
            .astype(str)
            .str.upper()
            .str.strip()
            + "_"
            + clean_data["destination"]
            .astype(str)
            .str.upper()
            .str.strip()
        )
        .dropna()
        .unique()
    )

else:

    available_routes = []


selected_routes = st.sidebar.multiselect(
    "Routes",
    options=available_routes,
    default=[],
)


# ---------------------------------------------------------
# Airline filter
# ---------------------------------------------------------

if not clean_data.empty:

    available_airlines = sorted(
        clean_data["airline"]
        .dropna()
        .astype(str)
        .unique()
    )

else:

    available_airlines = []


selected_airlines = st.sidebar.multiselect(
    "Airlines",
    options=available_airlines,
    default=[],
)


# ---------------------------------------------------------
# Source filter
# ---------------------------------------------------------

if not clean_data.empty:

    available_sources = sorted(
        clean_data["source"]
        .dropna()
        .astype(str)
        .unique()
    )

else:

    available_sources = []


selected_sources = st.sidebar.multiselect(
    "Data Sources",
    options=available_sources,
    default=[],
)


# ---------------------------------------------------------
# Display controls
# ---------------------------------------------------------

st.sidebar.divider()

show_anomalies = st.sidebar.checkbox(
    "Show anomaly monitoring",
    value=True,
)

show_source_coverage = st.sidebar.checkbox(
    "Show source coverage",
    value=True,
)

show_route_coverage = st.sidebar.checkbox(
    "Show route coverage",
    value=True,
)


# ---------------------------------------------------------
# Refresh
# ---------------------------------------------------------

st.sidebar.divider()

if st.sidebar.button(
    "🔄 Refresh Dashboard",
    use_container_width=True,
):

    st.cache_data.clear()
    st.rerun()


# =========================================================
# APPLY FILTERS
# =========================================================

filtered_clean_data = clean_data.copy()
filtered_daily_index = daily_index.copy()
filtered_route_indices = route_indices.copy()
filtered_advance_indices = advance_indices.copy()


# ---------------------------------------------------------
# Date filtering
# ---------------------------------------------------------

if (
    selected_dates is not None
    and len(selected_dates) == 2
):

    start_date = pd.Timestamp(
        selected_dates[0]
    )

    end_date = (
        pd.Timestamp(selected_dates[1])
        + pd.Timedelta(days=1)
    )

    # Filter index dates
    if "collection_date" in filtered_daily_index.columns:

        filtered_daily_index[
            "collection_date"
        ] = pd.to_datetime(
            filtered_daily_index[
                "collection_date"
            ],
            errors="coerce",
        )

        filtered_daily_index = filtered_daily_index[
            (
                filtered_daily_index["collection_date"]
                >= start_date
            )
            &
            (
                filtered_daily_index["collection_date"]
                < end_date
            )
        ]

    # Filter raw observations
    if "collection_timestamp" in filtered_clean_data.columns:

        collection_timestamp = pd.to_datetime(
            filtered_clean_data[
                "collection_timestamp"
            ],
            errors="coerce",
        )

        filtered_clean_data = filtered_clean_data[
            (
                collection_timestamp
                >= start_date
            )
            &
            (
                collection_timestamp
                < end_date
            )
        ]


# ---------------------------------------------------------
# Create route field for raw observations
# ---------------------------------------------------------

if not filtered_clean_data.empty:

    filtered_clean_data["route"] = (
        filtered_clean_data["origin"]
        .astype(str)
        .str.upper()
        .str.strip()
        + "_"
        + filtered_clean_data["destination"]
        .astype(str)
        .str.upper()
        .str.strip()
    )


# ---------------------------------------------------------
# Route filtering
# ---------------------------------------------------------

if selected_routes:

    if "route" in filtered_clean_data.columns:

        filtered_clean_data = filtered_clean_data[
            filtered_clean_data["route"].isin(
                selected_routes
            )
        ]

    if (
        "route"
        in filtered_route_indices.columns
    ):

        filtered_route_indices = filtered_route_indices[
            filtered_route_indices["route"].isin(
                selected_routes
            )
        ]

    if (
        "route"
        in filtered_advance_indices.columns
    ):

        filtered_advance_indices = filtered_advance_indices[
            filtered_advance_indices["route"].isin(
                selected_routes
            )
        ]


# ---------------------------------------------------------
# Airline filtering
# ---------------------------------------------------------

if selected_airlines:

    if "airline" in filtered_clean_data.columns:

        filtered_clean_data = filtered_clean_data[
            filtered_clean_data["airline"].isin(
                selected_airlines
            )
        ]


# ---------------------------------------------------------
# Source filtering
# ---------------------------------------------------------

if selected_sources:

    if "source" in filtered_clean_data.columns:

        filtered_clean_data = filtered_clean_data[
            filtered_clean_data["source"].isin(
                selected_sources
            )
        ]


# =========================================================
# HEADER
# =========================================================

render_header()

render_methodology_note()


# =========================================================
# FILTER SUMMARY
# =========================================================

active_filters = []

if selected_routes:
    active_filters.append(
        f"Routes: {', '.join(selected_routes)}"
    )

if selected_airlines:
    active_filters.append(
        f"Airlines: {', '.join(selected_airlines)}"
    )

if selected_sources:
    active_filters.append(
        f"Sources: {', '.join(selected_sources)}"
    )


if active_filters:

    st.info(
        "Active dashboard filters — "
        + " | ".join(active_filters)
    )


# =========================================================
# SYSTEM STATUS
# =========================================================

st.subheader("📡 Data System Status")

render_data_status(
    latest_date=latest_collection_date(
        filtered_daily_index
    ),
    observations=observation_count(
        filtered_clean_data
    ),
    routes=route_count(
        filtered_clean_data
    ),
    airlines=airline_count(
        filtered_clean_data
    ),
    sources=source_count(
        filtered_clean_data
    ),
)


# =========================================================
# MARKET SNAPSHOT
# =========================================================

st.subheader("Airfare Market Snapshot")


if filtered_daily_index.empty:

    st.warning(
        "No index observations are available "
        "for the selected filters."
    )

else:

    current = latest_index(
        filtered_daily_index
    )

    previous = previous_index(
        filtered_daily_index
    )

    change = index_change_percent(
        current,
        previous,
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Current Airfare Index",
        f"{current:.2f}",
    )

    col2.metric(
        "Previous Index",
        f"{previous:.2f}",
    )

    col3.metric(
        "Period Change",
        f"{change:+.2f}%",
    )

    col4.metric(
        "Index Base",
        "100",
    )


# =========================================================
# OVERALL INDEX TREND
# =========================================================

st.subheader("📈 Airfare Price Movement")


if filtered_daily_index.empty:

    st.info(
        "No time-series observations available."
    )

else:

    fig = create_overall_index_chart(
        filtered_daily_index
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# =========================================================
# INDEX INTERPRETATION
# =========================================================

st.subheader("📊 Index Interpretation")


if not filtered_daily_index.empty:

    current = latest_index(
        filtered_daily_index
    )

    previous = previous_index(
        filtered_daily_index
    )

    change = index_change_percent(
        current,
        previous,
    )

    if pd.notna(change):

        if change > 0:

            st.info(
                f"The latest observed airfare index is "
                f"**{current:.2f}**, representing an "
                f"increase of **{change:+.2f}%** from "
                f"the previous observed period."
            )

        elif change < 0:

            st.info(
                f"The latest observed airfare index is "
                f"**{current:.2f}**, representing a "
                f"decrease of **{change:+.2f}%** from "
                f"the previous observed period."
            )

        else:

            st.info(
                f"The latest observed airfare index is "
                f"**{current:.2f}**, with no change "
                f"from the previous observed period."
            )

    else:

        st.warning(
            "Insufficient observations are available "
            "for index movement interpretation."
        )

else:

    st.warning(
        "No observations are available for interpretation."
    )


# =========================================================
# ROUTE-LEVEL MONITORING
# =========================================================

st.subheader("🗺 Route-level Monitoring")


if filtered_route_indices.empty:

    st.info(
        "No route-level index data is available."
    )

else:

    route_fig = create_route_index_chart(
        filtered_route_indices
    )

    st.plotly_chart(
        route_fig,
        use_container_width=True,
    )


# =========================================================
# ROUTE COVERAGE
# =========================================================

if show_route_coverage:

    st.subheader("🗺 Route Coverage")

    route_coverage = calculate_route_coverage(
        filtered_clean_data
    )

    if route_coverage.empty:

        st.info(
            "No route coverage data available."
        )

    else:

        st.dataframe(
            route_coverage,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# ADVANCE PURCHASE WINDOW
# =========================================================

st.subheader("⏱ Advance Purchase Window")


if filtered_advance_indices.empty:

    st.info(
        "No advance-window index data is available."
    )

else:

    lead_fig = create_lead_time_chart(
        filtered_advance_indices
    )

    st.plotly_chart(
        lead_fig,
        use_container_width=True,
    )


# =========================================================
# AIRLINE AND SOURCE ANALYSIS
# =========================================================

col1, col2 = st.columns(2)


with col1:

    st.subheader("✈ Airline Fare Distribution")

    if filtered_clean_data.empty:

        st.info(
            "No airline fare data available."
        )

    else:

        airline_fig = create_airline_fare_chart(
            filtered_clean_data
        )

        st.plotly_chart(
            airline_fig,
            use_container_width=True,
        )


with col2:

    st.subheader("📡 Data Source Coverage")

    if filtered_clean_data.empty:

        st.info(
            "No source data available."
        )

    else:

        source_fig = create_source_chart(
            filtered_clean_data
        )

        st.plotly_chart(
            source_fig,
            use_container_width=True,
        )


# =========================================================
# DATA QUALITY MONITORING
# =========================================================

st.subheader("🛡 Data Quality Monitoring")


quality = calculate_data_quality(
    filtered_clean_data
)


q1, q2, q3, q4 = st.columns(4)


q1.metric(
    "Total Observations",
    f"{quality['total_observations']:,}",
)


q2.metric(
    "Missing Fares",
    f"{quality['missing_fare_pct']:.2f}%",
)


q3.metric(
    "Duplicate Rows",
    f"{quality['duplicate_pct']:.2f}%",
)


quality_healthy = (
    quality["missing_fare_pct"] == 0
    and quality["duplicate_pct"] < 1
)


q4.metric(
    "Data Quality Status",
    "Healthy" if quality_healthy else "Review",
)


# =========================================================
# SOURCE COVERAGE TABLE
# =========================================================

if show_source_coverage:

    st.subheader("📡 Source Coverage Details")

    source_coverage = calculate_source_coverage(
        filtered_clean_data
    )

    if source_coverage.empty:

        st.info(
            "No source coverage data available."
        )

    else:

        st.dataframe(
            source_coverage,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# FARE ANOMALY MONITORING
# =========================================================

if show_anomalies:

    st.subheader("⚠️ Fare Anomaly Monitoring")

    anomaly_data = detect_fare_anomalies(
        filtered_clean_data
    )

    if anomaly_data.empty:

        st.info(
            "No anomaly-monitoring data is available."
        )

    else:

        anomaly_count = int(
            anomaly_data[
                "anomaly_flag"
            ].sum()
        )

        anomaly_rate = (
            anomaly_count
            / len(anomaly_data)
            * 100
        )

        a1, a2 = st.columns(2)

        a1.metric(
            "Potential Anomalies",
            f"{anomaly_count:,}",
        )

        a2.metric(
            "Anomaly Rate",
            f"{anomaly_rate:.2f}%",
        )

        flagged = anomaly_data[
            anomaly_data["anomaly_flag"]
        ].copy()

        if flagged.empty:

            st.success(
                "No potential fare anomalies detected."
            )

        else:

            st.warning(
                "Potential anomalies detected. "
                "These observations are flagged for "
                "review and are not automatically removed."
            )

            display_columns = [
                column
                for column in [
                    "collection_timestamp",
                    "origin",
                    "destination",
                    "airline",
                    "flight_number",
                    "advance_days",
                    "total_fare",
                    "route",
                    "anomaly_flag",
                ]
                if column in flagged.columns
            ]

            st.dataframe(
                flagged[
                    display_columns
                ].head(100),
                use_container_width=True,
                hide_index=True,
            )


# =========================================================
# LATEST INDEX OBSERVATIONS
# =========================================================

st.subheader("🔎 Latest Index Observations")


if filtered_daily_index.empty:

    st.info(
        "No index observations available."
    )

else:

    latest_observations = (
        filtered_daily_index
        .sort_values(
            "collection_date"
        )
        .tail(20)
    )

    st.dataframe(
        latest_observations,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        label="⬇️ Download Index Data",
        data=filtered_daily_index.to_csv(
            index=False
        ).encode("utf-8"),
        file_name="airfare_index.csv",
        mime="text/csv",
        use_container_width=True,
    )


# =========================================================
# RAW / CLEAN OBSERVATION DOWNLOAD
# =========================================================

if not filtered_clean_data.empty:

    st.subheader(
        "⬇️ Processed Observation Export"
    )

    st.download_button(
        label="Download Processed Airfare Observations",
        data=filtered_clean_data.to_csv(
            index=False
        ).encode("utf-8"),
        file_name="processed_airfare_observations.csv",
        mime="text/csv",
        use_container_width=True,
    )


# =========================================================
# AUTOMATED STATISTICAL PROCESSING
# =========================================================

st.subheader(
    "⚙️ Automated Statistical Processing"
)


processing_steps = [
    (
        "1",
        "Data Collection",
        "Collect airfare observations from configured sources.",
    ),
    (
        "2",
        "Raw Data Preservation",
        "Preserve source payloads with provenance and identifiers.",
    ),
    (
        "3",
        "Normalization",
        "Standardize routes, fares, dates and source fields.",
    ),
    (
        "4",
        "Quality Validation",
        "Detect missing, invalid and duplicate observations.",
    ),
    (
        "5",
        "Representative Fare",
        "Calculate robust representative fares.",
    ),
    (
        "6",
        "Route Aggregation",
        "Construct route-level price indices.",
    ),
    (
        "7",
        "Weighted Aggregation",
        "Combine route indices into the overall index.",
    ),
    (
        "8",
        "Monitoring",
        "Monitor source coverage and potential anomalies.",
    ),
    (
        "9",
        "Reporting",
        "Expose statistical outputs through the dashboard.",
    ),
]


for step, title, description in processing_steps:

    st.markdown(
        f"""
        **{step}. {title}**  
        {description}
        """
    )


# =========================================================
# PIPELINE STATUS
# =========================================================

st.subheader(
    "⚙️ Data Pipeline Status"
)


status_col1, status_col2, status_col3 = st.columns(3)


status_col1.metric(
    "Input Dataset",
    "Available"
    if not clean_data.empty
    else "Unavailable",
)


status_col2.metric(
    "Statistical Index",
    "Generated"
    if not daily_index.empty
    else "Unavailable",
)


status_col3.metric(
    "Dashboard Data",
    "Loaded",
)


st.caption(
    "Current dashboard uses synthetic observations "
    "for pipeline and interface validation. Live "
    "source collection status will be connected to "
    "the automated collection service when production "
    "sources are enabled."
)


# =========================================================
# METHODOLOGY / STATUS NOTE
# =========================================================

st.divider()

st.caption(
    "SIH 2026 — Real-time Airfare Price Index | "
    "Smart Automation Statistical Monitoring Prototype"
)