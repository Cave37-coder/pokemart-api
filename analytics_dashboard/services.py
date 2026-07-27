# analytics_dashboard/services.py
# Wraps the GA4 Data API. All functions return plain dicts/lists ready for JSON.
# Requires env var GA4_PROPERTY_ID (e.g. "465691608") and
# GOOGLE_APPLICATION_CREDENTIALS_JSON (the full contents of the service account
# JSON key, stored as a single-line env var on Railway) OR
# GOOGLE_APPLICATION_CREDENTIALS pointing at a key file path.

import json
import os
from datetime import datetime, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    RunFunnelReportRequest,
    FunnelStep,
    Funnel,
    FunnelFieldFilter,
    FunnelEventFilter,
    FunnelFilterExpression,
)
from google.oauth2 import service_account

PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")


def _get_client():
    """Builds an authenticated GA4 Data API client from env-provided credentials."""
    raw_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if raw_json:
        info = json.loads(raw_json)
        credentials = service_account.Credentials.from_service_account_info(info)
        return BetaAnalyticsDataClient(credentials=credentials)
    # Falls back to GOOGLE_APPLICATION_CREDENTIALS file path if set instead.
    return BetaAnalyticsDataClient()


def get_daily_visits(days: int = 30) -> list[dict]:
    """Returns [{date: 'YYYY-MM-DD', visitors: int, sessions: int}, ...] for the last N days."""
    client = _get_client()
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        order_bys=[{"dimension": {"dimension_name": "date"}}],
    )
    response = client.run_report(request)

    results = []
    for row in response.rows:
        raw_date = row.dimension_values[0].value  # YYYYMMDD
        formatted = f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        results.append({
            "date": formatted,
            "visitors": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value),
        })
    return results


def get_conversion_summary(days: int = 30) -> dict:
    """Returns overall sessions, purchases, and conversion rate for the period."""
    client = _get_client()
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        metrics=[
            Metric(name="sessions"),
            Metric(name="ecommercePurchases"),
            Metric(name="totalRevenue"),
        ],
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
    )
    response = client.run_report(request)

    if not response.rows:
        return {"sessions": 0, "purchases": 0, "revenue": 0, "conversion_rate": 0}

    row = response.rows[0]
    sessions = int(row.metric_values[0].value)
    purchases = int(row.metric_values[1].value)
    revenue = float(row.metric_values[2].value)
    conversion_rate = round((purchases / sessions) * 100, 2) if sessions else 0

    return {
        "sessions": sessions,
        "purchases": purchases,
        "revenue": round(revenue, 2),
        "conversion_rate": conversion_rate,
    }


def get_funnel(days: int = 30) -> list[dict]:
    """
    Returns funnel drop-off across the PokeBulk purchase path:
    view_item -> add_to_cart -> begin_checkout -> purchase
    Each step includes the raw user count and % of the previous step retained.
    """
    client = _get_client()

    steps = [
        FunnelStep(
            name="View Card",
            filter_expression=FunnelFilterExpression(
                funnel_event_filter=FunnelEventFilter(event_name="view_item")
            ),
        ),
        FunnelStep(
            name="Add to Cart",
            filter_expression=FunnelFilterExpression(
                funnel_event_filter=FunnelEventFilter(event_name="add_to_cart")
            ),
        ),
        FunnelStep(
            name="Begin Checkout",
            filter_expression=FunnelFilterExpression(
                funnel_event_filter=FunnelEventFilter(event_name="begin_checkout")
            ),
        ),
        FunnelStep(
            name="Purchase",
            filter_expression=FunnelFilterExpression(
                funnel_event_filter=FunnelEventFilter(event_name="purchase")
            ),
        ),
    ]

    request = RunFunnelReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        funnel=Funnel(steps=steps),
    )
    response = client.run_funnel_report(request)

    step_names = ["View Card", "Add to Cart", "Begin Checkout", "Purchase"]
    counts = [0] * len(step_names)
    for row in response.funnel_table.rows:
        step_index = int(row.dimension_values[0].value)
        if 0 <= step_index < len(counts):
            counts[step_index] = int(float(row.metric_values[0].value))

    results = []
    for i, (name, count) in enumerate(zip(step_names, counts)):
        pct_of_previous = 100.0
        if i > 0 and counts[i - 1] > 0:
            pct_of_previous = round((count / counts[i - 1]) * 100, 1)
        results.append({
            "step": name,
            "users": count,
            "pct_of_previous": pct_of_previous,
        })
    return results
