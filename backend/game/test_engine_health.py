from datetime import timedelta
from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from game.models import GameEngineHeartbeat


@override_settings(GAME_ENGINE_URL="https://arcade-game-engine.onrender.com")
class GameEngineHealthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="engine-health-test",
            password="test-password",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch("game.views.requests.get")
    def test_fresh_heartbeat_reports_running_without_waking_engine(self, get):
        heartbeat = GameEngineHeartbeat.objects.create(
            id=1,
            last_heartbeat_at=timezone.now(),
            is_running=True,
        )

        response = self.client.get("/api/game/engine/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "RUNNING")
        get.assert_not_called()
        heartbeat.refresh_from_db()

    @patch("game.views.requests.get")
    def test_stale_heartbeat_pings_engine_and_reports_starting(self, get):
        GameEngineHeartbeat.objects.create(
            id=1,
            last_heartbeat_at=timezone.now() - timedelta(seconds=30),
            is_running=True,
        )
        get.return_value = Mock(status_code=503)

        response = self.client.get("/api/game/engine/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "STARTING")
        get.assert_called_once_with(
            "https://arcade-game-engine.onrender.com/ready/",
            timeout=3,
        )

    @patch("game.views.requests.get")
    def test_unreachable_engine_is_reported_as_unavailable(self, get):
        get.side_effect = requests.ConnectionError("offline")

        with self.assertLogs("game.views", level="WARNING"):
            response = self.client.get("/api/game/engine/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "UNAVAILABLE")
        self.assertIn("Unable to reach", response.data["detail"])

    @override_settings(GAME_ENGINE_URL="")
    @patch("game.views.requests.get")
    def test_missing_engine_url_reports_unavailable(self, get):
        response = self.client.get("/api/game/engine/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "UNAVAILABLE")
        get.assert_not_called()
