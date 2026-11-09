
from django.contrib import admin
from django.utils import timezone

from .models import DeviceActivationRequest, DeviceInstallation


@admin.register(DeviceActivationRequest)
class DeviceActivationRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "major_account",
        "installation_id",
        "expires_at",
        "consumed_at",
        "created_at",
    )
    list_filter = ("expires_at", "consumed_at")
    search_fields = ("major_account__name", "id", "installation_id")
    readonly_fields = (
        "id",
        "major_account",
        "installation_id",
        "code_hash",
        "expires_at",
        "consumed_at",
        "created_at",
    )


@admin.register(DeviceInstallation)
class DeviceInstallationAdmin(admin.ModelAdmin):
    list_display = (
        "major_account",
        "device_name",
        "status",
        "activated_at",
        "revoked_at",
    )
    list_filter = ("status", "activated_at")
    search_fields = (
        "major_account__name",
        "device_name",
        "installation_id",
    )
    readonly_fields = (
        "id",
        "major_account",
        "installation_id",
        "device_name",
        "credential_hash",
        "activated_at",
        "revoked_at",
    )
    actions = ["revoke_selected_installations"]

    @admin.action(description="Revoke selected device installations")
    def revoke_selected_installations(self, request, queryset):
        active_devices = queryset.filter(
            status=DeviceInstallation.Status.ACTIVE
        )

        count = active_devices.update(
            status=DeviceInstallation.Status.REVOKED,
            revoked_at=timezone.now(),
        )

        if count:
            self.message_user(
                request,
                f"Successfully revoked {count} device installation(s).",
            )
        else:
            self.message_user(
                request,
                "No active device installations were selected.",
            )
