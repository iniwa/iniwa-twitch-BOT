"""Contracts for the intentionally read-only v2 Live pilot."""

from __future__ import annotations

import builtins
from pathlib import Path
import socket
import subprocess
import threading

import pytest


def _snapshot(
    state: str = "live",
    *,
    stale: bool = False,
    twitch_state: str | None = None,
    bot_enabled: bool | None = None,
    bot_state: str | None = None,
):
    from twitchbot.application.live import LiveSnapshot, StreamSnapshot

    stream = StreamSnapshot(
        state=state,
        stale=stale,
        observed_at="2026-08-13T10:00:00+09:00",
        id="stream-1" if state in {"live", "degraded"} else None,
        title="配信タイトル" if state in {"live", "degraded"} else None,
        game="テストゲーム" if state in {"live", "degraded"} else None,
        started_at="2026-08-13T09:00:00+09:00" if state in {"live", "degraded"} else None,
        viewer_count=42 if state in {"live", "degraded"} else None,
    )
    enabled = state == "live" if bot_enabled is None else bot_enabled
    return LiveSnapshot(
        stream=stream,
        generated_at="2026-08-13T10:00:01+09:00",
        revision=7,
        bot_enabled=enabled,
        bot_state=bot_state or ("running" if enabled else "stopped"),
        connections={"twitch": twitch_state or ("unavailable" if state == "unavailable" else "healthy")},
        session={"viewers": 42},
    )


def _app(snapshot=None, *, running: bool = False, adapters=None):
    pytest.importorskip("flask")
    from twitchbot import create_app
    from twitchbot.adapters import AdapterSet
    from twitchbot.application.live import StaticLiveProvider
    from twitchbot.container import Container

    container = Container(
        adapters=adapters or AdapterSet.unavailable(),
        live_provider=StaticLiveProvider(snapshot or _snapshot("unavailable")),
    )
    if running:
        container.runtime.start()
    return create_app(container), container


def test_live_snapshot_is_allowlisted_deeply_immutable_and_detached():
    from twitchbot.application.live import LiveSnapshot, StaticLiveProvider, StreamSnapshot, UnavailableLiveProvider

    connections = {"twitch": "healthy"}
    session = {"viewers": 3}
    snapshot = LiveSnapshot(
        stream=StreamSnapshot(state="live", id="stream-1", title="title", game="game"),
        bot_enabled=True,
        bot_state="running",
        connections=connections,
        session=session,
    )
    connections["twitch"] = "degraded"
    session["viewers"] = 99
    assert snapshot.connections["twitch"] == "healthy"
    assert snapshot.session["viewers"] == 3
    with pytest.raises(TypeError):
        snapshot.connections["twitch"] = "degraded"
    with pytest.raises(TypeError):
        snapshot.session["viewers"] = 99
    detached = snapshot.as_dict()
    detached["connections"]["twitch"] = "degraded"
    detached["session"]["viewers"] = 99
    assert snapshot.as_dict()["connections"]["twitch"] == "healthy"
    assert snapshot.as_dict()["session"]["viewers"] == 3
    assert StaticLiveProvider(snapshot).snapshot() is snapshot
    unavailable = UnavailableLiveProvider().snapshot()
    assert unavailable.stream.state == "unavailable"
    assert unavailable.bot_enabled is None


@pytest.mark.parametrize(
    "factory",
    (
        lambda: _snapshot("live").stream.__class__(state="bogus"),
        lambda: _snapshot("live").stream.__class__(state="live", id=""),
        lambda: _snapshot("live").stream.__class__(state="live", title=object()),
        lambda: _snapshot("live").stream.__class__(state="live", viewer_count=True),
        lambda: _snapshot("live").stream.__class__(state="live", started_at="2026-08-13T10:00:00"),
        lambda: __import__("twitchbot.application.live", fromlist=["LiveSnapshot"]).LiveSnapshot(connections={"authorization": "healthy"}),
        lambda: __import__("twitchbot.application.live", fromlist=["LiveSnapshot"]).LiveSnapshot(connections={"twitch": "Bearer synthetic-secret"}),
        lambda: __import__("twitchbot.application.live", fromlist=["LiveSnapshot"]).LiveSnapshot(session={"memo": 1}),
        lambda: __import__("twitchbot.application.live", fromlist=["LiveSnapshot"]).LiveSnapshot(bot_state="debug"),
        lambda: __import__("twitchbot.application.live", fromlist=["LiveSnapshot"]).LiveSnapshot(bot_enabled=False, bot_state="running"),
        lambda: __import__("twitchbot.application.live", fromlist=["StaticLiveProvider"]).StaticLiveProvider("not-a-snapshot"),
    ),
)
def test_live_model_rejects_unsafe_or_invalid_values(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


@pytest.mark.parametrize(
    ("state", "stale", "copy"),
    (
        ("unavailable", False, "配信データを利用できません。"),
        ("offline", False, "現在、配信は行われていません。"),
        ("live", False, "配信タイトル"),
        ("degraded", True, "データが古い可能性があります"),
    ),
)
def test_live_api_and_ssr_truthfully_render_every_state(state, stale, copy):
    app, _ = _app(_snapshot(state, stale=stale))
    client = app.test_client()
    api = client.get("/api/v2/live")
    assert api.status_code == 200
    assert api.headers["Cache-Control"] == "no-store"
    payload = api.get_json()
    assert set(payload) == {"revision", "generated_at", "stream", "bot", "connections", "session"}
    assert payload["stream"]["state"] == state
    assert payload["stream"]["observed_at"].endswith("Z")
    page = client.get("/v2/live")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert copy in body
    assert "読み取り専用" in body
    assert "<form" not in body.lower()


def test_live_api_conditional_etag_and_json_detachment():
    app, _ = _app(_snapshot("live"))
    client = app.test_client()
    first = client.get("/api/v2/live")
    assert first.status_code == 200
    assert first.headers["Cache-Control"] == "no-store"
    etag = first.headers["ETag"]
    payload = first.get_json()
    payload["connections"]["twitch"] = "degraded"
    assert client.get("/api/v2/live").get_json()["connections"]["twitch"] == "healthy"
    conditional = client.get("/api/v2/live", headers={"If-None-Match": etag})
    assert conditional.status_code == 304
    assert conditional.headers["ETag"] == etag


@pytest.mark.parametrize("path", ("/v2/live", "/api/v2/live", "/api/v2/health"))
@pytest.mark.parametrize("method", ("post", "put", "patch", "delete"))
def test_live_pilot_rejects_all_mutating_http_methods(path, method):
    app, _ = _app(_snapshot("live"))
    assert getattr(app.test_client(), method)(path).status_code == 405


@pytest.mark.parametrize(
    ("snapshot", "twitch_state", "running", "expected_state", "expected_code"),
    (
        ("unavailable", "unavailable", False, "stopped", "runtime_stopped"),
        ("unavailable", "unavailable", True, "unavailable", "twitch_unavailable"),
        ("degraded", "healthy", True, "degraded", "live_degraded"),
        ("live", "healthy", True, "healthy", "ok"),
        ("live", "action_required", True, "action_required", "twitch_action_required"),
    ),
)
def test_v2_health_reports_safe_runtime_and_live_states(snapshot, twitch_state, running, expected_state, expected_code):
    app, _ = _app(_snapshot(snapshot, stale=snapshot == "degraded", twitch_state=twitch_state), running=running)
    response = app.test_client().get("/api/v2/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["state"] == expected_state
    assert payload["code"] == expected_code
    assert "token" not in repr(payload).lower()
    assert "secret" not in repr(payload).lower()


def test_legacy_health_endpoints_keep_their_existing_contract():
    app, container = _app(_snapshot("unavailable"))
    client = app.test_client()
    assert client.get("/health/live").get_json() == {"live": True, "ok": True}
    not_ready = client.get("/health/ready")
    assert not_ready.status_code == 503
    assert not_ready.get_json()["ready"] is False
    container.runtime.start()
    assert client.get("/health/ready").status_code == 200


def test_live_json_queries_do_not_reach_legacy_storage_network_or_media(monkeypatch):
    pytest.importorskip("flask")
    from twitchbot.adapters.persistence.sqlite import SQLiteDatabase

    def forbidden(*_args, **_kwargs):
        raise AssertionError("query crossed a forbidden boundary")

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "config" or name.startswith(("routes", "services")):
            raise AssertionError("query imported legacy application code")
        return original_import(name, *args, **kwargs)

    original_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        if str(file).endswith(("config.json", "twitchbot-v2.sqlite3", "vod.mp4")):
            raise AssertionError("query opened forbidden storage")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(SQLiteDatabase, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(threading.Thread, "start", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", guarded_open)
    app, _ = _app(_snapshot("live"), running=True)
    client = app.test_client()
    assert client.get("/api/v2/live").status_code == 200
    assert client.get("/api/v2/health").status_code == 200


@pytest.mark.parametrize(
    ("enabled", "state", "copy"),
    (
        (True, "running", "稼働中（有効）"),
        (False, "stopped", "停止中（無効）"),
        (True, "action_required", "対応が必要（有効）"),
        (False, "unavailable", "利用不可（無効）"),
    ),
)
def test_live_page_truthfully_shows_bot_state_and_enabled_intent(enabled, state, copy):
    app, _ = _app(_snapshot("live", bot_enabled=enabled, bot_state=state))
    assert copy in app.test_client().get("/v2/live").get_data(as_text=True)


def test_v2_health_never_calls_or_echoes_an_injected_adapter():
    from twitchbot.adapters import AdapterSet
    from twitchbot.adapters.null import NullCredentialRegistry, NullMediaAdapter

    calls = 0

    class ExplodingTwitch:
        def status(self):
            nonlocal calls
            calls += 1
            raise AssertionError("health must not call an adapter")

    app, _ = _app(
        _snapshot("live", twitch_state="healthy"),
        running=True,
        adapters=AdapterSet(ExplodingTwitch(), NullMediaAdapter(), NullCredentialRegistry()),
    )
    client = app.test_client()
    assert client.get("/api/v2/live").status_code == 200
    assert client.get("/v2/live").status_code == 200
    payload = client.get("/api/v2/health").get_json()
    assert payload["state"] == "healthy"
    assert payload["components"]["twitch"] == "healthy"
    assert "Bearer synthetic-secret" not in repr(payload)
    assert calls == 0


def test_live_template_and_styles_keep_the_accessible_responsive_shell():
    root = Path(__file__).resolve().parents[1]
    template = (root / "src/twitchbot/web/templates/v2/live.html").read_text(encoding="utf-8")
    stylesheet = (root / "src/twitchbot/web/static/v2/live.css").read_text(encoding="utf-8")
    assert 'class="skip-link"' in template
    assert '<main id="main"' in template
    assert "<h1>" in template
    assert "aria-labelledby=" in template
    assert "onclick=" not in template
    assert "<script" not in template.lower()
    assert "@media(max-width:520px)" in stylesheet
    assert "prefers-reduced-motion" in stylesheet
    assert "forced-colors" in stylesheet
    assert "tabular-nums" in stylesheet
