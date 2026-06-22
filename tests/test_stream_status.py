"""GET /api/stream/status のテスト。

- ライブ / オフラインの安定したレスポンス形状
- エンドポイントが Twitch API を呼ばず、ワーカー保持状態のみを読むこと
"""

import pytest

pytest.importorskip('flask')  # client フィクスチャは flask に依存

import config as c  # noqa: E402


def test_offline_status(client):
    c.clear_current_stream()
    resp = client.get('/api/stream/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['ok'] is True
    assert data['live'] is False
    assert data['stream'] is None
    assert data['checked_at'].endswith('Z')


def test_live_status(client):
    c.set_current_stream({
        'id': '123456',
        'title': 'stream title',
        'game_name': 'Final Fantasy XIV',
        'started_at': '2026-06-22T12:00:00Z',
        'channel_name': 'iniwa',
    })
    try:
        resp = client.get('/api/stream/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['ok'] is True
        assert data['live'] is True
        assert data['stream'] == {
            'id': '123456',
            'title': 'stream title',
            'game_name': 'Final Fantasy XIV',
            'started_at': '2026-06-22T12:00:00Z',
            'channel_name': 'iniwa',
        }
        assert data['checked_at'].endswith('Z')
    finally:
        c.clear_current_stream()


def test_status_reads_cache_without_twitch_call(client, monkeypatch):
    """ステータス取得が Twitch API を一切呼ばないことを保証する。"""
    import services.twitch_api as twitch_api

    def _boom(*args, **kwargs):
        raise AssertionError('status endpoint must not call the Twitch API')

    monkeypatch.setattr(twitch_api, 'get_stream_info', _boom)
    monkeypatch.setattr(twitch_api, 'check_stream_status_and_update', _boom)

    c.set_current_stream({
        'id': 'cached', 'title': 't', 'game_name': 'g',
        'started_at': None, 'channel_name': 'iniwa',
    })
    try:
        resp = client.get('/api/stream/status')
        assert resp.status_code == 200
        assert resp.get_json()['live'] is True
    finally:
        c.clear_current_stream()
