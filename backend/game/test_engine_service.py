import importlib
import sys
import threading
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone


class EngineServiceHealthTests(SimpleTestCase):
    def setUp(self):
        with patch.object(threading.Thread, "start") as thread_start:
            if "game.engine_service" in sys.modules:
                self.engine_service = importlib.reload(
                    sys.modules["game.engine_service"]
                )
            else:
                self.engine_service = importlib.import_module(
                    "game.engine_service"
                )

        self.assertEqual(thread_start.call_count, 2)

    def invoke(self, path):
        response = {}

        def start_response(status, headers):
            response["status"] = status
            response["headers"] = headers

        body = self.engine_service.application(
            {"PATH_INFO": path},
            start_response,
        )
        response["body"] = b"".join(body)
        return response

    def test_health_is_lightweight_and_does_not_start_controller(self):
        self.engine_service.engine_thread = SimpleNamespace(
            is_alive=lambda: False
        )

        with patch.object(
            self.engine_service,
            "_ensure_engine_thread",
        ) as ensure_thread:
            response = self.invoke("/health/")

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(
            response["body"],
            b"Game engine web application is running.",
        )
        ensure_thread.assert_not_called()

    def test_ready_reports_controller_readiness_without_starting_it(self):
        self.engine_service.engine_thread = SimpleNamespace(
            is_alive=lambda: True
        )
        self.engine_service.engine_ready.clear()

        with patch.object(
            self.engine_service,
            "_ensure_engine_thread",
        ) as ensure_thread:
            response = self.invoke("/ready/")

        self.assertEqual(response["status"], "503 Service Unavailable")
        ensure_thread.assert_not_called()


class EngineControllerWatchdogTests(SimpleTestCase):
    def setUp(self):
        with patch.object(threading.Thread, "start"):
            self.engine_service = importlib.import_module(
                "game.engine_service"
            )
        self.engine_service.engine_ready.set()
        self.engine_service.controller_started_at = 0

    def tearDown(self):
        self.engine_service.engine_ready.clear()
        self.engine_service.controller_started_at = None

    @patch("game.engine_service.time.monotonic", return_value=10)
    def test_startup_grace_prevents_early_restart(self, _monotonic):
        self.engine_service.controller_started_at = 0

        self.assertFalse(
            self.engine_service._controller_heartbeat_is_stale()
        )

    @patch("game.models.GameEngineHeartbeat.objects.filter")
    @patch("game.engine_service.time.monotonic", return_value=31)
    def test_fresh_heartbeat_keeps_controller_running(
        self,
        _monotonic,
        filter_heartbeat,
    ):
        filter_heartbeat.return_value.first.return_value = SimpleNamespace(
            is_running=True,
            last_heartbeat_at=timezone.now(),
        )

        self.assertFalse(
            self.engine_service._controller_heartbeat_is_stale()
        )

    @patch("game.models.GameEngineHeartbeat.objects.filter")
    @patch("game.engine_service.time.monotonic", return_value=31)
    def test_stale_heartbeat_marks_controller_stalled(
        self,
        _monotonic,
        filter_heartbeat,
    ):
        filter_heartbeat.return_value.first.return_value = SimpleNamespace(
            is_running=True,
            last_heartbeat_at=timezone.now() - timedelta(seconds=31),
        )

        self.assertTrue(
            self.engine_service._controller_heartbeat_is_stale()
        )

    @patch("game.engine_service.os.kill")
    @patch("game.engine_service._controller_heartbeat_is_stale", return_value=True)
    @patch("game.engine_service.time.sleep")
    def test_stalled_controller_restarts_gunicorn_worker(
        self,
        _sleep,
        _stale,
        kill,
    ):
        self.engine_service._watch_controller()

        kill.assert_called_once_with(
            self.engine_service.os.getpid(),
            self.engine_service.signal.SIGTERM,
        )
