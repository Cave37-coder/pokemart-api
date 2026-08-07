from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from products.admin import ProductAutocompleteJsonView
from orders.pos_auth import pos_csrf_view, pos_login_view, pos_logout_view, pos_whoami_view
from analytics_dashboard.dashboard_view import dashboard_page

urlpatterns = [
    # Must come BEFORE path("admin/", admin.site.urls) below -- Django's
    # URL resolver matches in order, and admin.site.urls registers its own
    # /admin/autocomplete/ internally. Listing ours first means our version
    # wins the match, intercepting the one global autocomplete endpoint
    # shared by every autocomplete field in the whole admin site.
    path("admin/autocomplete/", ProductAutocompleteJsonView.as_view(admin_site=admin.site), name="admin-autocomplete-override"),
    # Staff-only analytics dashboard (session auth via staff_member_required,
    # same pattern as manage_set_view.py) -- must also come before
    # path("admin/", ...) for the same reason as autocomplete above.
    path("admin/analytics-dashboard/", dashboard_page, name="analytics-dashboard-page"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/auth/", include("users.urls")),
    path("api/", include("products.urls")),
    path("api/", include("orders.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/analytics/", include("analytics_dashboard.urls")),
    path("api/community/", include("community.urls")),
    path("api/", include("accessories.urls")),

    # Standalone POS (pos.pokebulk.co.za) auth endpoints -- see
    # orders/pos_auth.py. These let the POS app log in using the same
    # staff session that already protects everything under /admin/,
    # including the existing manual-invoice pos/search/ and pos/save/
    # endpoints, which are used as-is and needed no changes.
    path("api/pos-auth/csrf/", pos_csrf_view, name="pos-auth-csrf"),
    path("api/pos-auth/login/", pos_login_view, name="pos-auth-login"),
    path("api/pos-auth/logout/", pos_logout_view, name="pos-auth-logout"),
    path("api/pos-auth/whoami/", pos_whoami_view, name="pos-auth-whoami"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
