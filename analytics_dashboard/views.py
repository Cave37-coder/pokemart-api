# analytics_dashboard/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from . import services


@api_view(["GET"])
@permission_classes([IsAdminUser])
def dashboard_summary(request):
    """
    Single endpoint powering the whole dashboard page: daily visits,
    conversion summary, and funnel drop-off, all for the same period.
    Query param: ?days=30 (default 30)
    """
    days = int(request.GET.get("days", 30))

    data = {
        "daily_visits": services.get_daily_visits(days=days),
        "conversion": services.get_conversion_summary(days=days),
        "funnel": services.get_funnel(days=days),
    }
    return Response(data)
