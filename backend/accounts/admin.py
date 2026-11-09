
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "must_change_password",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "role",
        "must_change_password",
        "is_staff",
        "is_active",
    )

    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )

    ordering = ("username",)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "ARCADE Account Settings",
            {
                "fields": (
                    "role",
                    "must_change_password",
                ),
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "ARCADE Account Settings",
            {
                "classes": ("wide",),
                "fields": (
                    "role",
                    "must_change_password",
                ),
            },
        ),
    )
