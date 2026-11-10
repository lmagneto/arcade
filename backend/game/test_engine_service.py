import importlib
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase


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

        self.assertEqual(thread_start.call_count, 1)

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
