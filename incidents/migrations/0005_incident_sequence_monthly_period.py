from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0004_witness_designation_optional"),
    ]

    operations = [
        migrations.DeleteModel(
            name="IncidentSequence",
        ),
        migrations.CreateModel(
            name="IncidentSequence",
            fields=[
                ("period", models.CharField(max_length=6, primary_key=True, serialize=False)),
                ("last_sequence", models.PositiveIntegerField(default=0)),
            ],
        ),
    ]
