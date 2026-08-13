"""Flask factory for the side-effect-free v2 boundary."""

from __future__ import annotations

from typing import Any

from flask import Flask

from ..container import Container
from .health import health
from .live import live


def create_app(container: Container | None = None, **flask_kwargs: Any) -> Flask:
    """Build an isolated app without loading legacy config or starting runtime."""

    application = Flask(__name__, **flask_kwargs)
    owned = container or Container()
    application.extensions["twitchbot.container"] = owned
    application.register_blueprint(health)
    application.register_blueprint(live)
    return application
