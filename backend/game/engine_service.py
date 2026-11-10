import logging
import os
import threading
import time

import django
from django.core.management import call_command


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger = logging.getLogger(__name__)
engine_ready = threading.Event()
engine_thread: threading.Thread | None = None
engine_thread_lock = threading.Lock()


def _run_engine():
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

            call_command("run_game")
            logger.warning("Game controller exited; retrying in 5 seconds.")
        except Exception:
            engine_ready.clear()
            logger.exception("Game controller failed; retrying in 5 seconds.")

        time.sleep(5)


def _ensure_engine_thread():
    global engine_thread

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
