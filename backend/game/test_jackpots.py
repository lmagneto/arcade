import hashlib
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from devices.models import DeviceInstallation
from game.models import Jackpot, JackpotAdjustment
from game.services.jackpot_service import adjust_jackpot
from tenants.models import MajorAccount

D = Decimal


class JackpotServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin1", password="TestOnlyPassword123!", is_staff=True
        )
        self.owner = User.objects.create_user(
            username="owner1", password="TestOnlyPassword123!", role=User.Role.MAJOR_OWNER
        )
        self.grand = Jackpot.objects.get(code="grand")

    def adjust(self, amount, user=None, reason="Weekly top-up"):
        return adjust_jackpot(
            jackpot_id=self.grand.pk,
            new_amount=amount,
            changed_by=user or self.admin,
            reason=reason,
        )

    def test_admin_adjustment_updates_amount_and_writes_audit_record(self):
        self.adjust("2500.50")
        self.grand.refresh_from_db()
        self.assertEqual(self.grand.amount, D("2500.50"))
        record = JackpotAdjustment.objects.get()
        self.assertEqual(
            (record.previous_amount, record.new_amount, record.changed_by, record.reason),
            (D("2000.45"), D("2500.50"), self.admin, "Weekly top-up"),
        )

    def test_non_administrators_cannot_adjust(self):
        with self.assertRaises(PermissionError):
            self.adjust("10.00", user=self.owner)
        with self.assertRaises(PermissionError):
            adjust_jackpot(
                jackpot_id=self.grand.pk, new_amount="10.00",
                changed_by=None, reason="x",
            )
        self.assertEqual(JackpotAdjustment.objects.count(), 0)

    def test_invalid_amounts_and_reasons_are_rejected_without_changes(self):
        for amount in ("-1", "NaN", "Infinity", "abc", "1.234", "10000000000000000.00", None):
            with self.assertRaises(ValidationError, msg=str(amount)):
                self.adjust(amount)
        for reason in ("", "   ", None):
            with self.assertRaises(ValidationError):
                self.adjust("100.00", reason=reason)
        with self.assertRaises(ValidationError):
            self.adjust("2000.45")  # unchanged
        self.grand.refresh_from_db()
        self.assertEqual(self.grand.amount, D("2000.45"))
        self.assertEqual(JackpotAdjustment.objects.count(), 0)

    def test_zero_is_allowed(self):
        self.adjust("0")
        self.grand.refresh_from_db()
        self.assertEqual(self.grand.amount, D("0.00"))


class JackpotApiTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            username="jp-owner", password="TestOnlyPassword123!", role=User.Role.MAJOR_OWNER
        )
        account = MajorAccount.objects.create(name="Jackpot Arcade", owner=owner)
        credential = "jackpot-test-credential"
        DeviceInstallation.objects.create(
            major_account=account,
            installation_id=uuid.uuid4(),
            credential_hash=hashlib.sha256(credential.encode()).hexdigest(),
        )
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Device {credential}")

    def test_five_starting_tiers_in_display_order_with_client_shape(self):
        data = self.client.get("/api/game/jackpots/").data["jackpots"]
        self.assertEqual([j["id"] for j in data], ["grand", "major", "global", "mini", "minor"])
        self.assertEqual(
            data[0],
            {"id": "grand", "label": "GRAND JACKPOT", "amount": "2000.45", "color": "#d62bd6", "icon": "crown"},
        )

    def test_adjusted_amounts_show_up_and_inactive_tiers_are_hidden(self):
        admin = User.objects.create_user(username="a2", password="TestOnlyPassword123!", is_staff=True)
        adjust_jackpot(
            jackpot_id=Jackpot.objects.get(code="grand").pk,
            new_amount="2500.00", changed_by=admin, reason="Top-up",
        )
        Jackpot.objects.filter(code="minor").update(is_active=False)
        data = self.client.get("/api/game/jackpots/").data["jackpots"]
        self.assertEqual(data[0]["amount"], "2500.00")
        self.assertNotIn("minor", [j["id"] for j in data])

    def test_requires_a_device_credential(self):
        self.assertIn(APIClient().get("/api/game/jackpots/").status_code, (401, 403))


class JackpotAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="root1", password="TestOnlyPassword123!", email="r@example.com"
        )
        self.client.force_login(self.admin)
        self.grand = Jackpot.objects.get(code="grand")
        self.url = reverse("admin:game_jackpot_change", args=[self.grand.pk])

    def post(self, amount, reason=""):
        return self.client.post(self.url, {
            "code": "grand", "label": "GRAND JACKPOT", "amount": amount,
            "color": "#d62bd6", "icon": "crown", "sort_order": 10, "is_active": "on",
            "adjustment_reason": reason,
        })

    def test_changing_the_amount_requires_a_reason(self):
        response = self.post("3000.00", reason="")
        self.assertEqual(response.status_code, 200)  # form re-shown with an error
        self.grand.refresh_from_db()
        self.assertEqual(self.grand.amount, D("2000.45"))

    def test_admin_change_goes_through_the_audited_service(self):
        response = self.post("3000.00", reason="Promotion")
        self.assertEqual(response.status_code, 302)
        self.grand.refresh_from_db()
        self.assertEqual(self.grand.amount, D("3000.00"))
        record = JackpotAdjustment.objects.get()
        self.assertEqual((record.previous_amount, record.new_amount, record.reason, record.changed_by),
                         (D("2000.45"), D("3000.00"), "Promotion", self.admin))

    def test_audit_log_cannot_be_edited_or_deleted_in_admin(self):
        adjust_jackpot(jackpot_id=self.grand.pk, new_amount="1.00", changed_by=self.admin, reason="x")
        record = JackpotAdjustment.objects.get()
        self.assertEqual(self.client.get(reverse("admin:game_jackpotadjustment_delete", args=[record.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:game_jackpotadjustment_add")).status_code, 403)
