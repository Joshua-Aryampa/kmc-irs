import csv

from django.http import HttpResponse


def incidents_csv(queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="incidents_export.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Incident ID",
            "Status",
            "Location",
            "Incident Date",
            "Incident Time",
            "Severity",
            "Reporter",
            "Verifier",
            "Approver",
            "Submitted At",
            "Late",
            "Closed At",
        ]
    )
    for inc in queryset.select_related("reporter", "verifier", "approver"):
        writer.writerow(
            [
                inc.incident_id,
                inc.get_status_display(),
                inc.scene_location,
                inc.incident_date,
                inc.incident_time,
                inc.get_severity_display(),
                inc.reporter.full_name,
                inc.verifier.full_name if inc.verifier_id else "",
                inc.approver.full_name if inc.approver_id else "",
                inc.submitted_at,
                inc.is_late_submission,
                inc.closed_at,
            ]
        )
    return response
