"""Side-effect-free v2 package boundary.

The legacy application remains the production entry point.  Flask is imported
only when the factory is called so importing :mod:`twitchbot` is safe in
lightweight tooling and characterization probes.
"""

from __future__ import annotations

from typing import Any


def create_app(*args: Any, **kwargs: Any):
    """Create an isolated v2 Flask application on demand."""

    from .web.app import create_app as _create_app

    return _create_app(*args, **kwargs)


__all__ = ["create_app"]
