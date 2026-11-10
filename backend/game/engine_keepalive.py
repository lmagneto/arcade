import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime

import requests
from django.conf import settings
from django.db import DatabaseError, connection, transaction
from django.utils import timezone


logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL_SECONDS = 5 * 60
CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 5
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (2, 4)
KEEPALIVE_ADVISORY_LOCK_ID = 724190262

_scheduler_thread: threading.Thread | None = None
_scheduler_lock = threading.Lock()
_last_successful_check: datetime | None = None
_engine_available: bool | None = None


@contextmanager
def _keepalive_slot():
    if connection.vendor != "postgresql":
        yield True
        return

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_xact_lock(%s)",
                [KEEPALIVE_ADVISORY_LOCK_ID],
            )
            acquired = cursor.fetchone()[0]
        yield acquired


def check_engine_health() -> bool | None:
    global _engine_available, _last_successful_check

    engine_url = settings.GAME_ENGINE_URL
    if not engine_url:
        _engine_available = False
        logger.error(
            "Engine health check failed: GAME_ENGINE_URL is not configured."
        )
        return False

    health_url = f"{engine_url.rstrip('/')}/health/"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        request_time = timezone.now()
        started = time.monotonic()

        try:
            with _keepalive_slot() as acquired:
                if not acquired:
                    logger.info(
                        "Engine health check skipped; another backend worker "
                        "owns the keep-alive check."
                    )
                    return None

                logger.info(
                    "Engine health check sent. request_time=%s attempt=%s "
                    "url=%s",
                    request_time.isoformat(),
                    attempt,
                    health_url,
                )
                response = requests.get(
                    health_url,
                    timeout=(
                        CONNECT_TIMEOUT_SECONDS,
                        READ_TIMEOUT_SECONDS,
                    ),
                )
                response_status = response.status_code
        except (requests.RequestException, DatabaseError) as error:
            duration = time.monotonic() - started
            _engine_available = False
            logger.warning(
                "Engine health check failed. request_time=%s attempt=%s "
                "response_status=unavailable duration_seconds=%.3f "
                "availability=unavailable error=%s",
                request_time.isoformat(),
                attempt,
                duration,
                error,
            )
        else:
            duration = time.monotonic() - started
            if response_status == 200:
                _engine_available = True
                _last_successful_check = request_time
                logger.info(
                    "Engine health check successful. request_time=%s "
                    "response_status=%s duration_seconds=%.3f "
                    "last_successful_health_check=%s availability=available",
                    request_time.isoformat(),
                    response_status,
                    duration,
                    _last_successful_check.isoformat(),
                )
                return True

            _engine_available = False
            logger.warning(
                "Engine health check failed. request_time=%s attempt=%s "
                "response_status=%s duration_seconds=%.3f "
                "availability=unavailable",
                request_time.isoformat(),
                attempt,
                response_status,
                duration,
            )

        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])

    logger.error(
        "Engine remains unavailable after %s health-check attempts. "
        "last_successful_health_check=%s availability=unavailable",
        MAX_ATTEMPTS,
        (
            _last_successful_check.isoformat()
            if _last_successful_check is not None
            else "never"
        ),
    )
    return False


def _monitor_loop():
    logger.info(
        "Engine keep-alive scheduler started. interval_seconds=%s "
        "availability=unknown last_successful_health_check=never",
        KEEPALIVE_INTERVAL_SECONDS,
    )
    next_check = time.monotonic()

    while True:
        try:
            check_engine_health()
        except Exception:
            logger.exception(
                "Unexpected engine keep-alive scheduler error; "
                "the backend will continue running."
            )

        next_check += KEEPALIVE_INTERVAL_SECONDS
        time.sleep(max(0, next_check - time.monotonic()))


def start_engine_keepalive():
    global _scheduler_thread

    if not settings.GAME_ENGINE_URL:
        logger.error(
            "Engine keep-alive scheduler was not started: "
            "GAME_ENGINE_URL is not configured."
        )
        return

    with _scheduler_lock:
        if _scheduler_thread is not None and _scheduler_thread.is_alive():
            return

        _scheduler_thread = threading.Thread(
            target=_monitor_loop,
            name="game-engine-keepalive",
            daemon=True,
        )
        _scheduler_thread.start()


def get_engine_keepalive_status() -> dict[str, object]:
    return {
        "available": _engine_available,
        "last_successful_check": _last_successful_check,
    }
