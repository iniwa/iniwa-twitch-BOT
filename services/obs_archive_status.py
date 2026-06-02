"""secretary-bot OBS アーカイブ状態ルックアップサービス。

stream_id をキーに secretary-bot API を問い合わせ、結果を stream_index.json に保存する。
"""

import logging
import time

import requests

from services.storage import load_stream_index, save_stream_index

log = logging.getLogger(__name__)

_STATUS_LABELS = {
    "recording": "録画中",
    "incoming": "エンコード待ち",
    "encoded": "保存済",
    "preview_ready": "保存済 / プレビュー可",
    "not_recorded": "未保存",
    "unknown": "確認不可",
}


def _obs_cfg(conf: dict) -> dict:
    return conf.get("obs_archive") or {}


def _headers(cfg: dict) -> dict:
    token = str(cfg.get("token") or "").strip()
    h = {}
    if token:
        h["X-Bot-Token"] = token
    return h


def fetch_archive_status(conf: dict, stream_id: str, log_fn=None) -> dict:
    """secretary-bot に stream_id のアーカイブ状態を問い合わせる。

    Returns dict with at least: ok, status, (error if not ok)
    """
    cfg = _obs_cfg(conf)
    if not cfg.get("enabled") or not str(cfg.get("secretary_bot_url") or "").strip():
        return {"ok": False, "status": "unknown", "error": "OBS archive not configured"}

    base_url = str(cfg["secretary_bot_url"]).rstrip("/")
    url = f"{base_url}/api/obs/archive-stream/{stream_id}/archive"
    timeout = int(cfg.get("timeout") or 10)

    try:
        r = requests.get(url, headers=_headers(cfg), timeout=timeout)
        body = r.json()
        if not r.ok:
            err = body.get("detail") or body.get("error") or f"HTTP {r.status_code}"
            return {"ok": False, "status": "unknown", "error": err}
        return body
    except Exception as e:
        msg = f"obs_archive_status fetch error: {e}"
        if log_fn:
            log_fn(f"[OBS] {msg}")
        else:
            log.warning(msg)
        return {"ok": False, "status": "unknown", "error": str(e)}


def refresh_archive_status(conf: dict, stream_id: str, log_fn=None) -> dict:
    """fetch して stream_index.json を更新し、結果を返す。"""
    result = fetch_archive_status(conf, stream_id, log_fn)
    _save_to_index(stream_id, result)
    return result


def _save_to_index(stream_id: str, result: dict) -> None:
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    now = datetime.now(JST).isoformat()

    idx = load_stream_index()
    if stream_id not in idx:
        return
    entry = idx[stream_id]
    status = result.get("status", "unknown")
    entry["obs_archive_status"] = status
    entry["obs_archive_checked_at"] = now

    replay = result.get("replay") or {}
    if replay.get("replay_id"):
        entry["obs_archive_replay_id"] = f"{replay.get('game', 'Streaming')}/{replay.get('filename', '')}"
    if replay.get("preview_status"):
        entry["obs_archive_preview_status"] = replay["preview_status"]

    if not result.get("ok"):
        entry["obs_archive_error"] = result.get("error", "")
    else:
        entry.pop("obs_archive_error", None)

    save_stream_index(idx)


def poll_archive_status_after_stream_end(
    conf: dict,
    stream_id: str,
    log_fn=None,
    attempts: int = 12,
    interval_sec: int = 30,
) -> None:
    """配信終了後に定期的にアーカイブ状態をポーリングして stream_index を更新する。

    encoded / preview_ready になったら早期終了する。
    """
    for i in range(attempts):
        result = refresh_archive_status(conf, stream_id, log_fn)
        status = result.get("status", "unknown")
        msg = f"[OBS] archive poll {i + 1}/{attempts}: stream_id={stream_id} status={status}"
        if log_fn:
            log_fn(msg)
        else:
            log.info(msg)

        if status in ("encoded", "preview_ready"):
            break

        if i < attempts - 1:
            time.sleep(interval_sec)
