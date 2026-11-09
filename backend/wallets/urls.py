
from django.urls import path

from wallets.views import (
    MajorAccountListView,
    PlayerSlotListView,
    PlayerCreditTransferView,
    MajorAccountCreditReturnView,
    PlatformCreditIssuanceView,
    PlatformCreditAllocationView,
    PlatformReserveView,
    PlatformTransactionHistoryView,
    MajorAccountTransactionHistoryView,
)

urlpatterns = [
    path(
        "major-accounts/",
        MajorAccountListView.as_view(),
        name="major-account-list",
    ),
    path(
        "major-accounts/<uuid:major_account_id>/players/",
        PlayerSlotListView.as_view(),
        name="major-account-players",
    ),
    path(
        "major-accounts/<uuid:major_account_id>/players/<uuid:player_slot_id>/transfer/",
        PlayerCreditTransferView.as_view(),
        name="player-credit-transfer",
    ),

path(
    "major-accounts/<uuid:major_account_id>/return/",
    MajorAccountCreditReturnView.as_view(),
    name="major-account-credit-return",
),
    path(
        "platform/issue/",
        PlatformCreditIssuanceView.as_view(),
        name="platform-credit-issuance",
    ),

   path(
        "platform/allocate/",
        PlatformCreditAllocationView.as_view(),
        name="platform-credit-allocation",
   ),

   path(
    "platform/reserve/",
    PlatformReserveView.as_view(),
    name="platform-reserve",
   ),
   path(
    "platform/transactions/",
    PlatformTransactionHistoryView.as_view(),
    name="platform-transactions",
    ),

    path(
    "major-accounts/<uuid:major_account_id>/transactions/",
    MajorAccountTransactionHistoryView.as_view(),
    name="major-account-transactions",
),
]
