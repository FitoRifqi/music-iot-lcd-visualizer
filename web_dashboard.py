"""Web dashboard server for Music IoT LCD Visualizer.

Runs a Flask app in a background thread, serving a real-time dashboard
via Server-Sent Events (SSE).
"""

import json
import os
import threading
import time

from flask import Flask, Response, render_template

HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "play_history.json")
MAX_HISTORY = 10


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
            "history": [],
            "bpm": 0,
            "artwork_url": "",
        }

    def update(self, **kwargs):
        with self._lock:
            self._data.update(kwargs)

    def add_to_history(self, track: str, played_at: str) -> None:
        """Add a track to play history and persist to disk."""
        with self._lock:
            history = self._data["history"]
            if history and history[0]["track"] == track:
                return
            entry = {"track": track, "played_at": played_at}
            self._data["history"] = [entry] + history[: MAX_HISTORY - 1]
            snapshot = list(self._data["history"])
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def load_history(self) -> None:
        """Load play history from disk (called at startup)."""
        try:
            with open(HISTORY_FILE, encoding="utf-8") as fh:
                history = json.load(fh)
            with self._lock:
                self._data["history"] = history[:MAX_HISTORY]
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    def snapshot(self):
        with self._lock:
            data = dict(self._data)
            data["history"] = list(self._data["history"])
            return data


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
