import os

from django.core.management.base import BaseCommand

from accounts.models import Role, User
from incidents.models import IncidentSequence, Location


def dev_email_for(username: str) -> str:
    """Map demo users to real inboxes when DEV_EMAIL_INBOX is set (Gmail +tags)."""
    inbox = os.getenv("DEV_EMAIL_INBOX", "").strip()
    if not inbox or "@" not in inbox:
        return f"{username}@kiira.local"
    local, domain = inbox.split("@", 1)
    tag = username.replace("_", "-")
    return f"{local}+{tag}@{domain}"


LOCATIONS = [
    ("TFA", "Trim and Final Assembly Line"),
    ("BODY", "Body Shop"),
    ("CHASSIS", "Chassis Line"),
    ("PAINT", "Paint Shop"),
    ("MACHINE", "Machine Shop"),
    ("QIT", "QIT (Quality, Inspection and Testing)"),
]

USERS = [
    ("admin", "Admin", "User", "System Administrator", Role.ADMIN, None, "admin123"),
    ("worker1", "John", "Okello", "Production Operator", Role.WORKER, None, "demo123"),
    ("supervisor_tfa", "Mary", "Nabukeera", "Supervisor", Role.SUPERVISOR, "TFA", "demo123"),
    ("manager_tfa", "Peter", "Ssemwogerere", "Shop Floor Manager", Role.SHOP_FLOOR_MANAGER, "TFA", "demo123"),
    ("supervisor_body", "Alice", "Kato", "Supervisor", Role.SUPERVISOR, "BODY", "demo123"),
    ("manager_body", "David", "Mukasa", "Shop Floor Manager", Role.SHOP_FLOOR_MANAGER, "BODY", "demo123"),
    ("director", "James", "Opio", "Director of Production", Role.DIRECTOR, None, "demo123"),
    ("ceo", "Sarah", "Achieng", "Chief Executive Officer", Role.CEO, None, "demo123"),
]


class Command(BaseCommand):
    help = "Seed locations, demo users, and incident sequence for local development."

    def handle(self, *args, **options):
        for code, name in LOCATIONS:
            Location.objects.update_or_create(code=code, defaults={"name": name, "is_active": True})
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(LOCATIONS)} locations."))

        from django.utils import timezone

        IncidentSequence.objects.get_or_create(year=timezone.localdate().year, defaults={"last_sequence": 0})

        for username, first, last, designation, role, loc_code, password in USERS:
            loc = Location.objects.filter(code=loc_code).first() if loc_code else None
            user, created = User.objects.update_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": dev_email_for(username),
                    "designation": designation,
                    "role": role,
                    "assigned_location": loc,
                    "is_active": True,
                    "is_staff": role == Role.ADMIN,
                    "is_superuser": role == Role.ADMIN,
                },
            )
            if created or options.get("reset_passwords"):
                user.set_password(password)
                user.save()
        self.stdout.write(self.style.SUCCESS("Seeded demo users (passwords: admin123 / demo123)."))
        inbox = os.getenv("DEV_EMAIL_INBOX", "").strip()
        if inbox:
            self.stdout.write(f"User emails use plus-tags on {inbox} (e.g. {dev_email_for('supervisor_tfa')}).")
        else:
            self.stdout.write("Set DEV_EMAIL_INBOX in .env and re-run seed_data to assign real dev email addresses.")
        self.stdout.write("Login as worker1, supervisor_tfa, manager_tfa, director, ceo, or admin.")
