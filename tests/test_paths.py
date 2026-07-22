"""Path configuration tests."""

import os

import config as c
import services.storage as storage


def test_history_paths_are_base_dir_absolute():
    assert os.path.isabs(c.DATA_DIR)
    assert os.path.isabs(c.HISTORY_DIR)
    assert c.HISTORY_DIR == os.path.join(c.DATA_DIR, 'history')
    assert c.STREAM_INDEX_FILE == os.path.join(c.HISTORY_DIR, 'stream_index.json')


def test_storage_uses_configured_stream_index_path(monkeypatch):
    calls = []
    monkeypatch.setattr(storage.os.path, 'exists', lambda path: calls.append(path) or False)

    assert storage.load_stream_index() == {}
    assert calls == [c.STREAM_INDEX_FILE]