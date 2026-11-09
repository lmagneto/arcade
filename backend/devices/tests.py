
import uuid
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import User
from devices.models import DeviceActivationRequest, DeviceInstallation
from devices.services.activation import _hash_code
from tenants.models import MajorAccount


class DevicePairingWorkflowTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="pairing_owner",
            password="TestOwnerPassword123!",
            role=User.Role.MAJOR_OWNER,
        )

        self.account = MajorAccount.objects.create(
            name="Pairing Test Account",
            owner=self.owner,
            status=MajorAccount.Status.ACTIVE,
        )

        self.installation_id = str(uuid.uuid4())

    def request_pairing_code(self):
        response = self.client.post(
            "/api/devices/pairing-requests/",
            {"installation_id": self.installation_id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data["pairing_code"]

    def test_owner_can_approve_and_activate_pc(self):
        pairing_code = self.request_pairing_code()

        activation_request = DeviceActivationRequest.objects.get(
            installation_id=self.installation_id
        )

        self.assertEqual(
            activation_request.code_hash,
            _hash_code(pairing_code),
        )
        self.assertIsNone(activation_request.major_account_id)

        self.client.force_authenticate(user=self.owner)

        claim_response = self.client.post(
            "/api/devices/pairing-requests/claim/",
            {"pairing_code": pairing_code},
            format="json",
        )

        self.assertEqual(claim_response.status_code, 200)

        activation_request.refresh_from_db()
        self.assertEqual(
            activation_request.major_account_id,
            self.account.id,
        )

        status_response = self.client.get(
            "/api/devices/pairing-requests/status/",
            {"installation_id": self.installation_id},
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data["status"], "APPROVED")

        activation_response = self.client.post(
            "/api/devices/activate/",
            {
                "installation_id": self.installation_id,
                "activation_code": pairing_code,
                "device_name": "Test Windows PC",
            },
            format="json",
        )

        self.assertEqual(activation_response.status_code, 200)
        self.assertTrue(
            activation_response.data["device_credential"]
        )

        installation = DeviceInstallation.objects.get(
            installation_id=self.installation_id
        )

        self.assertEqual(installation.major_account, self.account)
        self.assertEqual(
            installation.status,
            DeviceInstallation.Status.ACTIVE,
        )

        activation_request.refresh_from_db()
        self.assertIsNotNone(activation_request.consumed_at)

    def test_expired_pairing_code_cannot_be_claimed(self):
        pairing_code = self.request_pairing_code()

        activation_request = DeviceActivationRequest.objects.get(
            installation_id=self.installation_id
        )

        activation_request.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        activation_request.save(update_fields=["expires_at"])

        self.client.force_authenticate(user=self.owner)

        response = self.client.post(
            "/api/devices/pairing-requests/claim/",
            {"pairing_code": pairing_code},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(
            DeviceInstallation.objects.filter(
                installation_id=self.installation_id
            ).first()
        )

    def test_unrelated_user_cannot_claim_pairing_code(self):
        pairing_code = self.request_pairing_code()

        unrelated_user = User.objects.create_user(
            username="unrelated_user",
            password="TestOtherPassword123!",
            role=User.Role.MAJOR_OWNER,
        )

        self.client.force_authenticate(user=unrelated_user)

        response = self.client.post(
            "/api/devices/pairing-requests/claim/",
            {"pairing_code": pairing_code},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        activation_request = DeviceActivationRequest.objects.get(
            installation_id=self.installation_id
        )
        self.assertIsNone(activation_request.major_account_id)
