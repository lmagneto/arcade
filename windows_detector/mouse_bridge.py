import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from detect_mice import detect_external_mice


class MouseHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/mouse-count":
            self.send_error(404)
            return

        try:
            count = len(detect_external_mice())
            payload = {"detected_count": count}
            status = 200
        except Exception:
            payload = {"detail": "Mouse detection unavailable"}
            status = 503

        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8765), MouseHandler)
    print("Mouse bridge running at http://127.0.0.1:8765")
    print("Press Ctrl+C to stop.")
    server.serve_forever()