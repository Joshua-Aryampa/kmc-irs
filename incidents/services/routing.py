from django.conf import settings
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
