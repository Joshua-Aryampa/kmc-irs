from accounts.models import Role
from incidents.models import Incident, IncidentStatus


def incidents_for_user(user):
    if user.role in {Role.DIRECTOR, Role.CEO, Role.ADMIN}:
        return Incident.objects.all()
    if user.role in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER}:
        return Incident.objects.filter(scene_location=user.assigned_location)
    return Incident.objects.filter(reporter=user)


def user_can_view_incident(user, incident):
    if user.id in {incident.reporter_id, incident.verifier_id, incident.approver_id}:
        return True
    if user.role in {Role.DIRECTOR, Role.CEO, Role.ADMIN}:
        return True
    if user.role in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER}:
        return incident.scene_location_id == user.assigned_location_id
    return incident.reporter_id == user.id


def queue_visibility(user):
    role = user.role
    if role == Role.WORKER:
        return {"verify": False, "approve": False, "forward": False, "returned": True}
    if role == Role.SUPERVISOR:
        return {"verify": True, "approve": False, "forward": True, "returned": True}
    if role == Role.SHOP_FLOOR_MANAGER:
        return {"verify": True, "approve": True, "forward": True, "returned": True}
    if role == Role.DIRECTOR:
        return {"verify": True, "approve": True, "forward": True, "returned": False}
    if role == Role.CEO:
        return {"verify": False, "approve": True, "forward": False, "returned": False}
    return {"verify": True, "approve": True, "forward": True, "returned": True}


def queue_counts(user):
    counts = {
        "queue_verify": Incident.objects.filter(
            verifier=user, status=IncidentStatus.PENDING_VERIFICATION
        ).count(),
        "queue_approve": Incident.objects.filter(
            approver=user, status=IncidentStatus.PENDING_APPROVAL
        ).count(),
        "queue_forward": Incident.objects.filter(
            verifier=user, status=IncidentStatus.RETURNED_TO_VERIFIER
        ).count(),
        "queue_returned": Incident.objects.filter(
            reporter=user, status=IncidentStatus.RETURNED_TO_REPORTER
        ).count(),
    }
    visibility = queue_visibility(user)
    counts["queue_total"] = sum(
        counts[key]
        for key, visible in (
            ("queue_verify", visibility["verify"]),
            ("queue_approve", visibility["approve"]),
            ("queue_forward", visibility["forward"]),
            ("queue_returned", visibility["returned"]),
        )
        if visible
    )
    return counts
