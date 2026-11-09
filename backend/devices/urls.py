
from django.urls import path

from devices.views import (
    ActivateDeviceView,
    CreateActivationRequestView,
    DeviceStatusView,
    CreatePCPairingRequestView,
    ClaimPCPairingRequestView,
    PCPairingStatusView,
)
from devices.player_views import (
    SyncPlayerSlotsView,
    DevicePlayerSlotListView,
)

app_name = "devices"

urlpatterns = [
    path(
        "activation-requests/",
        CreateActivationRequestView.as_view(),
        name="create-activation-request",
    ),
    path(
        "activate/",
        ActivateDeviceView.as_view(),
        name="activate-device",
    ),

    path("player-slots/sync/",
    SyncPlayerSlotsView.as_view(),
    name="sync-player-slots",
),
    path(
        "pairing-requests/",
        CreatePCPairingRequestView.as_view(),
        name="create-pc-pairing-request",
    ),
    path(
        "pairing-requests/claim/",
        ClaimPCPairingRequestView.as_view(),
        name="claim-pc-pairing-request",
    ),
    path(
        "pairing-requests/status/",
        PCPairingStatusView.as_view(),
        name="pc-pairing-status",
    ),

    path(
        "status/",
        DeviceStatusView.as_view(),
        name="device-status",
    ),

path(
    "player-slots/",
    DevicePlayerSlotListView.as_view(),
    name="device-player-slot-list",
),
]