from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from incidents.models import IncidentSequence


class RoutingError(Exception):
    pass


def resolve_verifier_approver(reporter: User, scene_location_id: int) -> tuple[User, User]:
    from incidents.models import Location

    location = Location.objects.get(pk=scene_location_id)

    if reporter.role == Role.WORKER:
        verifier = _one_user(
            Role.SUPERVISOR,
            assigned_location=location,
            label=f"Supervisor for {location.name}",
        )
        approver = _one_user(
            Role.SHOP_FLOOR_MANAGER,
            assigned_location=location,
            label=f"Shop Floor Manager for {location.name}",
        )
    elif reporter.role == Role.SUPERVISOR:
        verifier = _one_user(
            Role.SHOP_FLOOR_MANAGER,
            assigned_location=location,
            label=f"Shop Floor Manager for {location.name}",
        )
        approver = _one_user(Role.DIRECTOR, label="Director of Production")
    elif reporter.role == Role.SHOP_FLOOR_MANAGER:
        verifier = _one_user(Role.DIRECTOR, label="Director of Production")
        approver = _one_user(Role.CEO, label="CEO")
    else:
        raise RoutingError("This role cannot report incidents.")

    _validate_role_separation(reporter, verifier, approver)
    return verifier, approver


def _one_user(role, assigned_location=None, label=""):
    qs = User.objects.filter(is_active=True, role=role)
    if assigned_location is not None:
        qs = qs.filter(assigned_location=assigned_location)
    user = qs.first()
    if not user:
        raise RoutingError(f"No active {label or role} is configured. Contact IT Admin.")
    return user


def _validate_role_separation(reporter, verifier, approver):
    ids = [reporter.id, verifier.id, approver.id]
    if len(set(ids)) != 3:
        raise RoutingError(
            "Cannot route this incident: reporter, verifier, and approver must be three different people. "
            "Contact IT Admin to adjust user assignments."
        )


@transaction.atomic
def generate_incident_id(submission_dt=None) -> str:
    submission_dt = submission_dt or timezone.localtime()
    year = submission_dt.year
    seq_row, _ = IncidentSequence.objects.select_for_update().get_or_create(
        year=year, defaults={"last_sequence": 0}
    )
    seq_row.last_sequence += 1
    seq_row.save(update_fields=["last_sequence"])
    seq = str(seq_row.last_sequence).zfill(5)
    mm = f"{submission_dt.month:02d}"
    dd = f"{submission_dt.day:02d}"
    yyyy = submission_dt.year
    return f"{settings.INCIDENT_ID_PREFIX}{mm}/{dd}-{yyyy}-{seq}"


def eligible_reassignments(incident, role_kind: str):
    """role_kind: verifier or approver"""
    from incidents.models import Incident

    inc: Incident = incident
    if role_kind == "verifier":
        current = inc.verifier
        if current.role == Role.SUPERVISOR:
            qs = User.objects.filter(
                is_active=True, role=Role.SUPERVISOR, assigned_location=inc.scene_location
            )
        elif current.role == Role.SHOP_FLOOR_MANAGER:
            qs = User.objects.filter(
                is_active=True,
                role=Role.SHOP_FLOOR_MANAGER,
                assigned_location=inc.scene_location,
            )
        elif current.role == Role.DIRECTOR:
            qs = User.objects.filter(is_active=True, role=Role.DIRECTOR)
        else:
            qs = User.objects.none()
    else:
        current = inc.approver
        if current.role == Role.SHOP_FLOOR_MANAGER:
            qs = User.objects.filter(
                is_active=True,
                role=Role.SHOP_FLOOR_MANAGER,
                assigned_location=inc.scene_location,
            )
        elif current.role == Role.DIRECTOR:
            qs = User.objects.filter(is_active=True, role=Role.DIRECTOR)
        elif current.role == Role.CEO:
            qs = User.objects.filter(is_active=True, role=Role.CEO)
        else:
            qs = User.objects.none()

    excluded = {inc.reporter_id}
    if inc.verifier_id:
        excluded.add(inc.verifier_id)
    if inc.approver_id:
        excluded.add(inc.approver_id)
    return qs.exclude(pk__in=excluded)
