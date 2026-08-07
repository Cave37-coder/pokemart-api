from django.urls import path
from . import views

urlpatterns = [
    path("profile/<int:user_id>/", views.public_profile, name="community-public-profile"),
    path("browse/", views.community_browse, name="community-browse"),
    path("most-wanted/", views.most_wanted, name="community-most-wanted"),

    path("conversations/", views.conversations_list, name="community-conversations"),
    path("conversations/<int:user_id>/", views.conversation_thread, name="community-conversation-thread"),
    path("messages/send/", views.send_message, name="community-send-message"),

    path("trade-requests/", views.trade_requests_list, name="community-trade-requests"),
    path("trade-requests/create/", views.trade_request_create, name="community-trade-request-create"),
    path("trade-requests/<int:trade_id>/respond/", views.trade_request_respond, name="community-trade-request-respond"),

    path("block/", views.block_user, name="community-block"),
    path("unblock/", views.unblock_user, name="community-unblock"),
    path("report/", views.report_user, name="community-report"),
]
