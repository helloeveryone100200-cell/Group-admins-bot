"""
Minimal Flask web server so UptimeRobot can keep the Render service alive.
Runs in a background daemon thread alongside the Telegram bot.
"""
import threading
from flask import Flask
from config import PORT, BOT_NAME, VERSION

app = Flask(__name__)


@app.route("/")
def home():
    return (
        f"<h2>🤖 {BOT_NAME} v{VERSION}</h2>"
        f"<p>Status: <b>Running</b></p>"
    )


@app.route("/health")
def health():
    return {"status": "ok", "bot": BOT_NAME, "version": VERSION}, 200


def run_server():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)


def keep_alive():
    """Start the Flask server in a daemon thread."""
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
