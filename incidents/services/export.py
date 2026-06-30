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
            "Submitted At",
            "Late",
            "Closed At",
        ]
    )
    for inc in queryset.select_related("scene_location", "reporter"):
        writer.writerow(
            [
                inc.incident_id,
                inc.get_status_display(),
                inc.scene_location,
                inc.incident_date,
                inc.incident_time,
                inc.get_severity_display(),
                inc.reporter.full_name,
                inc.submitted_at,
                inc.is_late_submission,
                inc.closed_at,
            ]
        )
    return response
