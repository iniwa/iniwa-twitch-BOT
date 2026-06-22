"""ワーカーの配信終了処理に関するテスト。

- 配信終了でスナップショットがクリアされる
- 自動 VOD ダウンロードが enable_vod_download にのみ従う
- Bot 停止時に外部スナップショットがクリアされる（回帰）
- ignore_stream_status の debug_stream が外部に公開されない（回帰）
"""

import config as c
import services.workers as workers


def _run_loop_once(monkeypatch, conf):
    """viewer_worker_loop を 1 周だけ実行して抜けるヘルパー。

    ループ前の sleep(5) を 1 回目、ループ内の最初の sleep を 2 回目として数え、
    2 回目で _shutdown_event をセットして 1 イテレーションで終了させる。
    """
    monkeypatch.setattr(workers, 'fix_dangling_states', lambda: None)
    monkeypatch.setattr(workers, 'ensure_directories', lambda: None)
    monkeypatch.setattr(workers, 'sync_vod_history', lambda *a, **k: None)
    monkeypatch.setattr(workers, 'force_update_followers', lambda *a, **k: None)
    monkeypatch.setattr(c, 'load_config', lambda: conf)

    calls = {'n': 0}

    def fake_sleep(_secs):
        calls['n'] += 1
        if calls['n'] >= 2:
            workers._shutdown_event.set()

    monkeypatch.setattr(workers.time, 'sleep', fake_sleep)

    workers._shutdown_event.clear()
    try:
        workers.viewer_worker_loop(conf)
    finally:
        workers._shutdown_event.clear()


class _SyncThread:
    """target を同期実行するスレッドのスタブ。"""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)


def test_snapshot_cleared_at_stream_end(monkeypatch):
    monkeypatch.setattr(workers, 'load_stream_index', lambda: {})
    monkeypatch.setattr(workers, 'save_stream_index', lambda idx: None)

    c.set_current_stream({
        'id': 's1', 'title': 't', 'game_name': 'g',
        'started_at': None, 'channel_name': 'iniwa',
    })
    c.current_stream_id = 's1'

    workers._handle_stream_end({}, 's1')

    assert c.get_current_stream() is None
    assert c.current_stream_id is None


def test_auto_download_follows_flag(monkeypatch):
    monkeypatch.setattr(workers, 'load_stream_index', lambda: {})
    monkeypatch.setattr(workers, 'save_stream_index', lambda idx: None)
    monkeypatch.setattr(workers.threading, 'Thread', _SyncThread)

    calls = []
    monkeypatch.setattr(workers, 'auto_download_task', lambda conf, sid: calls.append(sid))

    workers._handle_stream_end({'enable_vod_download': False}, 's1')
    assert calls == []

    workers._handle_stream_end({'enable_vod_download': True}, 's2')
    assert calls == ['s2']


def test_snapshot_cleared_when_bot_disabled(monkeypatch):
    """is_running が False のとき外部スナップショットをクリアする（回帰）。"""
    c.set_current_stream({
        'id': 'stale', 'title': 't', 'game_name': 'g',
        'started_at': None, 'channel_name': 'iniwa',
    })
    try:
        _run_loop_once(monkeypatch, {'is_running': False})
        assert c.get_current_stream() is None
    finally:
        c.clear_current_stream()


def test_debug_stream_not_published_externally(monkeypatch):
    """ignore_stream_status の debug_stream を外部 API に公開しない（回帰）。

    実際の Twitch はオフラインだが、内部デバッグ挙動はライブとして動く。
    外部スナップショットは offline（None）でなければならない。
    """
    monkeypatch.setattr(workers, 'check_stream_status_and_update',
                        lambda conf: (False, None, False))
    monkeypatch.setattr(workers, 'get_chatters', lambda conf: None)
    monkeypatch.setattr(workers, 'load_stream_index', lambda: {})
    monkeypatch.setattr(workers, 'save_stream_index', lambda idx: None)

    # 古いライブ状態が残っていてもクリアされることを確認するため事前に設定
    c.set_current_stream({
        'id': 'stale', 'title': 't', 'game_name': 'g',
        'started_at': None, 'channel_name': 'iniwa',
    })
    c.current_stream_id = None
    try:
        _run_loop_once(monkeypatch, {
            'is_running': True,
            'ignore_stream_status': True,
            'channel_name': 'iniwa',
        })
        # 内部デバッグ挙動は動作（current_stream_id がデバッグ配信に）
        assert c.current_stream_id == 'debug_stream'
        # 外部スナップショットは公開されない
        assert c.get_current_stream() is None
    finally:
        c.clear_current_stream()
        c.current_stream_id = None
        c.current_game = None
