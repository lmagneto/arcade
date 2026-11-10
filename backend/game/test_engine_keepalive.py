from contextlib import contextmanager
from datetime import datetime
from unittest.mock import Mock, call, patch

import requests
from django.test import SimpleTestCase, override_settings

from game import engine_keepalive


@contextmanager
def acquired_keepalive_slot():
    yield True


@contextmanager
def occupied_keepalive_slot():
    yield False


@override_settings(GAME_ENGINE_URL="https://arcade-game-engine.onrender.com")
class EngineKeepaliveTests(SimpleTestCase):
    def setUp(self):
        engine_keepalive._engine_available = None
        engine_keepalive._last_successful_check = None

    @patch("game.engine_keepalive._keepalive_slot", acquired_keepalive_slot)
    @patch("game.engine_keepalive.requests.get")
    def test_successful_check_uses_existing_health_endpoint_and_timeout(
        self,
        get,
    ):
        get.return_value = Mock(status_code=200)

        with self.assertLogs("game.engine_keepalive", level="INFO") as logs:
            result = engine_keepalive.check_engine_health()

        self.assertTrue(result)
        get.assert_called_once_with(
            "https://arcade-game-engine.onrender.com/health/",
            timeout=(3, 5),
        )
        status = engine_keepalive.get_engine_keepalive_status()
        self.assertTrue(status["available"])
        self.assertIsInstance(status["last_successful_check"], datetime)
        self.assertTrue(
            any("Engine health check successful" in line for line in logs.output)
        )
        self.assertTrue(
            any("last_successful_health_check=" in line for line in logs.output)
        )

    @patch("game.engine_keepalive.time.sleep")
    @patch("game.engine_keepalive._keepalive_slot", acquired_keepalive_slot)
    @patch("game.engine_keepalive.requests.get")
    def test_non_200_response_retries_with_controlled_backoff(
        self,
        get,
        sleep,
    ):
        get.side_effect = [
            Mock(status_code=503),
            Mock(status_code=502),
            Mock(status_code=200),
        ]

        result = engine_keepalive.check_engine_health()

        self.assertTrue(result)
        self.assertEqual(get.call_count, 3)
        self.assertEqual(
            sleep.call_args_list,
            [call(2), call(4)],
        )
        self.assertTrue(engine_keepalive.get_engine_keepalive_status()["available"])

    @patch("game.engine_keepalive.time.sleep")
    @patch("game.engine_keepalive._keepalive_slot", acquired_keepalive_slot)
    @patch("game.engine_keepalive.requests.get")
    def test_request_failures_do_not_escape_or_stop_retrying(
        self,
        get,
        sleep,
    ):
        get.side_effect = requests.ConnectionError("engine unavailable")

        with self.assertLogs("game.engine_keepalive", level="WARNING") as logs:
            result = engine_keepalive.check_engine_health()

        self.assertFalse(result)
        self.assertEqual(get.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(2), call(4)])
        self.assertFalse(engine_keepalive.get_engine_keepalive_status()["available"])
        self.assertTrue(
            any("availability=unavailable" in line for line in logs.output)
        )

    @patch("game.engine_keepalive._keepalive_slot", occupied_keepalive_slot)
    @patch("game.engine_keepalive.requests.get")
    def test_only_one_backend_worker_sends_a_check(self, get):
        result = engine_keepalive.check_engine_health()

        self.assertIsNone(result)
        get.assert_not_called()

    @override_settings(GAME_ENGINE_URL="")
    @patch("game.engine_keepalive.requests.get")
    def test_missing_engine_url_is_reported_without_request(self, get):
        with self.assertLogs("game.engine_keepalive", level="ERROR"):
            result = engine_keepalive.check_engine_health()

        self.assertFalse(result)
        get.assert_not_called()
