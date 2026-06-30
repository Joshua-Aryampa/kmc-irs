from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from incidents.models import NotificationLog


def _send(incident, recipient, notification_type, subject, body):
    if not recipient or not recipient.email:
        return
    log = NotificationLog.objects.create(
        incident=incident,
        recipient_email=recipient.email,
        notification_type=notification_type,
        status="PENDING",
    )
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient.email],
            fail_silently=False,
        )
        log.status = "SENT"
        log.sent_at = timezone.now()
        log.save(update_fields=["status", "sent_at"])
    except Exception as exc:
        log.status = "FAILED"
        log.error_message = str(exc)
        log.save(update_fields=["status", "error_message"])


def _link(incident):
    return f"{settings.IRS_BASE_URL}/incidents/{incident.pk}/"


def notify_submitted(incident):
    subject = f"[KMC Incident] Verification required: {incident.incident_id}"
    body = (
        f"A new incident requires your verification.\n\n"
        f"Incident ID: {incident.incident_id}\n"
        f"Location: {incident.scene_location}\n"
        f"Reporter: {incident.reporter.full_name}\n\n"
        f"View incident: {_link(incident)}"
    )
    _send(incident, incident.verifier, "SUBMITTED", subject, body)


def notify_reporter_returned(incident):
    subject = f"[KMC Incident] Report returned: {incident.incident_id}"
    body = (
        f"Your incident report was returned for correction.\n\n"
        f"Comment: {incident.return_comment}\n\n"
        f"Edit report: {_link(incident)}"
    )
    _send(incident, incident.reporter, "VERIFICATION_REJECTED", subject, body)


def notify_approver(incident):
    subject = f"[KMC Incident] Approval required: {incident.incident_id}"
    body = (
        f"Incident {incident.incident_id} has been verified and requires your approval.\n\n"
        f"View incident: {_link(incident)}"
    )
    _send(incident, incident.approver, "VERIFIED", subject, body)


def notify_verifier_rejected_by_approver(incident):
    subject = f"[KMC Incident] Approval rejected — action required: {incident.incident_id}"
    body = (
        f"Approver rejected incident {incident.incident_id}.\n\n"
        f"Comment: {incident.pending_approver_comment}\n\n"
        f"View incident: {_link(incident)}"
    )
    _send(incident, incident.verifier, "APPROVAL_REJECTED", subject, body)


def notify_closed(incident):
    subject = f"[KMC Incident] Incident closed: {incident.incident_id}"
    body = (
        f"Incident {incident.incident_id} has been approved and closed.\n\n"
        f"View incident: {_link(incident)}"
    )
    for recipient in {incident.reporter, incident.verifier}:
        _send(incident, recipient, "CLOSED", subject, body)
