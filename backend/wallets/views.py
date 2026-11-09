
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import PasswordChangeComplete

from tenants.models import MajorAccount, PlayerSlot
from wallets.models import Wallet, LedgerTransaction, LedgerEntry
from django.db.models import Q, Prefetch

def is_major_owner(user):
    return (
        user.is_authenticated
        and getattr(user, "role", None) == "MAJOR_OWNER"
    )


def is_platform_admin(user):
    return (
        user.is_authenticated
        and user.is_staff
        and getattr(user, "role", None) == "PLATFORM_ADMIN"
    )


def parse_positive_amount(raw_amount):
    if (
        not isinstance(raw_amount, (str, int, float, Decimal))
        or isinstance(raw_amount, bool)
    ):
        return None

    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError):
        return None

    if not amount.is_finite():
        return None

    if amount <= 0 or amount >= Decimal("10000000000000000"):
        return None

    try:
        if amount != amount.quantize(Decimal("0.01")):
            return None
    except InvalidOperation:
        return None

    return amount


def validate_idempotency_key(raw_key):
    if (
        not isinstance(raw_key, str)
        or not raw_key.strip()
        or len(raw_key.strip()) > 100
    ):
        return None

    key = raw_key.strip()

    try:
        UUID(key)
    except (ValueError, AttributeError):
        return None

    return key


class MajorAccountListView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def get(self, request):
        if not is_major_owner(request.user):
            return Response(
                {"detail": "Major account owner access is required."},
                status=403,
            )

        accounts = MajorAccount.objects.filter(
            owner=request.user
        ).order_by("name")

        results = []

        for account in accounts:
            wallet = Wallet.objects.filter(
                major_account=account
            ).first()

            results.append({
                "id": str(account.id),
                "name": account.name,
                "status": account.status,
                "wallet_balance": str(
                    wallet.available_balance
                    if wallet else Decimal("0.00")
                ),
            })

        return Response({"accounts": results})


class PlayerSlotListView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def get(self, request, major_account_id):
        if not is_major_owner(request.user):
            return Response(
                {"detail": "Major account owner access is required."},
                status=403,
            )

        account = MajorAccount.objects.filter(
            id=major_account_id,
            owner=request.user,
        ).first()

        if account is None:
            return Response(
                {"detail": "Major account not found."},
                status=404,
            )

        slots = PlayerSlot.objects.filter(
            major_account=account
        ).order_by("slot_number")

        results = []

        for slot in slots:
            wallet = Wallet.objects.filter(
                player_slot=slot
            ).first()

            results.append({
                "id": str(slot.id),
                "slot_number": slot.slot_number,
                "display_name": (
                    slot.display_name or f"Player {slot.slot_number}"
                ),
                "status": slot.status,
                "wallet_balance": str(
                    wallet.available_balance
                    if wallet else Decimal("0.00")
                ),
            })

        return Response({
            "major_account_id": str(account.id),
            "major_account_name": account.name,
            "account_status": account.status,
            "players": results,
        })


class PlayerCreditTransferView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def post(self, request, major_account_id, player_slot_id):
        if not is_major_owner(request.user):
            return Response(
                {"detail": "Major account owner access is required."},
                status=403,
            )

        direction = request.data.get("direction")
        amount = parse_positive_amount(request.data.get("amount"))
        idempotency_key = validate_idempotency_key(
            request.data.get("idempotency_key")
        )

        if direction not in ("CREDIT", "DEBIT"):
            return Response(
                {"detail": "direction must be CREDIT or DEBIT."},
                status=400,
            )

        if amount is None:
            return Response(
                {
                    "detail": (
                        "amount must be positive, with at most "
                        "2 decimal places."
                    )
                },
                status=400,
            )

        if idempotency_key is None:
            return Response(
                {"detail": "A valid UUID idempotency_key is required."},
                status=400,
            )

        try:
            with transaction.atomic():
                account = MajorAccount.objects.select_for_update().filter(
                    id=major_account_id,
                    owner=request.user,
                ).first()

                if account is None:
                    return Response(
                        {"detail": "Major account not found."},
                        status=404,
                    )

                if account.status != MajorAccount.Status.ACTIVE:
                    return Response(
                        {"detail": "Major account is not active."},
                        status=409,
                    )

                slot = PlayerSlot.objects.select_for_update().filter(
                    id=player_slot_id,
                    major_account=account,
                ).first()

                if slot is None:
                    return Response(
                        {
                            "detail": (
                                "Player slot not found in this account."
                            )
                        },
                        status=404,
                    )

                if slot.status != PlayerSlot.Status.ACTIVE:
                    return Response(
                        {
                            "detail": (
                                "Only active player slots can be "
                                "credited or debited."
                            )
                        },
                        status=409,
                    )

                if LedgerTransaction.objects.filter(
                    idempotency_key=idempotency_key
                ).exists():
                    return Response(
                        {"detail": "This request key has already been used."},
                        status=409,
                    )

                major_wallet_id = Wallet.objects.filter(
                    major_account=account
                ).values_list("id", flat=True).first()

                player_wallet_id = Wallet.objects.filter(
                    player_slot=slot
                ).values_list("id", flat=True).first()

                if major_wallet_id is None or player_wallet_id is None:
                    return Response(
                        {"detail": "A required wallet is missing."},
                        status=409,
                    )

                locked_wallets = {
                    wallet.id: wallet
                    for wallet in Wallet.objects.select_for_update()
                    .filter(id__in=[major_wallet_id, player_wallet_id])
                    .order_by("id")
                }

                major_wallet = locked_wallets[major_wallet_id]
                player_wallet = locked_wallets[player_wallet_id]

                if direction == "CREDIT":
                    source = major_wallet
                    destination = player_wallet
                    description = f"Credit to Player {slot.slot_number}"
                    ledger_type = (
                        LedgerTransaction.TransactionType.ALLOCATION
                    )
                else:
                    source = player_wallet
                    destination = major_wallet
                    description = f"Debit from Player {slot.slot_number}"
                    ledger_type = (
                        LedgerTransaction.TransactionType.ADJUSTMENT
                    )

                if source.available_balance < amount:
                    return Response(
                        {
                            "detail": (
                                "Insufficient available virtual credits."
                            )
                        },
                        status=409,
                    )

                ledger_transaction = LedgerTransaction.objects.create(
                    idempotency_key=idempotency_key,
                    transaction_type=ledger_type,
                    description=description,
                    created_by=request.user,
                )

                source.available_balance -= amount
                destination.available_balance += amount

                source.save(
                    update_fields=["available_balance", "updated_at"]
                )
                destination.save(
                    update_fields=["available_balance", "updated_at"]
                )

                LedgerEntry.objects.create(
                    transaction=ledger_transaction,
                    wallet=source,
                    direction=LedgerEntry.Direction.DEBIT,
                    amount=amount,
                )

                LedgerEntry.objects.create(
                    transaction=ledger_transaction,
                    wallet=destination,
                    direction=LedgerEntry.Direction.CREDIT,
                    amount=amount,
                )

                return Response({
                    "detail": "Virtual credit transfer completed.",
                    "reference": str(ledger_transaction.reference),
                    "direction": direction,
                    "amount": str(amount),
                    "major_account_balance": str(
                        major_wallet.available_balance
                    ),
                    "player_balance": str(
                        player_wallet.available_balance
                    ),
                }, status=200)

        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "The request could not be recorded. Check the "
                        "request key and transaction history before retrying."
                    )
                },
                status=409,
            )



class MajorAccountCreditReturnView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def post(self, request, major_account_id):
        if not is_major_owner(request.user):
            return Response(
                {"detail": "Major account owner access is required."},
                status=403,
            )

        amount = parse_positive_amount(request.data.get("amount"))
        idempotency_key = validate_idempotency_key(
            request.data.get("idempotency_key")
        )
        description = request.data.get(
            "description",
            "Return credits to platform reserve",
        )

        if amount is None:
            return Response(
                {
                    "detail": (
                        "amount must be positive, with at most "
                        "2 decimal places."
                    )
                },
                status=400,
            )

        if idempotency_key is None:
            return Response(
                {"detail": "A valid UUID idempotency_key is required."},
                status=400,
            )

        if not isinstance(description, str) or len(description) > 255:
            return Response(
                {"detail": "description must be text of at most 255 characters."},
                status=400,
            )

        try:
            with transaction.atomic():
                account = MajorAccount.objects.select_for_update().filter(
                    id=major_account_id,
                    owner=request.user,
                ).first()

                if account is None:
                    return Response(
                        {"detail": "Major account not found."},
                        status=404,
                    )

                if account.status != MajorAccount.Status.ACTIVE:
                    return Response(
                        {"detail": "Major account is not active."},
                        status=409,
                    )

                if LedgerTransaction.objects.filter(
                    idempotency_key=idempotency_key
                ).exists():
                    return Response(
                        {"detail": "This request key has already been used."},
                        status=409,
                    )

                reserve_id = Wallet.objects.filter(
                    platform_reserve=True
                ).values_list("id", flat=True).first()

                major_wallet_id = Wallet.objects.filter(
                    major_account=account
                ).values_list("id", flat=True).first()

                if reserve_id is None or major_wallet_id is None:
                    return Response(
                        {"detail": "A required wallet is missing."},
                        status=409,
                    )

                if reserve_id == major_wallet_id:
                    return Response(
                        {"detail": "Invalid wallet configuration."},
                        status=409,
                    )

                # Lock both wallets in a consistent order.
                locked_wallets = {
                    wallet.id: wallet
                    for wallet in Wallet.objects.select_for_update()
                    .filter(id__in=[reserve_id, major_wallet_id])
                    .order_by("id")
                }

                reserve_wallet = locked_wallets.get(reserve_id)
                major_wallet = locked_wallets.get(major_wallet_id)

                if reserve_wallet is None or major_wallet is None:
                    return Response(
                        {"detail": "A required wallet could not be locked."},
                        status=409,
                    )

                if major_wallet.available_balance < amount:
                    return Response(
                        {
                            "detail": (
                                "Insufficient available virtual credits "
                                "in the major account."
                            )
                        },
                        status=409,
                    )

                maximum_balance = Decimal("10000000000000000")

                if reserve_wallet.available_balance + amount >= maximum_balance:
                    return Response(
                        {"detail": "Return would exceed the reserve maximum balance."},
                        status=400,
                    )

                ledger_transaction = LedgerTransaction.objects.create(
                    idempotency_key=idempotency_key,
                    transaction_type=(
                        LedgerTransaction.TransactionType.ADJUSTMENT
                    ),
                    description=(
                        description.strip()
                        or f"Return credits from {account.name} to platform reserve"
                    ),
                    created_by=request.user,
                )

                major_wallet.available_balance -= amount
                reserve_wallet.available_balance += amount

                major_wallet.save(
                    update_fields=["available_balance", "updated_at"]
                )
                reserve_wallet.save(
                    update_fields=["available_balance", "updated_at"]
                )

                LedgerEntry.objects.create(
                    transaction=ledger_transaction,
                    wallet=major_wallet,
                    direction=LedgerEntry.Direction.DEBIT,
                    amount=amount,
                )

                LedgerEntry.objects.create(
                    transaction=ledger_transaction,
                    wallet=reserve_wallet,
                    direction=LedgerEntry.Direction.CREDIT,
                    amount=amount,
                )

                return Response(
                    {
                        "detail": "Virtual credits returned successfully.",
                        "reference": str(ledger_transaction.reference),
                        "amount": str(amount),
                        "major_account_id": str(account.id),
                        "major_account_name": account.name,
                        "major_account_balance": str(
                            major_wallet.available_balance
                        ),
                        "reserve_balance": str(
                            reserve_wallet.available_balance
                        ),
                    },
                    status=201,
                )

        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "The return could not be recorded. Check "
                        "transaction history before retrying."
                    )
                },
                status=409,
            )


class PlatformCreditIssuanceView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def post(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Platform administrator access is required."},
                status=403,
            )

        amount = parse_positive_amount(request.data.get("amount"))
        idempotency_key = validate_idempotency_key(
            request.data.get("idempotency_key")
        )
        description = request.data.get(
            "description",
            "Platform virtual-credit issuance",
        )

        if amount is None:
            return Response(
                {
                    "detail": (
                        "amount must be positive, with at most "
                        "2 decimal places."
                    )
                },
                status=400,
            )

        if idempotency_key is None:
            return Response(
                {"detail": "A valid UUID idempotency_key is required."},
                status=400,
            )

        if not isinstance(description, str) or len(description) > 255:
            return Response(
                {
                    "detail": (
                        "description must be text of at most 255 characters."
                    )
                },
                status=400,
            )

        try:
            with transaction.atomic():
                if LedgerTransaction.objects.filter(
                    idempotency_key=idempotency_key
                ).exists():
                    return Response(
                        {
                            "detail": (
                                "This request key has already been used."
                            )
                        },
                        status=409,
                    )

                reserve_wallet = Wallet.objects.select_for_update().filter(
                    platform_reserve=True
                ).first()

                if reserve_wallet is None:
                    return Response(
                        {
                            "detail": (
                                "Platform reserve wallet is missing. "
                                "Create it before issuing credits."
                            )
                        },
                        status=409,
                    )

                new_balance = reserve_wallet.available_balance + amount

                if new_balance >= Decimal("10000000000000000"):
                    return Response(
                        {
                            "detail": (
                                "Issuance would exceed the reserve "
                                "wallet's maximum balance."
                            )
                        },
                        status=400,
                    )

                ledger_transaction = LedgerTransaction.objects.create(
                    idempotency_key=idempotency_key,
                    transaction_type=(
                        LedgerTransaction.TransactionType.ISSUANCE
                    ),
                    description=description.strip()
                    or "Platform virtual-credit issuance",
                    created_by=request.user,
                )

                reserve_wallet.available_balance = new_balance
                reserve_wallet.save(
                    update_fields=["available_balance", "updated_at"]
                )

                # Issuance is a minting event, not a wallet-to-wallet transfer.
                LedgerEntry.objects.create(
                    transaction=ledger_transaction,
                    wallet=reserve_wallet,
                    direction=LedgerEntry.Direction.CREDIT,
                    amount=amount,
                )

                return Response({
                    "detail": "Virtual credits issued successfully.",
                    "reference": str(ledger_transaction.reference),
                    "transaction_type": (
                        ledger_transaction.transaction_type
                    ),
                    "amount": str(amount),
                    "reserve_balance": str(
                        reserve_wallet.available_balance
                    ),
                }, status=201)

        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "The issuance could not be recorded. The request "
                        "key may already have been used; check transaction "
                        "history before retrying."
                    )
                },
                status=409,
            )


class PlatformCreditAllocationView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def post(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Platform administrator access is required."},
                status=403,
            )

        raw_account_id = request.data.get("major_account_id")
        amount = parse_positive_amount(request.data.get("amount"))
        idempotency_key = validate_idempotency_key(
            request.data.get("idempotency_key")
        )
        description = request.data.get(
            "description",
            "Platform allocation to major account",
        )

        try:
            account_id = UUID(str(raw_account_id))
        except (ValueError, TypeError, AttributeError):
            return Response(
                {"detail": "A valid major_account_id UUID is required."},
                status=400,
            )

        if amount is None:
            return Response(
                {
                    "detail": (
                        "amount must be positive, with at most "
                        "2 decimal places."
                    )
                },
                status=400,
            )

        if idempotency_key is None:
            return Response(
                {"detail": "A valid UUID idempotency_key is required."},
                status=400,
            )

        if not isinstance(description, str) or len(description) > 255:
            return Response(
                {"detail": "description must be text of at most 255 characters."},
                status=400,
            )

        try:
            with transaction.atomic():
                if LedgerTransaction.objects.filter(
                    idempotency_key=idempotency_key
                ).exists():
                    return Response(
                        {"detail": "This request key has already been used."},
                        status=409,
                    )

                account = MajorAccount.objects.select_for_update().filter(
                    id=account_id
                ).first()

                if account is None:
                    return Response(
                        {"detail": "Major account not found."},
                        status=404,
                    )

                if account.status != MajorAccount.Status.ACTIVE:
                    return Response(
                        {"detail": "Major account is not active."},
                        status=409,
                    )

                reserve_id = Wallet.objects.filter(
                    platform_reserve=True
                ).values_list("id", flat=True).first()

                major_wallet_id = Wallet.objects.filter(
                    major_account=account
                ).values_list("id", flat=True).first()

                if reserve_id is None:
                    return Response(
                        {"detail": "Platform reserve wallet is missing."},
                        status=409,
                    )

                if major_wallet_id is None:
                    return Response(
                        {"detail": "Major account wallet is missing."},
                        status=409,
                    )

                if reserve_id == major_wallet_id:
                    return Response(
                        {"detail": "Invalid wallet configuration."},
                        status=409,
                    )

                # Lock wallets in a consistent order to reduce deadlocks.
                locked_wallets = {
                    wallet.id: wallet
                    for wallet in Wallet.objects.select_for_update()
                    .filter(id__in=[reserve_id, major_wallet_id])
                    .order_by("id")
                }

                reserve_wallet = locked_wallets.get(reserve_id)
                major_wallet = locked_wallets.get(major_wallet_id)

                if reserve_wallet is None or major_wallet is None:
                    return Response(
                        {"detail": "A required wallet could not be locked."},
                        status=409,
                    )

                if reserve_wallet.available_balance < amount:
                    return Response(
                        {
                            "detail": (
                                "Insufficient available credits in "
                                "the platform reserve."
                            )
                        },
                        status=409,
                    )

                maximum_balance = Decimal("10000000000000000")

                if major_wallet.available_balance + amount >= maximum_balance:
                    return Response(
                        {
                            "detail": (
                                "Allocation would exceed the major "
                                "account wallet's maximum balance."
                            )
                        },
                        status=400,
                    )

                ledger_transaction = LedgerTransaction.objects.create(
                    idempotency_key=idempotency_key,
                    transaction_type=(
                        LedgerTransaction.TransactionType.ALLOCATION
                    ),
                    description=(
                        description.strip()
                        or f"Allocation to {account.name}"
                    ),
                    created_by=request.user,
                )

                reserve_wallet.available_balance -= amount
                major_wallet.available_balance += amount

                reserve_wallet.save(
                    update_fields=["available_balance", "updated_at"]
                )
                major_wallet.save(
                    update_fields=["available_balance", "updated_at"]
                )

                # Balanced double-entry transfer.
                LedgerEntry.objects.create(
                    transaction=ledger_transaction,
                    wallet=reserve_wallet,
                    direction=LedgerEntry.Direction.DEBIT,
                    amount=amount,
                )

                LedgerEntry.objects.create(
                    transaction=ledger_transaction,
                    wallet=major_wallet,
                    direction=LedgerEntry.Direction.CREDIT,
                    amount=amount,
                )

                return Response(
                    {
                        "detail": "Virtual credits allocated successfully.",
                        "reference": str(ledger_transaction.reference),
                        "transaction_type": (
                            ledger_transaction.transaction_type
                        ),
                        "major_account_id": str(account.id),
                        "major_account_name": account.name,
                        "amount": str(amount),
                        "reserve_balance": str(
                            reserve_wallet.available_balance
                        ),
                        "major_account_balance": str(
                            major_wallet.available_balance
                        ),
                    },
                    status=201,
                )

        except IntegrityError:
            return Response(
                {
                    "detail": (
                        "The allocation could not be recorded. Check "
                        "transaction history before retrying."
                    )
                },
                status=409,
            )


class PlatformReserveView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def get(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Platform administrator access is required."},
                status=403,
            )

        reserve = Wallet.objects.filter(platform_reserve=True).first()

        if reserve is None:
            return Response(
                {"detail": "Platform reserve wallet is missing."},
                status=409,
            )

        return Response({
            "available_balance": str(reserve.available_balance),
            "reserved_balance": str(reserve.reserved_balance),
        })


class PlatformTransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def get(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Platform administrator access is required."},
                status=403,
            )

        try:
            limit = int(request.query_params.get("limit", "50"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "limit must be a whole number."},
                status=400,
            )

        if limit < 1 or limit > 100:
            return Response(
                {"detail": "limit must be between 1 and 100."},
                status=400,
            )

        transactions = (
            LedgerTransaction.objects
            .select_related("created_by")
            .prefetch_related("entries__wallet")
            .order_by("-created_at")[:limit]
        )

        results = []

        for item in transactions:
            entries = []

            for entry in item.entries.all():
                wallet = entry.wallet

                if wallet.platform_reserve:
                    wallet_name = "Platform reserve"
                elif wallet.major_account_id:
                    wallet_name = (
                        wallet.major_account.name
                        if wallet.major_account_id
                        else "Major account"
                    )
                elif wallet.player_slot_id:
                    wallet_name = f"Player slot {wallet.player_slot_id}"
                else:
                    wallet_name = "Unknown wallet"

                entries.append({
                    "wallet_id": str(wallet.id),
                    "wallet_name": wallet_name,
                    "direction": entry.direction,
                    "amount": str(entry.amount),
                })

            results.append({
                "id": str(item.id),
                "reference": str(item.reference),
                "transaction_type": item.transaction_type,
                "description": item.description,
                "created_by": item.created_by.username,
                "created_at": item.created_at.isoformat(),
                "entries": entries,
            })

        return Response({"transactions": results})

class MajorAccountTransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def get(self, request, major_account_id):
        if not is_major_owner(request.user):
            return Response(
                {"detail": "Major account owner access is required."},
                status=403,
            )

        account = MajorAccount.objects.filter(
            id=major_account_id,
            owner=request.user,
        ).first()

        if account is None:
            return Response(
                {"detail": "Major account not found."},
                status=404,
            )

        try:
            limit = int(request.query_params.get("limit", "50"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "limit must be a whole number."},
                status=400,
            )

        if limit < 1 or limit > 100:
            return Response(
                {"detail": "limit must be between 1 and 100."},
                status=400,
            )

        account_entries = (
            LedgerEntry.objects
            .filter(
                Q(wallet__major_account=account)
                | Q(wallet__player_slot__major_account=account)
            )
            .select_related(
                "wallet__major_account",
                "wallet__player_slot",
            )
        )

        transactions = (
            LedgerTransaction.objects
            .filter(entries__in=account_entries)
            .distinct()
            .select_related("created_by")
            .prefetch_related(
                Prefetch(
                    "entries",
                    queryset=account_entries,
                    to_attr="account_entries",
                )
            )
            .order_by("-created_at")[:limit]
        )

        results = []

        for item in transactions:
            entries = []

            for entry in item.account_entries:
                wallet = entry.wallet

                if wallet.major_account_id:
                    wallet_name = wallet.major_account.name
                elif wallet.player_slot_id:
                    player = wallet.player_slot
                    wallet_name = (
                        f"{account.name} - Player {player.slot_number}"
                    )
                else:
                    continue

                entries.append({
                    "wallet_id": str(wallet.id),
                    "wallet_name": wallet_name,
                    "direction": entry.direction,
                    "amount": str(entry.amount),
                })

            results.append({
                "id": str(item.id),
                "reference": str(item.reference),
                "transaction_type": item.transaction_type,
                "description": item.description,
                "created_by": item.created_by.username,
                "created_at": item.created_at.isoformat(),
                "entries": entries,
            })

        return Response({"transactions": results})