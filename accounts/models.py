from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    WORKER = "WORKER", "Employee"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    SHOP_FLOOR_MANAGER = "SHOP_FLOOR_MANAGER", "Shop Floor Manager"
    DIRECTOR = "DIRECTOR", "Director of Production"
    CEO = "CEO", "CEO"
    ADMIN = "ADMIN", "Admin"


class User(AbstractUser):
    keycloak_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    designation = models.CharField(max_length=255, blank=True, default="")
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.WORKER)

    class Meta:
        ordering = ["last_name", "first_name", "username"]

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.username

    def can_report(self):
        return self.role != Role.ADMIN

    def has_plant_wide_access(self):
        return self.role in {Role.ADMIN, Role.CEO}

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"
