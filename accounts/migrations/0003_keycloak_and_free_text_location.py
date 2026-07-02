from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="keycloak_id",
            field=models.CharField(blank=True, max_length=255, null=True, unique=True),
        ),
        migrations.RemoveField(
            model_name="user",
            name="assigned_location",
        ),
        migrations.AlterField(
            model_name="user",
            name="designation",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("WORKER", "Employee"),
                    ("SUPERVISOR", "Supervisor"),
                    ("SHOP_FLOOR_MANAGER", "Shop Floor Manager"),
                    ("DIRECTOR", "Director of Production"),
                    ("CEO", "CEO"),
                    ("ADMIN", "Admin"),
                ],
                default="WORKER",
                max_length=32,
            ),
        ),
    ]
