import secrets
import string

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from accounts.permissions import PasswordChangeComplete

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from tenants.models import MajorAccount
from wallets.models import Wallet


def is_platform_admin(user):
    return (
        user.is_authenticated
        and user.is_staff
        and getattr(user, "role", None) == User.Role.PLATFORM_ADMIN
    )


def generate_temporary_password(length=20):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*()-_=+" for c in password)
        ):
            return password


class PlatformMajorAccountListCreateView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def get(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Platform administrator access is required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        accounts = MajorAccount.objects.select_related("owner").order_by("name")
        results = []

        for account in accounts:
            wallet = Wallet.objects.filter(major_account=account).first()
            results.append({
                "id": str(account.id),
                "name": account.name,
                "account_code": str(account.account_code),
                "status": account.status,
                "owner_id": account.owner_id,
                "owner_username": account.owner.username,
                "owner_email": account.owner.email,
                "wallet_balance": str(
                    wallet.available_balance if wallet else "0.00"
                ),
                "created_at": account.created_at.isoformat(),
            })

        return Response({"accounts": results})

    def post(self, request):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Platform administrator access is required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        name = request.data.get("name")
        username = request.data.get("username")
        email = request.data.get("email", "")

        if not isinstance(name, str) or not name.strip():
            return Response(
                {"detail": "A major account name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(name.strip()) > 150:
            return Response(
                {"detail": "Account name must be at most 150 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(username, str) or not username.strip():
            return Response(
                {"detail": "An owner username is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = username.strip()
        if len(username) > 150:
            return Response(
                {"detail": "Username must be at most 150 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username__iexact=username).exists():
            return Response(
                {"detail": "That username is already in use."},
                status=status.HTTP_409_CONFLICT,
            )

        if not isinstance(email, str) or len(email) > 254:
            return Response(
                {"detail": "Email must be text of at most 254 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temporary_password = generate_temporary_password()
        owner = None

        try:
            with transaction.atomic():
                owner = User(
                    username=username,
                    email=email.strip(),
                    role=User.Role.MAJOR_OWNER,
                    is_active=True,
                    must_change_password=True,
                )
                owner.set_password(temporary_password)
                password_validation.validate_password(
                    temporary_password, user=owner
                )
                owner.save()

                account = MajorAccount.objects.create(
                    name=name.strip(),
                    owner=owner,
                )

                Wallet.objects.create(major_account=account)

        except DjangoValidationError as exc:
            return Response(
                {"detail": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            return Response(
                {"detail": "The account could not be created because of a conflicting record."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "detail": "Major account created. Provide the temporary password securely to its owner.",
                "account": {
                    "id": str(account.id),
                    "name": account.name,
                    "account_code": str(account.account_code),
                    "status": account.status,
                    "owner_username": owner.username,
                    "owner_email": owner.email,
                    "wallet_balance": str(account.wallet.available_balance),
                    "must_change_password": owner.must_change_password,
                },
                "temporary_password": temporary_password,
            },
            status=status.HTTP_201_CREATED,
        )


class ResetMajorOwnerPasswordView(APIView):
    permission_classes = [IsAuthenticated, PasswordChangeComplete]

    def post(self, request, major_account_id):
        if not is_platform_admin(request.user):
            return Response(
                {"detail": "Platform administrator access is required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        account = MajorAccount.objects.select_related("owner").filter(
            pk=major_account_id
        ).first()

        if account is None:
            return Response(
                {"detail": "Major account not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        owner = account.owner
        temporary_password = generate_temporary_password()

        try:
            password_validation.validate_password(
                temporary_password, user=owner
            )
        except DjangoValidationError:
            # A randomly generated password may match an owner's attributes.
            # Generate another one rather than weakening validation.
            for _ in range(5):
                temporary_password = generate_temporary_password()
                try:
                    password_validation.validate_password(
                        temporary_password, user=owner
                    )
                    break
                except DjangoValidationError:
                    continue
            else:
                return Response(
                    {"detail": "Could not generate a valid temporary password. Please retry."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        owner.set_password(temporary_password)
        owner.must_change_password = True
        owner.save(update_fields=["password", "must_change_password"])

        return Response(
            {
                "detail": "Temporary password generated. The owner must change it at next login.",
                "owner_username": owner.username,
                "must_change_password": True,
                "temporary_password": temporary_password,
            },
            status=status.HTTP_200_OK,
        )
