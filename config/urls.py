from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from mozilla_django_oidc.views import OIDCAuthenticationRequestView, OIDCLogoutView

from accounts.views import KmcOIDCAuthenticationCallbackView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("oidc/authenticate/", OIDCAuthenticationRequestView.as_view(), name="oidc_authentication_init"),
    path("oidc/callback/", KmcOIDCAuthenticationCallbackView.as_view(), name="oidc_authentication_callback"),
    path("oidc/logout/", OIDCLogoutView.as_view(), name="oidc_logout"),
    path("", include("incidents.urls")),
    path("accounts/", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
