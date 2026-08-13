import pytest


def test_current_stream_snapshot_is_detached():
    import config as c

    c.set_current_stream({"id": "one", "title": "title"})
    try:
        first = c.get_current_stream()
        first["title"] = "mutated"
        assert c.get_current_stream()["title"] == "title"
    finally:
        c.clear_current_stream()


def test_status_exposes_only_public_stream_fields(request):
    pytest.importorskip("flask")
    client = request.getfixturevalue("client")
    import config as c

    c.set_current_stream(
        {
            "id": "one",
            "title": "title",
            "game_name": "game",
            "started_at": "2026-01-01T00:00:00Z",
            "channel_name": "channel",
            "internal_token": "must-not-leak",
        }
    )
    try:
        response = client.get("/api/stream/status")
        assert response.status_code == 200
        assert set(response.get_json()["stream"]) == {
            "id", "title", "game_name", "started_at", "channel_name"
        }
    finally:
        c.clear_current_stream()


def test_vod_download_is_opt_in_when_flag_absent(monkeypatch):
    import config as c
    import services.workers as workers

    assert c.DEFAULT_CONFIG.get("enable_vod_download", False) is False

    scheduled = []

    class ForbiddenThread:
        def __init__(self, *args, **kwargs):
            scheduled.append((args, kwargs))
            raise AssertionError("automatic VOD download must remain opt-in")

    monkeypatch.setattr(workers, "load_stream_index", lambda: {})
    monkeypatch.setattr(workers, "save_stream_index", lambda _index: None)
    monkeypatch.setattr(workers.c, "log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(workers.threading, "Thread", ForbiddenThread)

    workers._handle_stream_end({}, "absent-flag")
    assert scheduled == []
