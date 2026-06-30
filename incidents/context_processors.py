from incidents.permissions import queue_counts


def nav_counts(request):
    if not request.user.is_authenticated:
        return {}
    counts = queue_counts(request.user)
    alert = request.session.pop("show_queue_alert", None)
    if alert:
        counts["queue_alert"] = alert
    return {"nav_counts": counts}
