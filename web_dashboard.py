"""Web dashboard server for Music IoT LCD Visualizer.

Runs a Flask app in a background thread, serving a real-time dashboard
via Server-Sent Events (SSE).
"""

import json
import os
import threading
import time

from flask import Flask, Response, render_template


class SharedState:
    """Thread-safe container for dashboard state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
            "mode": "MONITOR",
            "track": "",
            "visualizer": [0] * 16,
            "brightness": 0,
            "cpu": 0,
            "ram": 0,
            "time": "--:--",
            "date": "-- ---",
        }

    def update(self, **kwargs):
        with self._lock:
            self._data.update(kwargs)

    def snapshot(self):
        with self._lock:
            return dict(self._data)


def create_shared_state():
    return SharedState()


def create_app(shared_state):
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    app = Flask(__name__, template_folder=template_dir)

    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/api/stream")
    def event_stream():
        def generate():
            while True:
                data = shared_state.snapshot()
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(0.033)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


def start_dashboard(shared_state, port=5050):
    """Start the Flask dashboard in the current thread."""
    app = create_app(shared_state)

    import logging

    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    app.run(host="0.0.0.0", port=port, threaded=True)
