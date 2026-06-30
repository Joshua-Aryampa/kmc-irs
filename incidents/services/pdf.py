import base64
from io import BytesIO
from pathlib import Path

from django.template.loader import render_to_string
from xhtml2pdf import pisa


def _photo_data_uri(photo):
    try:
        path = Path(photo.image.path)
    except (ValueError, AttributeError):
        return ""
    if not path.is_file():
        return ""
    mime = photo.mime_type or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


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
        },
    )
    result = BytesIO()
    pisa.CreatePDF(html, dest=result, encoding="UTF-8")
    return result.getvalue()
