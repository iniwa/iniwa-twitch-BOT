"""Isolated health endpoints for the v2 application boundary."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify


health = Blueprint("v2_health", __name__)


@health.get("/health/live")
def live():
    return jsonify(ok=True, live=True)


@health.get("/health/ready")
def ready():
    snapshot = current_app.extensions["twitchbot.container"].runtime.snapshot()
    payload = {"ok": snapshot.ready, "ready": snapshot.ready, "runtime": snapshot.as_dict()}
    return jsonify(payload), (200 if snapshot.ready else 503)
