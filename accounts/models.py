from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    WORKER = "WORKER", "Worker"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    SHOP_FLOOR_MANAGER = "SHOP_FLOOR_MANAGER", "Shop Floor Manager"
    DIRECTOR = "DIRECTOR", "Director of Production"
    CEO = "CEO", "CEO"
    ADMIN = "ADMIN", "Admin"


class User(AbstractUser):
    designation = models.CharField(max_length=255)
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.WORKER)
    assigned_location = models.ForeignKey(
        "incidents.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_users",
    )

    class Meta:
        ordering = ["last_name", "first_name", "username"]

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    def can_report(self):
        return self.role in {
            Role.WORKER,
            Role.SUPERVISOR,
            Role.SHOP_FLOOR_MANAGER,
        }

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.role in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER} and not self.assigned_location_id:
            raise ValidationError("Supervisor and Shop Floor Manager must have an assigned location.")
        if self.role not in {Role.SUPERVISOR, Role.SHOP_FLOOR_MANAGER} and self.assigned_location_id:
            raise ValidationError("Only Supervisor and Shop Floor Manager may have an assigned location.")

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
