import logging
import re
from uuid import UUID
from devices.authentication import DeviceCredentialAuthentication
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from django.db import transaction
from django.utils import timezone
from packaging.version import InvalidVersion, Version
import requests
from accounts.permissions import PasswordChangeComplete
from devices.services.activation import (
    activate_installation,
    create_activation_request,
    create_pc_pairing_request,
)
from devices.models import DeviceActivationRequest, DeviceInstallation
from tenants.models import MajorAccount

logger = logging.getLogger(__name__)
CLIENT_UPDATE_CACHE_SECONDS = 300
CLIENT_UPDATE_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class IsPlatformAdministrator(BasePermission):
    message = "Platform administrator access is required."

    def has_permission(self, request, view):
        user = request.user
        return (
            user.is_authenticated
            and user.is_staff
            and getattr(user, "role", None) == "PLATFORM_ADMIN"
        )


class DeviceActivationThrottle(AnonRateThrottle):
    scope = "device_activation"


class PairingStatusThrottle(AnonRateThrottle):
    scope = "pairing_status"


class CreateActivationRequestView(APIView):
    permission_classes = [
        IsAuthenticated,
        PasswordChangeComplete,
        IsPlatformAdministrator,
    ]

    def post(self, request):
        major_account_id = request.data.get("major_account_id")

        if not major_account_id:
            return Response(
                {"detail": "major_account_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = create_activation_request(
                major_account_id=major_account_id,
            )
        except MajorAccount.DoesNotExist:
            return Response(
                {"detail": "Major account not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except (ValidationError, ValueError, TypeError) as exc:
            message = (
                exc.messages
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_201_CREATED)


class ActivateDeviceView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DeviceActivationThrottle]

    def post(self, request):
        installation_id = request.data.get("installation_id")
        activation_code = request.data.get("activation_code")
        device_name = request.data.get("device_name", "")

        if not installation_id or not activation_code:
            return Response(
                {
                    "detail": (
                        "installation_id and activation_code are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = activate_installation(
                installation_id=installation_id,
                activation_code=activation_code,
                device_name=device_name,
            )
        except ValidationError as exc:
            return Response(
                {"detail": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        installation = result["installation"]

        return Response(
            {
                "installation_id": str(installation.installation_id),
                "major_account_id": str(installation.major_account_id),
                "device_name": installation.device_name,
                "status": installation.status,
                "device_credential": result["device_credential"],
            },
            status=status.HTTP_200_OK,
        )


class DeviceStatusView(APIView):
    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        installation = request.auth
        major_account = installation.major_account

        return Response({
            "installation_id": str(installation.installation_id),
            "device_name": installation.device_name,
            "installation_status": installation.status,
            "major_account_id": str(major_account.id),
            "major_account_name": major_account.name,
            "major_account_status": major_account.status,
        })


class ClientUpdateView(APIView):
    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client_version = request.query_params.get("version", "")
        try:
            installed_version = Version(client_version)
        except InvalidVersion:
            return Response(
                {"detail": "A valid client version query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        release_tag = settings.GAME_CLIENT_RELEASE_TAG
        if not release_tag:
            return Response(
                {"detail": "The game client release tag is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        manifest = cache.get(f"arcade-client-update:{release_tag}")
        if manifest is None:
            manifest = self.fetch_manifest(release_tag)
            if isinstance(manifest, Response):
                return manifest
            cache.set(
                f"arcade-client-update:{release_tag}",
                manifest,
                CLIENT_UPDATE_CACHE_SECONDS,
            )

        try:
            latest_version = Version(manifest["version"])
        except (InvalidVersion, KeyError, TypeError):
            logger.error("The configured game client update manifest is invalid.")
            return Response(
                {"detail": "The game client update manifest is invalid."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            "update_available": latest_version > installed_version,
            "version": str(latest_version),
            "download_url": manifest["download_url"],
            "sha256": manifest["sha256"],
        })

    @staticmethod
    def fetch_manifest(release_tag):
        release_url = (
            "https://api.github.com/repos/lmagneto/arcade/releases/tags/"
            f"{release_tag}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "arcade-client-updater",
        }
        try:
            release_response = requests.get(
                release_url,
                headers=headers,
                timeout=(3, 5),
            )
            release_response.raise_for_status()
            release = release_response.json()
            if (
                not isinstance(release, dict)
                or release.get("tag_name") != release_tag
                or not isinstance(release.get("assets"), list)
            ):
                raise ValueError("The release tag does not match configuration.")
            manifest_asset = next(
                asset
                for asset in release["assets"]
                if isinstance(asset, dict)
                and asset.get("name") == "client-update.json"
            )
            manifest_url = manifest_asset.get("browser_download_url")
            expected_manifest_url = (
                "https://github.com/lmagneto/arcade/releases/download/"
                f"{release_tag}/"
            )
            if (
                not isinstance(manifest_url, str)
                or not manifest_url.startswith(expected_manifest_url)
            ):
                raise ValueError("The release manifest URL is invalid.")
            manifest_response = requests.get(
                manifest_url,
                headers={"User-Agent": "arcade-client-updater"},
                timeout=(3, 5),
            )
            manifest_response.raise_for_status()
            manifest = manifest_response.json()
        except (requests.RequestException, KeyError, StopIteration, ValueError):
            logger.exception(
                "Could not load the game client update manifest for tag %s.",
                release_tag,
            )
            return Response(
                {"detail": "No valid game client update is available."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not isinstance(manifest, dict):
            logger.error("The game client update manifest is not an object.")
            return Response(
                {"detail": "The game client update manifest is invalid."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        version = manifest.get("version")
        download_url = manifest.get("download_url")
        sha256 = manifest.get("sha256")
        expected_prefix = (
            "https://github.com/lmagneto/arcade/releases/download/"
            f"{release_tag}/"
        )
        if (
            not isinstance(version, str)
            or not isinstance(download_url, str)
            or not isinstance(sha256, str)
            or not CLIENT_UPDATE_SHA256.fullmatch(sha256)
            or not download_url.startswith(expected_prefix)
            or not download_url.lower().endswith(".exe")
        ):
            logger.error(
                "The game client update manifest for tag %s failed validation.",
                release_tag,
            )
            return Response(
                {"detail": "The game client update manifest is invalid."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            parsed_version = Version(version)
        except InvalidVersion:
            logger.error(
                "The game client update manifest has an invalid version."
            )
            return Response(
                {"detail": "The game client update manifest is invalid."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if release_tag != f"game-client-v{parsed_version}":
            logger.error(
                "The game client update version does not match release tag %s.",
                release_tag,
            )
            return Response(
                {"detail": "The game client update manifest is invalid."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return {
            "version": version,
            "download_url": download_url,
            "sha256": sha256.lower(),
        }

class CreatePCPairingRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DeviceActivationThrottle]

    def post(self, request):
        installation_id = request.data.get("installation_id")

        if not installation_id:
            return Response(
                {"detail": "installation_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = create_pc_pairing_request(
                installation_id=installation_id,
            )
        except ValidationError as exc:
            return Response(
                {"detail": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(result, status=status.HTTP_201_CREATED)


class ClaimPCPairingRequestView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def post(self, request):
        pairing_code = request.data.get("pairing_code")

        if not isinstance(pairing_code, str) or not pairing_code.strip():
            return Response(
                {"detail": "pairing_code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner_accounts = MajorAccount.objects.filter(
            owner=request.user,
            status=MajorAccount.Status.ACTIVE,
        )

        if owner_accounts.count() != 1:
            return Response(
                {
                    "detail": (
                        "Your user account must own exactly one active "
                        "major account to link a PC."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        from devices.services.activation import _hash_code

        code_hash = _hash_code(pairing_code.strip().upper())

        try:
            with transaction.atomic():
                activation_request = (
                    DeviceActivationRequest.objects.select_for_update()
                    .get(code_hash=code_hash)
                )

                if activation_request.major_account_id is not None:
                    return Response(
                        {"detail": "This code has already been claimed."},
                        status=status.HTTP_409_CONFLICT,
                    )

                if activation_request.consumed_at is not None:
                    return Response(
                        {"detail": "This code has already been used."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if activation_request.expires_at <= timezone.now():
                    return Response(
                        {"detail": "This pairing code has expired."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                major_account = owner_accounts.first()

                if DeviceInstallation.objects.filter(
                    major_account=major_account,
                    status=DeviceInstallation.Status.ACTIVE,
                ).exists():
                    return Response(
                        {
                            "detail": (
                                "This major account already has an active PC. "
                                "Revoke it before linking another."
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                activation_request.major_account = major_account
                activation_request.save(update_fields=["major_account"])

        except DeviceActivationRequest.DoesNotExist:
            return Response(
                {"detail": "Invalid pairing code."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "detail": "PC pairing approved. The PC can now complete activation.",
                "installation_id": str(activation_request.installation_id),
            },
            status=status.HTTP_200_OK,
        )


class PCPairingStatusView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PairingStatusThrottle]
    def get(self, request):
        installation_id = request.query_params.get("installation_id")

        try:
            installation_uuid = UUID(str(installation_id))
        except (ValueError, TypeError, AttributeError):
            return Response(
                {"detail": "A valid installation_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        activation_request = DeviceActivationRequest.objects.filter(
            installation_id=installation_uuid,
        ).first()

        if activation_request is None:
            return Response(
                {"detail": "Pairing request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if activation_request.consumed_at is not None:
            return Response({"status": "ACTIVATED"})

        if activation_request.expires_at <= timezone.now():
            return Response({"status": "EXPIRED"})

        if activation_request.major_account_id is None:
            return Response({"status": "WAITING"})

        return Response({
            "status": "APPROVED",
            "installation_id": str(activation_request.installation_id),
        })
