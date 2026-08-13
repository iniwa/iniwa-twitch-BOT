import pytest


def test_runtime_start_stop_are_idempotent():
    from twitchbot.runtime import RuntimeSupervisor

    runtime = RuntimeSupervisor()
    assert runtime.snapshot().as_dict() == {"state": "stopped", "ready": False}
    assert runtime.start().as_dict() == {"state": "running", "ready": True}
    assert runtime.start().as_dict() == {"state": "running", "ready": True}
    assert runtime.stop().as_dict() == {"state": "stopped", "ready": False}
    assert runtime.stop().as_dict() == {"state": "stopped", "ready": False}


def test_v2_health_endpoints_are_isolated():
    pytest.importorskip("flask")
    from twitchbot import create_app

    app = create_app()
    client = app.test_client()
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/live").get_json() == {"live": True, "ok": True}
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.get_json()["ready"] is False

    app.extensions["twitchbot.container"].runtime.start()
    assert client.get("/health/ready").status_code == 200


def test_factory_does_not_start_runtime():
    pytest.importorskip("flask")
    from twitchbot import create_app

    app = create_app()
    assert app.extensions["twitchbot.container"].runtime.snapshot().ready is False
