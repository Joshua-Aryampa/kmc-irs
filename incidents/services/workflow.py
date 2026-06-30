from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Role
from incidents.models import Incident, IncidentStatus, TimelineEntry, TimelineEntryType
from incidents.services.notifications import (
    notify_approver,
    notify_closed,
    notify_reporter_returned,
    notify_submitted,
    notify_verifier_rejected_by_approver,
)
from incidents.services.routing import RoutingError, generate_incident_id, resolve_verifier_approver


class WorkflowError(Exception):
    pass


def _log(incident, entry_type, actor, message="", metadata=None):
    TimelineEntry.objects.create(
        incident=incident,
        entry_type=entry_type,
        actor=actor,
        actor_role=actor.role if actor else "",
        message=message,
        metadata=metadata or {},
    )


def _incident_datetime(incident_date, incident_time):
    if not incident_date or not incident_time:
        return None
    return timezone.make_aware(
        datetime.combine(incident_date, incident_time),
        timezone.get_current_timezone(),
    )


def is_late_at_submission(incident_date, incident_time, submitted_at=None):
    submitted_at = submitted_at or timezone.localtime()
    incident_dt = _incident_datetime(incident_date, incident_time)
    if not incident_dt:
        return False
    return submitted_at > incident_dt + timedelta(minutes=settings.INCIDENT_LATE_MINUTES)


def compute_late(incident, submitted_at=None):
    return is_late_at_submission(incident.incident_date, incident.incident_time, submitted_at)


@transaction.atomic
def submit_incident(incident: Incident, actor):
    if incident.reporter_id != actor.id:
        raise WorkflowError("Only the reporter can submit.")
    if incident.status not in {IncidentStatus.DRAFT, IncidentStatus.RETURNED_TO_REPORTER}:
        raise WorkflowError("Incident cannot be submitted in its current status.")

    submitted_at = timezone.localtime()
    incident.is_late_submission = compute_late(incident, submitted_at)
    if incident.is_late_submission and not incident.late_reason.strip():
        raise WorkflowError("Reason for delay is required for late submissions.")

    if not incident.incident_id:
        incident.incident_id = generate_incident_id(submitted_at)
    incident.submitted_at = submitted_at

    try:
        verifier, approver = resolve_verifier_approver(actor, incident.scene_location_id)
    except RoutingError as exc:
        raise WorkflowError(str(exc)) from exc

    incident.verifier = verifier
    incident.approver = approver
    incident.status = IncidentStatus.PENDING_VERIFICATION
    incident.return_comment = ""
    incident.pending_approver_comment = ""
    incident.severity = ""
    incident.reporter_confirmed_at = submitted_at
    incident.save()

    meta = {"is_late": incident.is_late_submission}
    _log(incident, TimelineEntryType.SUBMITTED, actor, metadata=meta)
    if incident.is_late_submission:
        _log(incident, TimelineEntryType.LATE_FLAGGED, actor, message=incident.late_reason)
    notify_submitted(incident)
    return incident


@transaction.atomic
def verify_incident(incident: Incident, actor, severity: str):
    if incident.verifier_id != actor.id:
        raise WorkflowError("You are not the assigned verifier.")
    if incident.status != IncidentStatus.PENDING_VERIFICATION:
        raise WorkflowError("Incident is not pending verification.")
    if not severity:
        raise WorkflowError("Severity must be assigned before verification.")

    now = timezone.localtime()
    incident.severity = severity
    incident.status = IncidentStatus.PENDING_APPROVAL
    incident.verifier_confirmed_at = now
    incident.save()
    _log(incident, TimelineEntryType.VERIFIED, actor)
    notify_approver(incident)
    return incident


@transaction.atomic
def reject_verification(incident: Incident, actor, comment: str):
    if incident.verifier_id != actor.id:
        raise WorkflowError("You are not the assigned verifier.")
    if incident.status != IncidentStatus.PENDING_VERIFICATION:
        raise WorkflowError("Incident is not pending verification.")
    if not comment.strip():
        raise WorkflowError("Comment is required when rejecting.")

    incident.status = IncidentStatus.RETURNED_TO_REPORTER
    incident.return_comment = comment.strip()
    incident.save()
    _log(incident, TimelineEntryType.VERIFICATION_REJECTED, actor, message=comment.strip())
    notify_reporter_returned(incident)
    return incident


@transaction.atomic
def approve_incident(incident: Incident, actor):
    if incident.approver_id != actor.id:
        raise WorkflowError("You are not the assigned approver.")
    if incident.status != IncidentStatus.PENDING_APPROVAL:
        raise WorkflowError("Incident is not pending approval.")

    now = timezone.localtime()
    incident.status = IncidentStatus.CLOSED
    incident.approver_confirmed_at = now
    incident.closed_at = now
    incident.save()
    _log(incident, TimelineEntryType.APPROVED, actor)
    notify_closed(incident)
    return incident


@transaction.atomic
def reject_approval(incident: Incident, actor, comment: str):
    if incident.approver_id != actor.id:
        raise WorkflowError("You are not the assigned approver.")
    if incident.status != IncidentStatus.PENDING_APPROVAL:
        raise WorkflowError("Incident is not pending approval.")
    if not comment.strip():
        raise WorkflowError("Comment is required when rejecting.")

    incident.status = IncidentStatus.RETURNED_TO_VERIFIER
    incident.pending_approver_comment = comment.strip()
    incident.save()
    _log(incident, TimelineEntryType.APPROVAL_REJECTED, actor, message=comment.strip())
    notify_verifier_rejected_by_approver(incident)
    return incident


@transaction.atomic
def forward_to_reporter(incident: Incident, actor, comment: str):
    if incident.verifier_id != actor.id:
        raise WorkflowError("You are not the assigned verifier.")
    if incident.status != IncidentStatus.RETURNED_TO_VERIFIER:
        raise WorkflowError("Incident is not awaiting verifier forward.")
    if not comment.strip():
        raise WorkflowError("Comment is required when returning to reporter.")

    incident.status = IncidentStatus.RETURNED_TO_REPORTER
    incident.return_comment = comment.strip()
    incident.save()
    _log(incident, TimelineEntryType.RETURNED_TO_REPORTER, actor, message=comment.strip())
    notify_reporter_returned(incident)
    return incident


@transaction.atomic
def add_comment(incident: Incident, actor, comment: str):
    if not comment.strip():
        raise WorkflowError("Comment cannot be empty.")
    if actor.id not in {incident.verifier_id, incident.approver_id}:
        raise WorkflowError("Only assigned verifier or approver can comment.")
    _log(incident, TimelineEntryType.COMMENT, actor, message=comment.strip())
    return incident


@transaction.atomic
def reassign(incident: Incident, admin, role_kind: str, new_user, reason: str):
    if admin.role != Role.ADMIN:
        raise WorkflowError("Only Admin can reassign.")
    if incident.is_closed:
        raise WorkflowError("Closed incidents cannot be reassigned.")
    if not reason.strip():
        raise WorkflowError("Reason is required for reassignment.")

    if role_kind == "verifier":
        if new_user.role != incident.verifier.role:
            raise WorkflowError("Replacement must have the same role as the current verifier.")
        if incident.verifier.assigned_location_id and new_user.assigned_location_id != incident.verifier.assigned_location_id:
            raise WorkflowError("Replacement supervisor/manager must be at the same location.")
        old_id = incident.verifier_id
        incident.verifier = new_user
        incident.save(update_fields=["verifier", "updated_at"])
        _log(
            incident,
            TimelineEntryType.REASSIGNED_VERIFIER,
            admin,
            message=reason.strip(),
            metadata={"old_id": old_id, "new_id": new_user.id},
        )
    elif role_kind == "approver":
        if new_user.role != incident.approver.role:
            raise WorkflowError("Replacement must have the same role as the current approver.")
        old_id = incident.approver_id
        incident.approver = new_user
        incident.save(update_fields=["approver", "updated_at"])
        _log(
            incident,
            TimelineEntryType.REASSIGNED_APPROVER,
            admin,
            message=reason.strip(),
            metadata={"old_id": old_id, "new_id": new_user.id},
        )
    else:
        raise WorkflowError("Invalid reassignment role.")
    return incident
