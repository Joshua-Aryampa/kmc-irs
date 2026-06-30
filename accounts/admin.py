from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "designation", "role", "assigned_location", "is_active")
    list_filter = ("role", "assigned_location", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("IRS Profile", {"fields": ("designation", "role", "assigned_location")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("IRS Profile", {"fields": ("designation", "role", "assigned_location", "email", "first_name", "last_name")}),
    )
