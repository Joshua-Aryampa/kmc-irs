from pathlib import Path

from django.conf import settings

from incidents.permissions import queue_counts


def nav_counts(request):
    if not request.user.is_authenticated:
        return {}
    counts = queue_counts(request.user)
    alert = request.session.pop("show_queue_alert", None)
    if alert:
        counts["queue_alert"] = alert
    return {"nav_counts": counts}


def static_version(request):
    css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    try:
        version = int(css_path.stat().st_mtime)
    except OSError:
        version = 1
    return {"static_version": version}
