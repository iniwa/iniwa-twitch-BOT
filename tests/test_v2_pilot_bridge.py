"""Production-Flask bridge coverage for the read-only v2 live pilot."""

from datetime import datetime, timezone

import pytest

pytest.importorskip("flask")

import config
from routes.v2_pilot import LegacyCurrentStreamLiveProvider


def test_bridge_provider_translates_live_snapshot_without_private_fields():
    provider = LegacyCurrentStreamLiveProvider(
        lambda: ({
            "id": "stream-1", "title": "公開タイトル", "game_name": "ゲーム",
            "started_at": "2026-08-13T10:00:00Z", "channel_name": "private",
        }, datetime(2026, 8, 13, 10, 1, tzinfo=timezone.utc)),
        clock=lambda: datetime(2026, 8, 13, 10, 2, tzinfo=timezone.utc),
    )

    payload = provider.snapshot().as_dict()
    assert payload["stream"] == {
        "state": "live", "stale": False, "observed_at": "2026-08-13T10:01:00Z",
        "id": "stream-1", "title": "公開タイトル", "game": "ゲーム",
        "started_at": "2026-08-13T10:00:00Z", "viewer_count": None,
    }
    assert payload["bot"] == {"enabled": None, "state": "unavailable"}
    assert payload["connections"] == {}
    assert payload["session"] == {}
    assert payload["generated_at"] == "2026-08-13T10:02:00Z"
    assert "private" not in repr(payload)


@pytest.mark.parametrize(
    ("observation", "state", "stale"),
    (
        ((None, None), "unavailable", False),
        ((None, datetime(2026, 8, 13, tzinfo=timezone.utc)), "offline", False),
        (({"id": ""}, datetime(2026, 8, 13, tzinfo=timezone.utc)), "degraded", True),
        (({"id": "stream"}, "not-a-timestamp"), "degraded", True),
    ),
)
def test_bridge_provider_is_truthful_for_missing_or_malformed_observations(observation, state, stale):
    snapshot = LegacyCurrentStreamLiveProvider(lambda: observation).snapshot()
    assert snapshot.stream.state == state
    assert snapshot.stream.stale is stale
    assert snapshot.bot_enabled is None


def test_bridge_routes_are_registered_on_plain_legacy_app_and_static_is_isolated(app, monkeypatch):
    monkeypatch.setattr(
        config,
        "get_current_stream_observation",
        lambda: (None, datetime(2026, 8, 13, tzinfo=timezone.utc)),
    )
    # The bridge captured the default reader at construction, so create an app
    # with the desired detached memory observation explicitly instead.
    app.extensions["twitchbot.container"].live_provider = LegacyCurrentStreamLiveProvider(
        config.get_current_stream_observation
    )
    client = app.test_client()
    assert client.get("/v2/live").status_code == 200
    assert client.get("/api/v2/live").get_json()["stream"]["state"] == "offline"
    assert client.get("/api/v2/health").status_code == 200
    css = client.get("/v2-static/v2/live.css")
    assert css.status_code == 200
    assert "tabular-nums" in css.get_data(as_text=True)
    assert client.get("/static/v2/live.css").status_code == 404


def test_bridge_default_provider_reads_only_the_current_stream_observation(monkeypatch):
    calls = 0

    def observed():
        nonlocal calls
        calls += 1
        return None, datetime(2026, 8, 13, tzinfo=timezone.utc)

    monkeypatch.setattr(config, "load_config", lambda: pytest.fail("bridge must not load config"))
    provider = LegacyCurrentStreamLiveProvider(observed)
    assert provider.snapshot().stream.state == "offline"
    assert calls == 1


def test_legacy_observation_is_detached_and_clear_is_visible():
    config.set_current_stream({"id": "stream", "title": "title", "game_name": "game"})
    try:
        snapshot, observed = config.get_current_stream_observation()
        snapshot["title"] = "changed"
        assert config.get_current_stream()["title"] == "title"
        assert observed is not None
    finally:
        config.clear_current_stream()
    snapshot, observed = config.get_current_stream_observation()
    assert snapshot is None
    assert observed is not None


def test_bridge_etag_represents_response_generation_time(app):
    ticks = iter((
        datetime(2026, 8, 13, 10, 2, tzinfo=timezone.utc),
        datetime(2026, 8, 13, 10, 3, tzinfo=timezone.utc),
    ))
    app.extensions["twitchbot.container"].live_provider = LegacyCurrentStreamLiveProvider(
        lambda: (None, datetime(2026, 8, 13, 10, 1, tzinfo=timezone.utc)),
        clock=lambda: next(ticks),
    )
    client = app.test_client()
    first = client.get("/api/v2/live")
    second = client.get("/api/v2/live")
    assert first.get_json()["generated_at"] != second.get_json()["generated_at"]
    assert first.headers["ETag"] != second.headers["ETag"]
