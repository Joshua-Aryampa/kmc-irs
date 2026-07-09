from django.db.models import Q

from incidents.models import Incident, IncidentStatus


def _visible_incidents_for_user(user):
    if user.has_plant_wide_access():
        queryset = Incident.objects.all()
    else:
        queryset = Incident.objects.filter(
            Q(reporter=user) | Q(verifier=user) | Q(approver=user)
        )
    return queryset.filter(
        ~Q(status=IncidentStatus.DRAFT) | Q(reporter=user, status=IncidentStatus.DRAFT)
    )


def incidents_for_user(user):
    return _visible_incidents_for_user(user)


def user_can_view_incident(user, incident):
    if incident.status == IncidentStatus.DRAFT and incident.reporter_id != user.id:
        return False
    if user.id in {incident.reporter_id, incident.verifier_id, incident.approver_id}:
        return True
    return user.has_plant_wide_access()


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
    counts["queue_total"] = sum(counts.values())
    return counts
