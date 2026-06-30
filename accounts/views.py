from django.contrib.auth.views import LoginView

from incidents.permissions import queue_counts


class KmcLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        counts = queue_counts(self.request.user)
        if counts.get("queue_total"):
            self.request.session["show_queue_alert"] = counts["queue_total"]
        return response
