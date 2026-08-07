from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend

from .models import Accessory
from .serializers import AccessorySerializer


class AccessoryViewSet(viewsets.ModelViewSet):
    """Public-facing catalog is ALWAYS filtered to is_active + in-stock --
    "customers only see what is in Stock" (Michael, 2026-08-07), a
    deliberately stricter rule than cards (which stay visible out-of-stock,
    just greyed out). Staff get full unrestricted visibility/editing through
    Django admin instead (accessories/admin.py), not through this API --
    keeps "what customers can see" and "what Michael can manage" as two
    clearly separate surfaces rather than one endpoint with conditional
    logic that's easy to get wrong."""
    serializer_class = AccessorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category"]
    search_fields = ["name", "manufacturer", "description"]
    ordering_fields = ["price", "created_at", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Accessory.objects.filter(is_active=True, stock__gt=0)

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]
