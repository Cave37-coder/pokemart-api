# analytics_dashboard/services.py
# Wraps the GA4 Data API. All functions return plain dicts/lists ready for JSON.
# Requires env var GA4_PROPERTY_ID (e.g. "465691608") and
# GOOGLE_APPLICATION_CREDENTIALS_JSON (the full contents of the service account
# JSON key, stored as a single-line env var on Railway) OR
# GOOGLE_APPLICATION_CREDENTIALS pointing at a key file path.
#
# FIXED 2026-07-27: get_funnel() originally used RunFunnelReportRequest,
# which is part of Google's newer *alpha* Data API, not the stable v1beta
# client this project installs -- caused an ImportError on deploy. Rewritten
# to compute the funnel from standard, stable RunReportRequest calls
# (eventName dimension + totalUsers metric, filtered to our four funnel
# events), which needs no alpha access and works reliably.

import json
import os

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
    Filter,
    FilterExpression,
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
    Each step includes the unique-user count and % of the previous step retained.

    Uses a standard, stable RunReportRequest (eventName dimension + totalUsers
    metric) rather than GA4's alpha-only funnel-report endpoint -- totalUsers
    broken down by eventName gives the unique users who triggered each specific
    event in the period, which is exactly what a funnel step needs.
    """
    client = _get_client()

    event_names = ["view_item", "add_to_cart", "begin_checkout", "purchase"]
    step_labels = {
        "view_item": "View Card",
        "add_to_cart": "Add to Cart",
        "begin_checkout": "Begin Checkout",
        "purchase": "Purchase",
    }

    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="totalUsers")],
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="eventName",
                in_list_filter=Filter.InListFilter(values=event_names),
            )
        ),
    )
    response = client.run_report(request)

    counts = {name: 0 for name in event_names}
    for row in response.rows:
        evt_name = row.dimension_values[0].value
        if evt_name in counts:
            counts[evt_name] = int(row.metric_values[0].value)

    results = []
    prev_count = None
    for name in event_names:
        count = counts[name]
        pct_of_previous = 100.0
        if prev_count is not None and prev_count > 0:
            pct_of_previous = round((count / prev_count) * 100, 1)
        results.append({
            "step": step_labels[name],
            "users": count,
            "pct_of_previous": pct_of_previous,
        })
        prev_count = count

    return results
