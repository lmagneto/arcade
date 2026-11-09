from django.core.exceptions import ValidationError

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from tenants.models import PlayerSlot
from devices.authentication import DeviceCredentialAuthentication
from tenants.services.player_slots import sync_player_slots


class SyncPlayerSlotsView(APIView):
    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        detected_count = request.data.get("detected_count")

        # Accept only an integer from 1 to 8, not a boolean or string.
        if (
            isinstance(detected_count, bool)
            or not isinstance(detected_count, int)
            or not 1 <= detected_count <= 8
        ):
            return Response(
                {"detail": "detected_count must be an integer between 1 and 8."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # The account comes from the authenticated installation.
        # Never accept a major_account_id from the request body.
        installation = request.auth

        try:
            slots = sync_player_slots(
                major_account_id=installation.major_account_id,
                detected_count=detected_count,
            )
        except ValidationError as exc:
            return Response(
                {"detail": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "major_account_id": str(installation.major_account_id),
                "detected_count": detected_count,
                "players": [
                    {
                        "slot_id": str(slot.id),
                        "slot_number": slot.slot_number,
                        "display_name": slot.display_name,
                        "status": slot.status,
                        "wallet_balance": str(
                            slot.wallet.available_balance
                        ),
                    }
                    for slot in slots
                ],
            },
            status=status.HTTP_200_OK,
        )


class DevicePlayerSlotListView(APIView):
    authentication_classes = [DeviceCredentialAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        installation = request.auth

        slots = (
            PlayerSlot.objects
            .filter(major_account_id=installation.major_account_id)
            .select_related("wallet")
            .order_by("slot_number")
        )

        return Response(
            {
                "major_account_id": str(installation.major_account_id),
                "players": [
                    {
                        "slot_id": str(slot.id),
                        "slot_number": slot.slot_number,
                        "display_name": (
                            slot.display_name
                            or f"Player {slot.slot_number}"
                        ),
                        "status": slot.status,
                        "wallet_balance": str(
                            slot.wallet.available_balance
                        ),
                    }
                    for slot in slots
                ],
            },
            status=status.HTTP_200_OK,
        )
