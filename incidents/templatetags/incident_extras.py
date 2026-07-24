from django import template

register = template.Library()

STATUS_LABELS = {
    "DRAFT": "Draft",
    "PENDING_VERIFICATION": "Pending verification",
    "PENDING_APPROVAL": "Pending approval",
    "RETURNED_TO_VERIFIER": "Bounced by approver",
    "RETURNED_TO_REPORTER": "Bounced by verifier",
    "CLOSED": "Closed",
}

DETAIL_STATUS_LABELS = {
    "DRAFT": "Draft",
    "PENDING_VERIFICATION": "Pending verification",
    "PENDING_APPROVAL": "Pending approval",
    "RETURNED_TO_VERIFIER": "Returned to verifier",
    "RETURNED_TO_REPORTER": "Returned to reporter",
    "CLOSED": "Closed",
}


@register.filter
def get_item(mapping, key):
    if hasattr(mapping, "__getitem__"):
        return mapping[key]
    return getattr(mapping, key, "")


@register.filter
def status_label(status):
    return STATUS_LABELS.get(status, status.replace("_", " ").title())


@register.filter
def status_label_detail(status):
    return DETAIL_STATUS_LABELS.get(status, status.replace("_", " ").title())


@register.filter
def incident_date_display(value):
    if not value:
        return "—"
    return value.strftime("%B %d, %Y")
