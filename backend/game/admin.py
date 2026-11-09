from django.contrib import admin

# Register your models here.

from game.models import PlayerBet


@admin.register(PlayerBet)
class PlayerBetAdmin(admin.ModelAdmin):
    list_display = (
        "game_round",
        "major_account",
        "player_slot",
        "stake",
        "status",
        "cashout_multiplier",
        "payout",
        "payout_capped",
        "created_at",
    )
    list_filter = ("status", "major_account")
    readonly_fields = [f.name for f in PlayerBet._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Jackpots: amounts change only through the audited service
# ---------------------------------------------------------------------------

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from game.models import Jackpot, JackpotAdjustment
from game.services.jackpot_service import adjust_jackpot


class JackpotAdminForm(forms.ModelForm):
    adjustment_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required whenever the amount is changed. Saved in the audit log.",
    )

    class Meta:
        model = Jackpot
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        if (
            self.instance.pk
            and "amount" in self.changed_data
            and not (cleaned.get("adjustment_reason") or "").strip()
        ):
            self.add_error(
                "adjustment_reason", "An adjustment reason is required."
            )

        return cleaned


@admin.register(Jackpot)
class JackpotAdmin(admin.ModelAdmin):
    form = JackpotAdminForm
    list_display = ("label", "code", "amount", "color", "icon", "sort_order", "is_active", "updated_at")
    ordering = ("sort_order", "code")

    def save_model(self, request, obj, form, change):
        if not change:
            requested = obj.amount
            obj.amount = Decimal("0.00")
            super().save_model(request, obj, form, change)
            if requested > 0:
                adjust_jackpot(
                    jackpot_id=obj.pk,
                    new_amount=requested,
                    changed_by=request.user,
                    reason="Initial amount",
                )
            return

        requested = obj.amount
        amount_changed = "amount" in form.changed_data

        if amount_changed:
            # Keep the stored amount; the service applies and records the change.
            obj.amount = Jackpot.objects.get(pk=obj.pk).amount

        super().save_model(request, obj, form, change)

        if amount_changed:
            try:
                adjust_jackpot(
                    jackpot_id=obj.pk,
                    new_amount=requested,
                    changed_by=request.user,
                    reason=form.cleaned_data["adjustment_reason"],
                )
            except ValidationError as error:
                from django.contrib import messages

                messages.error(request, " ".join(error.messages))


@admin.register(JackpotAdjustment)
class JackpotAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("created_at", "jackpot", "previous_amount", "new_amount", "changed_by", "reason")
    list_filter = ("jackpot",)
    readonly_fields = [f.name for f in JackpotAdjustment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
