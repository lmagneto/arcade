import os
import threading

import django
from django.core.management import call_command


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _run_engine():
    django.setup()
    call_command("migrate", interactive=False)
    call_command("run_game")


engine_thread = threading.Thread(
    target=_run_engine,
    name="game-round-controller",
    daemon=True,
)
engine_thread.start()


def application(environ, start_response):
    if environ.get("PATH_INFO") == "/health/":
        if engine_thread.is_alive():
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
