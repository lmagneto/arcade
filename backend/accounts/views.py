from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.views import TokenObtainPairView
from accounts.serializers import CustomTokenObtainPairSerializer
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    allow_password_change_required = True

    def post(self, request):
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not isinstance(current_password, str) or not current_password:
            return Response(
                {"detail": "current_password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(new_password, str) or not new_password:
            return Response(
                {"detail": "new_password is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user

        if not user.check_password(current_password):
            return Response(
                {"detail": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            password_validation.validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            return Response(
                {"detail": list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.must_change_password = False
        user.save(
            update_fields=["password", "must_change_password"]
        )

        return Response(
            {
                "detail": "Password changed successfully. Please log in again.",
                "must_change_password": False,
            },
            status=status.HTTP_200_OK,
        )

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
