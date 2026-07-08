from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count

from incidents.models import IncidentStatus


def paginate_queryset(request, queryset, page_param="page", per_page=None):
    per_page = per_page or settings.INCIDENT_LIST_PAGE_SIZE
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param) or 1
    return paginator.get_page(page_number)


def filter_form_values(params):
    return {
        "status": params.get("status", ""),
        "severity": params.get("severity", ""),
        "date_from": params.get("date_from", ""),
        "date_to": params.get("date_to", ""),
        "late": params.get("late", ""),
    }


def apply_incident_filters(qs, params):
    status = params.get("status")
    severity = params.get("severity")
    late = params.get("late")
    date_from = params.get("date_from")
    date_to = params.get("date_to")

    if status:
        qs = qs.filter(status=status)
    if severity:
        qs = qs.filter(severity=severity)
    if late == "1":
        qs = qs.filter(is_late_submission=True)
    if date_from:
        qs = qs.filter(incident_date__gte=date_from)
    if date_to:
        qs = qs.filter(incident_date__lte=date_to)
    return qs


def incident_summary(qs):
    return {
        "open": qs.exclude(status=IncidentStatus.CLOSED).count(),
        "closed": qs.filter(status=IncidentStatus.CLOSED).count(),
        "pending_verification": qs.filter(status=IncidentStatus.PENDING_VERIFICATION).count(),
        "pending_approval": qs.filter(status=IncidentStatus.PENDING_APPROVAL).count(),
        "late": qs.filter(is_late_submission=True).count(),
    }


def incidents_by_location(qs):
    return (
        qs.exclude(scene_location="")
        .values("scene_location")
        .annotate(c=Count("id"))
        .order_by("scene_location")
    )
