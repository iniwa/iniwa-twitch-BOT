from __future__ import annotations

from flask import Blueprint, current_app, jsonify, make_response, render_template, request

live = Blueprint(
    "v2_live",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/v2-static",
)


def _snapshot():
    return current_app.extensions["twitchbot.container"].live_provider.snapshot()


@live.get("/api/v2/live")
def live_api():
    snapshot = _snapshot()
    response = make_response(jsonify(snapshot.as_dict()))
    response.headers["Cache-Control"] = "no-store"
    response.set_etag(snapshot.etag().strip('"'))
    response.make_conditional(request)
    return response


@live.get("/api/v2/health")
def health_api():
    container = current_app.extensions["twitchbot.container"]
    runtime = container.runtime.snapshot()
    snapshot = container.live_provider.snapshot()
    # This pilot deliberately does not ask an adapter for health: an injected
    # adapter may eventually have I/O behind status().  The provider publishes
    # only the already-observed, allowlisted connection state instead.
    twitch = snapshot.connections.get("twitch", "unavailable")
    if not runtime.ready:
        state, code = "stopped", "runtime_stopped"
    elif snapshot.stream.state == "degraded":
        state, code = "degraded", "live_degraded"
    elif twitch == "healthy":
        state, code = "healthy", "ok"
    elif twitch == "degraded":
        state, code = "degraded", "twitch_degraded"
    elif twitch == "action_required":
        state, code = "action_required", "twitch_action_required"
    elif twitch == "stopped":
        state, code = "stopped", "twitch_stopped"
    else:
        state, code = "unavailable", "twitch_unavailable"
    return jsonify({"state": state, "code": code, "runtime": runtime.as_dict(),
                    "components": {"twitch": twitch, "stream": snapshot.stream.state,
                                   "bot": snapshot.bot_state}})


@live.get("/v2/live")
def live_page():
    snapshot = _snapshot()
    return render_template("v2/live.html", snapshot=snapshot.as_dict())
