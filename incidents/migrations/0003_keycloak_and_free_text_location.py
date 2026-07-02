from django.db import migrations, models


def copy_location_names(apps, schema_editor):
    Incident = apps.get_model("incidents", "Incident")
    Location = apps.get_model("incidents", "Location")
    for incident in Incident.objects.exclude(scene_location_id__isnull=True).iterator():
        location = Location.objects.filter(pk=incident.scene_location_id).first()
        if location:
            incident.scene_location_text = location.name[:70]
            incident.save(update_fields=["scene_location_text"])


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0002_incident_other_person_incident_other_person_text_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="scene_location_text",
            field=models.CharField(blank=True, max_length=70),
        ),
        migrations.RunPython(copy_location_names, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="incident",
            name="scene_location",
        ),
        migrations.RenameField(
            model_name="incident",
            old_name="scene_location_text",
            new_name="scene_location",
        ),
        migrations.AddField(
            model_name="incident",
            name="approver_signature",
            field=models.ImageField(blank=True, null=True, upload_to="signatures/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="incident",
            name="reporter_signature",
            field=models.ImageField(blank=True, null=True, upload_to="signatures/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="incident",
            name="verifier_signature",
            field=models.ImageField(blank=True, null=True, upload_to="signatures/%Y/%m/"),
        ),
        migrations.DeleteModel(
            name="Location",
        ),
    ]
