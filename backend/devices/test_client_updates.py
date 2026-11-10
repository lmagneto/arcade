from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from devices.views import CLIENT_UPDATE_CACHE_SECONDS


@override_settings(GAME_CLIENT_RELEASE_TAG="game-client-v1.0.1")
class ClientUpdateViewTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="client-update-test",
            password="test-password",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.manifest = {
            "version": "1.0.1",
            "download_url": (
                "https://github.com/lmagneto/arcade/releases/download/"
                "game-client-v1.0.1/ARCADE%20Setup%201.0.1.exe"
            ),
            "sha256": "a" * 64,
        }

    @patch("devices.views.cache.set")
    @patch("devices.views.cache.get", return_value=None)
    @patch("devices.views.requests.get")
    def test_returns_authenticated_update_manifest(
        self, get, cache_get, cache_set
    ):
        release_response = Mock()
        release_response.json.return_value = {
            "tag_name": "game-client-v1.0.1",
            "assets": [{
                "name": "client-update.json",
                "browser_download_url": (
                    "https://github.com/lmagneto/arcade/releases/download/"
                    "game-client-v1.0.1/client-update.json"
                ),
            }],
        }
        manifest_response = Mock()
        manifest_response.json.return_value = self.manifest
        get.side_effect = [release_response, manifest_response]

        response = self.client.get(
            "/api/devices/client-update/?version=1.0.0"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["version"], "1.0.1")
        self.assertTrue(response.data["update_available"])
        self.assertEqual(response.data["sha256"], "a" * 64)
        cache_get.assert_called_once_with("arcade-client-update:game-client-v1.0.1")
        cache_set.assert_called_once_with(
            "arcade-client-update:game-client-v1.0.1",
            self.manifest,
            CLIENT_UPDATE_CACHE_SECONDS,
        )

    @patch("devices.views.cache.get")
    def test_does_not_offer_same_or_newer_version(self, cache_get):
        cache_get.return_value = self.manifest

        response = self.client.get(
            "/api/devices/client-update/?version=1.0.1"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["update_available"])

    def test_rejects_missing_or_invalid_client_version(self):
        response = self.client.get("/api/devices/client-update/")

        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/api/devices/client-update/?version=not-a-version"
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(GAME_CLIENT_RELEASE_TAG="")
    def test_reports_unconfigured_release(self):
        response = self.client.get(
            "/api/devices/client-update/?version=1.0.0"
        )

        self.assertEqual(response.status_code, 503)

    def test_requires_device_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(
            "/api/devices/client-update/?version=1.0.0"
        )

        self.assertEqual(response.status_code, 401)

    @patch("devices.views.cache.get", return_value=None)
    @patch("devices.views.requests.get")
    def test_rejects_untrusted_update_url(self, get, _cache_get):
        release_response = Mock()
        release_response.json.return_value = {
            "tag_name": "game-client-v1.0.1",
            "assets": [{
                "name": "client-update.json",
                "browser_download_url": (
                    "https://github.com/lmagneto/arcade/releases/download/"
                    "game-client-v1.0.1/client-update.json"
                ),
            }],
        }
        manifest_response = Mock()
        manifest_response.json.return_value = {
            **self.manifest,
            "download_url": "https://example.com/installer.exe",
        }
        get.side_effect = [release_response, manifest_response]

        response = self.client.get(
            "/api/devices/client-update/?version=1.0.0"
        )

        self.assertEqual(response.status_code, 503)
