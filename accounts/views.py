from django.conf import settings
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

from incidents.permissions import queue_counts


class KmcLoginView(LoginView):
    template_name = "accounts/login.html"

    def dispatch(self, request, *args, **kwargs):
        if settings.KEYCLOAK_SERVER_URL and not request.user.is_authenticated:
            return redirect("oidc_authentication_init")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["keycloak_enabled"] = bool(settings.KEYCLOAK_SERVER_URL)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        counts = queue_counts(self.request.user)
        if counts.get("queue_total"):
            self.request.session["show_queue_alert"] = counts["queue_total"]
        return response


class KmcOIDCAuthenticationCallbackView(OIDCAuthenticationCallbackView):
    def login_success(self):
        response = super().login_success()
        counts = queue_counts(self.request.user)
        if counts.get("queue_total"):
            self.request.session["show_queue_alert"] = counts["queue_total"]
        return response
