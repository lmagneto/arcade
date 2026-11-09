from rest_framework.permissions import BasePermission


class PasswordChangeComplete(BasePermission):
    """
    Block ordinary API access until a required password change is complete.
    The password-change endpoint can explicitly opt out of this permission.
    """

    message = "You must change your temporary password before continuing."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if getattr(view, "allow_password_change_required", False):
            return True

        # Device credentials authenticate a DeviceInstallation rather
        # than a normal User. Do not apply the user password flag to them.
        if getattr(request, "auth", None) is not None:
            from devices.models import DeviceInstallation

            if isinstance(request.auth, DeviceInstallation):
                return True

        return not getattr(user, "must_change_password", False)
