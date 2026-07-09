from django.test import TestCase

from accounts.models import Role
from incidents.templatetags.incident_extras import get_item
from incidents.tests.helpers import make_user


class AccountModelTests(TestCase):
    def test_user_string_and_access_flags(self):
        user = make_user("ceo", role=Role.CEO)
        self.assertIn("Ceo User", str(user))
        self.assertTrue(user.has_plant_wide_access())


class TemplateTagTests(TestCase):
    def test_get_item_filter(self):
        self.assertEqual(get_item({"a": 1}, "a"), 1)
