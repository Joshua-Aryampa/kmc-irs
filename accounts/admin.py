from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "designation", "role", "keycloak_id", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "keycloak_id")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("IRS Profile", {"fields": ("keycloak_id", "designation", "role")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("IRS Profile", {"fields": ("keycloak_id", "designation", "role", "email", "first_name", "last_name")}),
    )
