from django.contrib import admin
from .models import Block, TradeRequest, Message, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """The moderation queue -- newest first, unresolved surfaced by default
    via list_filter. Nothing here auto-actions anything; resolving a report
    is a manual decision (tick 'resolved', leave a note)."""
    list_display = ["id", "reporter", "reported_user", "reason", "resolved", "created_at"]
    list_filter = ["reason", "resolved"]
    search_fields = ["reporter__username", "reported_user__username", "details"]
    raw_id_fields = ["reporter", "reported_user", "message"]
    list_editable = ["resolved"]
    ordering = ["resolved", "-created_at"]


@admin.register(TradeRequest)
class TradeRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "from_user", "to_user", "wanted_product", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["from_user__username", "to_user__username"]
    raw_id_fields = ["from_user", "to_user", "wanted_product"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Read-only-in-practice audit trail (no add permission) -- useful when
    investigating a report, not meant for day-to-day browsing."""
    list_display = ["id", "sender", "recipient", "created_at", "read_at"]
    search_fields = ["sender__username", "recipient__username", "body"]
    raw_id_fields = ["sender", "recipient", "trade_request"]

    def has_add_permission(self, request):
        return False


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ["user", "blocked_user", "created_at"]
    search_fields = ["user__username", "blocked_user__username"]
    raw_id_fields = ["user", "blocked_user"]
