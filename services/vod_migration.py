"""Twitch VOD ファイルの OBS アーカイブ移行サービス。

stream_index.json から移行候補を取得し、secretary-bot 経由で
Windows Agent に1件ずつ移行依頼を送る。
"""

import os
from datetime import datetime, timedelta, timezone

import requests

from services.storage import ARCHIVE_WAIT_DIR, load_stream_index, save_stream_index

_ALREADY_MIGRATED_STATUSES = {"incoming", "encoded", "preview_ready"}
_JST = timezone(timedelta(hours=9))


def _obs_cfg(conf: dict) -> dict:
    return conf.get("obs_archive") or {}


def _headers(cfg: dict) -> dict:
    token = str(cfg.get("token") or "").strip()
    return {"X-Bot-Token": token} if token else {}


def _resolve_source_path(file_path: str) -> tuple[str | None, list[str]]:
    """Return an existing VOD path, including legacy /app/downloads fallback."""
    checked = []
    if file_path:
        checked.append(file_path)
        if os.path.exists(file_path):
            return file_path, checked

    filename = os.path.basename(file_path or "")
    if filename:
        wait_path = os.path.join(ARCHIVE_WAIT_DIR, filename)
        if wait_path not in checked:
            checked.append(wait_path)
        if os.path.exists(wait_path):
            return wait_path, checked

    return None, checked


def scan_migration_candidates(conf: dict) -> dict:
    """stream_index.json から移行候補を返す。外部呼び出しなし。

    候補条件:
      - vod_status == 'downloaded'
      - file_path が存在する
      - obs_archive_status が incoming/encoded/preview_ready でない
    """
    cfg = _obs_cfg(conf)
    if not cfg.get("enabled") or not str(cfg.get("secretary_bot_url") or "").strip():
        return {
            "ok": False,
            "error": "OBS archive not configured",
            "candidates": [],
            "skipped": [],
        }

    idx = load_stream_index()
    candidates = []
    skipped = []

    for stream_id, entry in idx.items():
        if not isinstance(entry, dict):
            continue

        if entry.get("vod_status") != "downloaded":
            continue

        obs_status = entry.get("obs_archive_status")
        if obs_status in _ALREADY_MIGRATED_STATUSES:
            skipped.append({
                "stream_id": stream_id,
                "reason": "already_in_obs_archive",
                "obs_archive_status": obs_status,
            })
            continue

        file_path = entry.get("file_path")
        if not file_path:
            skipped.append({"stream_id": stream_id, "reason": "no_file_path"})
            continue

        resolved_path, checked_paths = _resolve_source_path(file_path)
        if not resolved_path:
            skipped.append({
                "stream_id": stream_id,
                "reason": "file_missing",
                "file_path": file_path,
                "checked_paths": checked_paths,
            })
            continue

        try:
            file_size = os.path.getsize(resolved_path)
        except OSError:
            file_size = 0

        candidates.append({
            "stream_id": stream_id,
            "source_filename": os.path.basename(resolved_path),
            "source_path": resolved_path,
            "original_file_path": file_path,
            "title": entry.get("title", ""),
            "game_name": entry.get("game_name", ""),
            "start_time": entry.get("start_time"),
            "file_size": file_size,
            "obs_archive_status": obs_status,
        })

    return {"ok": True, "candidates": candidates, "skipped": skipped}


def run_migration_item(
    conf: dict,
    stream_id: str,
    source_filename: str,
    title: str,
    game_name: str,
    start_time: str | None,
    log_fn=None,
) -> dict:
    """secretary-bot に1件の移行を依頼し、成功時に stream_index.json を更新する。"""
    cfg = _obs_cfg(conf)
    base_url = str(cfg.get("secretary_bot_url") or "").rstrip("/")
    if not base_url:
        return {"ok": False, "error": "secretary_bot_url not configured"}

    url = f"{base_url}/api/obs_archive/vod_migration/ingest"
    timeout = int(cfg.get("migration_timeout") or 600)
    channel_name = conf.get("channel_name", "")

    payload = {
        "source_filename": source_filename,
        "stream_id": stream_id,
        "title": title,
        "game_name": game_name,
        "started_at": start_time,
        "channel_name": channel_name,
    }

    try:
        r = requests.post(url, json=payload, headers=_headers(cfg), timeout=timeout)
        body = r.json()
        if not r.ok:
            err = body.get("detail") or body.get("error") or f"HTTP {r.status_code}"
            return {"ok": False, "error": err}
    except Exception as e:
        msg = f"vod_migration ingest error: {e}"
        if log_fn:
            log_fn(f"[VOD_MIGR] {msg}")
        return {"ok": False, "error": str(e)}

    # スキップ (already_encoded 等) も成功扱いで index を更新
    if body.get("skipped"):
        reason = body.get("reason", "")
        if reason == "already_encoded":
            _update_index(stream_id, body.get("target_filename", source_filename), "encoded")
        return {"ok": True, "status": "skipped", "reason": reason, **body}

    if body.get("ok"):
        _update_index(stream_id, body.get("target_filename", source_filename), "incoming")

    return body


def _update_index(stream_id: str, target_filename: str, status: str) -> None:
    now = datetime.now(_JST).isoformat()
    idx = load_stream_index()
    if stream_id not in idx:
        return
    entry = idx[stream_id]
    entry["obs_archive_status"] = status
    entry["obs_migrated_at"] = now
    entry["obs_archive_replay_id"] = f"Streaming/{target_filename}"
    entry.pop("obs_archive_error", None)
    save_stream_index(idx)
