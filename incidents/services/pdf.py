import base64
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from incidents.classifications import INVOLVE_GROUPS


FORM_REFERENCE = settings.INCIDENT_FORM_REFERENCE


def _file_data_uri(path, mime="image/png"):
    try:
        file_path = Path(path)
    except (TypeError, ValueError):
        return ""
    if not file_path.is_file():
        return ""
    encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _photo_data_uri(photo):
    try:
        path = Path(photo.image.path)
    except (ValueError, AttributeError):
        return ""
    if not path.is_file():
        return ""
    mime = photo.mime_type or "image/jpeg"
    return _file_data_uri(path, mime)


def _signatory_payload(image_field, person, confirmed_at):
    if not person:
        return None
    payload = {
        "name": person.full_name,
        "designation": person.designation,
        "image_url": "",
        "pending_label": "—",
        "confirmed": bool(confirmed_at),
    }
    if not confirmed_at:
        if person:
            payload["pending_label"] = "Pending"
        return payload
    if image_field:
        try:
            payload["image_url"] = _file_data_uri(image_field.path)
            return payload
        except (ValueError, AttributeError):
            pass
    return payload



def _involve_classification_groups(incident):
    groups = []
    for key in ("person", "product", "premises", "property"):
        group = INVOLVE_GROUPS[key]
        if not getattr(incident, group["field"]):
            continue
        classifications = []
        for field_name, label in group["classifications"]:
            if getattr(incident, field_name):
                classifications.append(label)
        if getattr(incident, group["other_bool"]):
            text = (getattr(incident, group["other_text"]) or "").strip()
            classifications.append(f"Other ({text})" if text else "Other")
        groups.append({"label": group["label"], "classifications": classifications})
    return groups



def _gallery_rows(photos, columns=2):
    if not photos:
        return [[None, None], [None, None]]
    rows = []
    for index in range(0, len(photos), columns):
        row = list(photos[index : index + columns])
        while len(row) < columns:
            row.append(None)
        rows.append(row)
    return rows


def render_incident_pdf(request, incident):
    photos = []
    for photo in incident.photos.all():
        photos.append({"obj": photo, "file_url": _photo_data_uri(photo)})
    html = render_to_string(
        "incidents/pdf/incident_report.html",
        {
            "incident": incident,
            "timeline": incident.timeline_entries.select_related("actor"),
            "photos": photos,
            "gallery_rows": _gallery_rows(photos),
            "branding_url": _file_data_uri(
                settings.BASE_DIR / "static" / "img" / "kmc-pdf-branding.png"
            ),
            "form_reference": FORM_REFERENCE,
            "involve_groups": _involve_classification_groups(incident),
            "reporter_sign": _signatory_payload(
                incident.reporter_signature, incident.reporter, incident.reporter_confirmed_at
            ),
            "verifier_sign": _signatory_payload(
                incident.verifier_signature, incident.verifier, incident.verifier_confirmed_at
            ),
            "approver_sign": _signatory_payload(
                incident.approver_signature, incident.approver, incident.approver_confirmed_at
            ),
        },
    )
    result = BytesIO()
    pisa.CreatePDF(html, dest=result, encoding="UTF-8")
    return result.getvalue()
