from django.contrib import admin

from .models import Incident, Location, NotificationLog, TimelineEntry


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")


class WitnessInline(admin.TabularInline):
    from .models import Witness

    model = Witness
    extra = 0


class PhotoInline(admin.TabularInline):
    from .models import IncidentPhoto

    model = IncidentPhoto
    extra = 0
    readonly_fields = ("original_filename", "file_size_bytes")


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("incident_id", "status", "scene_location", "reporter", "submitted_at")
    list_filter = ("status", "scene_location", "severity", "is_late_submission")
    search_fields = ("incident_id", "reporter__username")
    inlines = [WitnessInline, PhotoInline]


@admin.register(TimelineEntry)
class TimelineEntryAdmin(admin.ModelAdmin):
    list_display = ("incident", "entry_type", "actor", "created_at")
    readonly_fields = ("created_at",)


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("incident", "notification_type", "recipient_email", "status", "created_at")
