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
    django.setup()
    while True:
        try:
            if not engine_ready.is_set():
                call_command("migrate", interactive=False)
                engine_ready.set()

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
    if environ.get("PATH_INFO") == "/health/":
        if engine_ready.is_set() and engine_thread.is_alive():
            status = "200 OK"
            body = b"Game engine is running."
        else:
            status = "503 Service Unavailable"
            body = b"Game engine is not running."
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
