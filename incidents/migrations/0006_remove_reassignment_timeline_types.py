from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0005_incident_sequence_monthly_period"),
    ]

    operations = [
        migrations.AlterField(
            model_name="timelineentry",
            name="entry_type",
            field=models.CharField(
                choices=[
                    ("CREATED", "Created"),
                    ("SUBMITTED", "Submitted"),
                    ("VERIFIED", "Verified"),
                    ("VERIFICATION_REJECTED", "Verification rejected"),
                    ("APPROVED", "Approved"),
                    ("APPROVAL_REJECTED", "Approval rejected"),
                    ("COMMENT", "Comment"),
                    ("RETURNED_TO_REPORTER", "Returned to reporter"),
                    ("LATE_FLAGGED", "Late submission flagged"),
                ],
                max_length=32,
            ),
        ),
    ]
