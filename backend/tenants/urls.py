from django.urls import path

from tenants.views import (
    PlatformMajorAccountListCreateView,
    ResetMajorOwnerPasswordView,
)

urlpatterns = [
    path(
        "major-accounts/",
        PlatformMajorAccountListCreateView.as_view(),
        name="platform-major-accounts",
    ),
    path(
        "major-accounts/<uuid:major_account_id>/reset-password/",
        ResetMajorOwnerPasswordView.as_view(),
        name="reset-major-owner-password",
    ),
]