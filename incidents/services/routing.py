from django.db import transaction
from django.utils import timezone

from incidents.models import IncidentSequence


class RoutingError(Exception):
    pass


def validate_three_different_people(reporter, verifier, approver=None):
    ids = [reporter.id, verifier.id]
    if approver is not None:
        ids.append(approver.id)
    if len(set(ids)) != len(ids):
        raise RoutingError("Reporter, verifier, and approver must be three different people.")


@transaction.atomic
def generate_incident_id(submission_dt=None) -> str:
    submission_dt = submission_dt or timezone.localtime()
    period = f"{submission_dt.year:04d}{submission_dt.month:02d}"
    seq_row, _ = IncidentSequence.objects.select_for_update().get_or_create(
        period=period, defaults={"last_sequence": 0}
    )
    seq_row.last_sequence += 1
    if seq_row.last_sequence > 999:
        raise RoutingError(
            f"Monthly incident sequence limit reached for {submission_dt:%B %Y} (max 999)."
        )
    seq_row.save(update_fields=["last_sequence"])
    mm = f"{submission_dt.month:02d}"
    yy = f"{submission_dt.year % 100:02d}"
    seq = str(seq_row.last_sequence).zfill(3)
    return f"{mm}{yy}{seq}"
