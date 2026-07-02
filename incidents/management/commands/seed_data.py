import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User
from incidents.models import IncidentSequence


def dev_email_for(username: str) -> str:
    inbox = os.getenv("DEV_EMAIL_INBOX", "").strip()
    if not inbox or "@" not in inbox:
        return f"{username}@kiira.local"
    local, domain = inbox.split("@", 1)
    tag = username.replace("_", "-")
    return f"{local}+{tag}@{domain}"


USERS = [
    ("admin", "Admin", "User", "System Administrator", Role.ADMIN, "dev-admin", "admin123"),
    ("worker1", "John", "Okello", "Production Operator", Role.WORKER, "dev-worker1", "demo123"),
    ("supervisor_tfa", "Mary", "Nabukeera", "Supervisor", Role.WORKER, "dev-supervisor-tfa", "demo123"),
    ("manager_tfa", "Peter", "Ssemwogerere", "Shop Floor Manager", Role.WORKER, "dev-manager-tfa", "demo123"),
    ("supervisor_body", "Alice", "Kato", "Supervisor", Role.WORKER, "dev-supervisor-body", "demo123"),
    ("manager_body", "David", "Mukasa", "Shop Floor Manager", Role.WORKER, "dev-manager-body", "demo123"),
    ("director", "James", "Opio", "Director of Production", Role.WORKER, "dev-director", "demo123"),
    ("ceo", "Sarah", "Achieng", "Chief Executive Officer", Role.CEO, "dev-ceo", "demo123"),
]


class Command(BaseCommand):
    help = "Seed demo users and incident sequence for local development (without Keycloak)."

    def handle(self, *args, **options):
        IncidentSequence.objects.get_or_create(year=timezone.localdate().year, defaults={"last_sequence": 0})

        for username, first, last, designation, role, keycloak_id, password in USERS:
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": dev_email_for(username),
                    "designation": designation,
                    "role": role,
                    "keycloak_id": keycloak_id,
                    "is_active": True,
                    "is_staff": role == Role.ADMIN,
                    "is_superuser": role == Role.ADMIN,
                },
            )
            if created or options.get("reset_passwords"):
                user.set_password(password)
                user.save()

        self.stdout.write(self.style.SUCCESS("Seeded demo users (passwords: admin123 / demo123)."))
        self.stdout.write("Use local login when KEYCLOAK_SERVER_URL is not set in .env.")
