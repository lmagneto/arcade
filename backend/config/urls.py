from django.contrib import admin
from django.urls import include, path
from config.views import health_check
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import ChangePasswordView, CustomTokenObtainPairView
from game import urls as game_urls

admin.site.site_header = "ARCADE Control Center"
admin.site.site_title = "ARCADE Admin"
admin.site.index_title = "Operations dashboard"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("admin/", admin.site.urls),
    path("api/token/", CustomTokenObtainPairView.as_view(),
        name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "api/accounts/change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),
    path("api/devices/", include("devices.urls")),
    path("api/wallets/", include("wallets.urls")),
    path("api/tenants/", include("tenants.urls")),
    path("api/game/", include(game_urls)),
]