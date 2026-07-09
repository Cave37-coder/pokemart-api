from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from products.admin import ProductAutocompleteJsonView

urlpatterns = [
    # Must come BEFORE path("admin/", admin.site.urls) below -- Django's
    # URL resolver matches in order, and admin.site.urls registers its own
    # /admin/autocomplete/ internally. Listing ours first means our version
    # wins the match, intercepting the one global autocomplete endpoint
    # shared by every autocomplete field in the whole admin site.
    path("admin/autocomplete/", ProductAutocompleteJsonView.as_view(admin_site=admin.site), name="admin-autocomplete-override"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/auth/", include("users.urls")),
    path("api/", include("products.urls")),
    path("api/", include("orders.urls")),
    path("api/payments/", include("payments.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
