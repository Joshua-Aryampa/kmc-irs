from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("incidents", "0003_keycloak_and_free_text_location"),
    ]

    operations = [
        migrations.AlterField(
            model_name="witness",
            name="designation",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
