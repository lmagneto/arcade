import logging
import os
import signal
import threading
import time
from datetime import timedelta

import django
import requests
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger = logging.getLogger(__name__)
BACKEND_KEEPALIVE_INTERVAL_SECONDS = 5 * 60
CONTROLLER_HEARTBEAT_TIMEOUT_SECONDS = 30
CONTROLLER_WATCH_INTERVAL_SECONDS = 5
engine_ready = threading.Event()
engine_thread: threading.Thread | None = None
engine_thread_lock = threading.Lock()
watchdog_thread: threading.Thread | None = None
backend_keepalive_thread: threading.Thread | None = None
controller_started_at: float | None = None


def _run_engine():
    global controller_started_at

    django_initialized = False
    while True:
        try:
            if not django_initialized:
                logger.warning("Game engine startup: initializing Django.")
                django.setup()
                django_initialized = True
                logger.warning("Game engine startup: Django initialized.")

            if not engine_ready.is_set():
                logger.warning("Game engine startup: applying database migrations.")
                call_command("migrate", interactive=False)
                logger.warning("Game engine startup: initializing platform.")
                call_command("initialize_platform")
                engine_ready.set()
                logger.warning(
                    "Game engine startup: database and platform initialization "
                    "completed."
                )

            logger.warning("Game engine startup: starting the round controller.")
            controller_started_at = time.monotonic()
            call_command("run_game")
            logger.warning("Game controller exited; retrying in 5 seconds.")
        except Exception:
            engine_ready.clear()
            logger.exception("Game controller failed; retrying in 5 seconds.")

        time.sleep(5)


def _controller_heartbeat_is_stale() -> bool:
    if not engine_ready.is_set() or controller_started_at is None:
        return False

    if (
        time.monotonic() - controller_started_at
        < CONTROLLER_HEARTBEAT_TIMEOUT_SECONDS
    ):
        return False

    from django.db import DatabaseError, close_old_connections
    from game.models import GameEngineHeartbeat

    try:
        close_old_connections()
        heartbeat = GameEngineHeartbeat.objects.filter(pk=1).first()
    except DatabaseError:
        logger.exception("Could not read the game controller heartbeat.")
        return False
    finally:
        close_old_connections()

    return (
        heartbeat is None
        or not heartbeat.is_running
        or timezone.now() - heartbeat.last_heartbeat_at
        > timedelta(seconds=CONTROLLER_HEARTBEAT_TIMEOUT_SECONDS)
    )


def _watch_controller():
    while True:
        time.sleep(CONTROLLER_WATCH_INTERVAL_SECONDS)
        if not _controller_heartbeat_is_stale():
            continue

        logger.critical(
            "Game controller heartbeat has been stale for at least %s "
            "seconds; restarting the Gunicorn worker.",
            CONTROLLER_HEARTBEAT_TIMEOUT_SECONDS,
        )
        os.kill(os.getpid(), signal.SIGTERM)
        return


def _ping_backend():
    backend_url = settings.GAME_BACKEND_URL
    if not backend_url:
        logger.error(
            "Backend keep-alive skipped: GAME_BACKEND_URL is not configured."
        )
        return

    health_url = f"{backend_url.rstrip('/')}/health/"
    try:
        response = requests.get(health_url, timeout=(3, 5))
    except requests.RequestException:
        logger.warning(
            "Backend keep-alive request failed. url=%s",
            health_url,
            exc_info=True,
        )
        return

    if response.status_code == 200:
        logger.info("Backend keep-alive request succeeded. url=%s", health_url)
    else:
        logger.warning(
            "Backend keep-alive request returned HTTP %s. url=%s",
            response.status_code,
            health_url,
        )


def _keep_backend_awake():
    next_check = time.monotonic()
    while True:
        try:
            _ping_backend()
        except Exception:
            logger.exception(
                "Unexpected backend keep-alive error; the game engine "
                "will continue running."
            )

        next_check += BACKEND_KEEPALIVE_INTERVAL_SECONDS
        time.sleep(max(0, next_check - time.monotonic()))


def _ensure_engine_thread():
    global engine_thread, watchdog_thread, backend_keepalive_thread

    with engine_thread_lock:
        if engine_thread is None or not engine_thread.is_alive():
            engine_ready.clear()
            engine_thread = threading.Thread(
                target=_run_engine,
                name="game-round-controller",
                daemon=True,
            )
            engine_thread.start()

        assert engine_thread is not None
        if watchdog_thread is None or not watchdog_thread.is_alive():
            watchdog_thread = threading.Thread(
                target=_watch_controller,
                name="game-controller-watchdog",
                daemon=True,
            )
            watchdog_thread.start()
        if (
            backend_keepalive_thread is None
            or not backend_keepalive_thread.is_alive()
        ):
            backend_keepalive_thread = threading.Thread(
                target=_keep_backend_awake,
                name="game-backend-keepalive",
                daemon=True,
            )
            backend_keepalive_thread.start()
    return engine_thread


def application(environ, start_response):
    path = environ.get("PATH_INFO")
    thread = engine_thread

    if path == "/health/":
        status = "200 OK"
        body = b"Game engine web application is running."
    elif path == "/ready/":
        if (
            engine_ready.is_set()
            and thread is not None
            and thread.is_alive()
        ):
            status = "200 OK"
            body = b"Game engine is ready."
        else:
            status = "503 Service Unavailable"
            body = b"Game engine is not ready."
    else:
        status = "404 Not Found"
        body = b"Not found."

    start_response(
        status,
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


# Start the controller with the WSGI worker, not as a side effect of a
# health-check request. The controller's database advisory lock prevents a
# second process from controlling rounds during overlapping deployments.
_ensure_engine_thread()
