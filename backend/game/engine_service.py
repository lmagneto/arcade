import logging
import os
import threading
import time

import django
from django.core.management import call_command


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger = logging.getLogger(__name__)
engine_ready = threading.Event()


def _run_engine():
    django_initialized = False
    while True:
        try:
            if not django_initialized:
                logger.info("Initializing Django for the game engine.")
                django.setup()
                django_initialized = True
                logger.info("Django initialized for the game engine.")

            if not engine_ready.is_set():
                logger.info("Applying database migrations for the game engine.")
                call_command("migrate", interactive=False)
                engine_ready.set()
                logger.info("Database migrations completed for the game engine.")

            call_command("run_game")
            logger.warning("Game controller exited; retrying in 5 seconds.")
        except Exception:
            engine_ready.clear()
            logger.exception("Game controller failed; retrying in 5 seconds.")

        time.sleep(5)


engine_thread = threading.Thread(
    target=_run_engine,
    name="game-round-controller",
    daemon=True,
)
engine_thread.start()


def application(environ, start_response):
    path = environ.get("PATH_INFO")
    if path == "/health/":
        if engine_thread.is_alive():
            status = "200 OK"
            body = b"Game engine process is running."
        else:
            status = "503 Service Unavailable"
            body = b"Game engine process is not running."
    elif path == "/ready/":
        if engine_ready.is_set() and engine_thread.is_alive():
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
