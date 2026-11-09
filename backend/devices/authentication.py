
import hashlib

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from devices.models import DeviceInstallation
from tenants.models import MajorAccount


class DeviceCredentialAuthentication(BaseAuthentication):
    """
    Authenticate an activated installation using its device credential.

    The plaintext credential is never stored in the database.
    """

    def authenticate(self, request):
        authorization = request.headers.get("Authorization", "")
        parts = authorization.split()

        if not parts or parts[0].lower() != "device":
            return None

        if len(parts) != 2 or not parts[1]:
            raise AuthenticationFailed("Invalid device authorization header.")

        credential = parts[1]
        credential_hash = hashlib.sha256(
            credential.encode("utf-8")
        ).hexdigest()

        try:
            installation = (
                DeviceInstallation.objects
                .select_related("major_account__owner")
                .get(credential_hash=credential_hash)
            )
        except DeviceInstallation.DoesNotExist:
            raise AuthenticationFailed("Invalid device credential.")

        if installation.status != DeviceInstallation.Status.ACTIVE:
            raise AuthenticationFailed("This installation has been revoked.")

        if installation.major_account.status != MajorAccount.Status.ACTIVE:
            raise AuthenticationFailed("This major account is not active.")

        owner = installation.major_account.owner

        if not owner.is_active:
            raise AuthenticationFailed("The account owner is inactive.")

        return owner, installation

    def authenticate_header(self, request):
        return "Device"
