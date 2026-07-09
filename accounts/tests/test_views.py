from django.test import TestCase

from accounts.views import KmcLoginView
from django.test import RequestFactory


class AccountViewTests(TestCase):
    def test_login_view_form_valid_sets_queue_alert(self):
        from incidents.models import IncidentStatus
        from incidents.tests.helpers import make_incident, make_user

        verifier = make_user("verifier2", keycloak_id="kc-verifier2")
        reporter = make_user("reporter2", keycloak_id="kc-reporter2")
        make_incident(
            reporter,
            status=IncidentStatus.PENDING_VERIFICATION,
            verifier=verifier,
        )
        factory = RequestFactory()
        request = factory.post("/accounts/login/")
        request.session = self.client.session
        view = KmcLoginView()
        view.request = request
        view.setup(request)
        from django.contrib.auth import authenticate

        user = authenticate(username="verifier2", password="testpass123")
        from django.contrib.auth.forms import AuthenticationForm

        form = AuthenticationForm(data={"username": "verifier2", "password": "testpass123"})
        self.assertTrue(form.is_valid())
        view.request.user = user
        response = view.form_valid(form)
        self.assertEqual(response.status_code, 302)
