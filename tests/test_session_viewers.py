"""セッション視聴者スナップショットのテスト。"""

from datetime import datetime

import pytest

import config as c


def test_current_session_viewers_snapshot_is_detached():
    c.current_session_viewers.clear()
    c.current_session_viewers['u1'] = {
        'joined_at': datetime(2026, 7, 7, tzinfo=c.JST),
        'name': 'Alice',
        'login': 'alice',
    }
    try:
        snapshot = c.get_current_session_viewers()
        snapshot['u1']['name'] = 'Changed'
        snapshot['u2'] = {'name': 'Bob'}

        assert c.current_session_viewers['u1']['name'] == 'Alice'
        assert 'u2' not in c.current_session_viewers
    finally:
        c.current_session_viewers.clear()


def test_api_status_reads_session_viewers_snapshot(monkeypatch):
    pytest.importorskip('flask')
    from flask import Flask
    from routes import register_blueprints
    from routes.filters import register_filters

    app = Flask(__name__)
    register_filters(app)
    register_blueprints(app)
    app.config.update(TESTING=True)
    client = app.test_client()

    joined_at = c.get_now()
    snapshot = {
        'u1': {'joined_at': joined_at, 'name': 'Alice', 'login': 'alice'},
    }

    monkeypatch.setattr(c, 'get_current_session_viewers', lambda: snapshot.copy())
    monkeypatch.setattr(c, 'load_config', lambda: {'rules': [], 'current_title': 'Title'})
    monkeypatch.setattr(c, 'load_viewers', lambda: {})

    resp = client.get('/api/status')

    assert resp.status_code == 200
    data = resp.get_json()
    assert data['count'] == 1
    assert data['viewer_count'] == 1
    assert data['viewers'][0]['uid'] == 'u1'