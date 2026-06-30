import os

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = "Send a test email to verify SMTP settings in .env"

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            nargs="?",
            help="Recipient email (defaults to EMAIL_HOST_USER)",
        )

    def handle(self, *args, **options):
        recipient = options["recipient"] or settings.EMAIL_HOST_USER
        if not recipient:
            self.stderr.write(
                self.style.ERROR(
                    "Provide a recipient address or set EMAIL_HOST_USER in .env"
                )
            )
            return

        backend = settings.EMAIL_BACKEND
        self.stdout.write(f"Backend: {backend}")
        self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"To: {recipient}")

        try:
            send_mail(
                subject="[KMC Incident] SMTP test",
                message=(
                    "If you received this message, email notifications are configured correctly.\n\n"
                    f"IRS base URL: {settings.IRS_BASE_URL}\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Failed to send: {exc}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient}"))
