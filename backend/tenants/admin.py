
from django.contrib import admin

from .models import MajorAccount, PlayerSlot


class PlayerSlotInline(admin.TabularInline):
    model = PlayerSlot
    extra = 0
    fields = (
        "slot_number",
        "display_name",
        "status",
        "created_at",
    )
    readonly_fields = ("created_at",)


@admin.register(MajorAccount)
class MajorAccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "account_code",
        "owner",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "name",
        "account_code",
        "owner__username",
    )
    readonly_fields = (
        "id",
        "account_code",
        "created_at",
        "updated_at",
    )
    inlines = [PlayerSlotInline]


@admin.register(PlayerSlot)
class PlayerSlotAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "major_account",
        "slot_number",
        "status",
        "created_at",
    )
    list_filter = ("status", "major_account")
    search_fields = (
        "display_name",
        "major_account__name",
        "major_account__account_code",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
