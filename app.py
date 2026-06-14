"""Pydashboard 애플리케이션 진입점.

실행:
    python app.py
    PYDASHBOARD_PORT=8800 python app.py
"""

from __future__ import annotations

import os

from flask import Flask, render_template

from pydashboard import config
from pydashboard.api import api


def create_app() -> Flask:
    config.ensure_dirs()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.register_blueprint(api)

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PYDASHBOARD_PORT", "8800"))
    host = os.environ.get("PYDASHBOARD_HOST", "127.0.0.1")
    debug = os.environ.get("PYDASHBOARD_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
