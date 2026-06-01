"""secretary-bot OBS アーカイブ録画通知サービス。

Twitch 配信開始・終了時に secretary-bot の /api/obs/archive-stream/* を呼び出す。
失敗はログに残すのみ（配信ワーカーをブロックしない）。
"""

import logging

import requests

log = logging.getLogger(__name__)


def _obs_cfg(conf: dict) -> dict:
    return conf.get("obs_archive") or {}


def _headers(cfg: dict) -> dict:
    token = str(cfg.get("token") or "").strip()
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Bot-Token"] = token
    return h


def notify_stream_start(conf: dict, stream_data: dict, log_fn=None) -> None:
    """secretary-bot に配信開始を通知する。OBS 録画開始を依頼。"""
    cfg = _obs_cfg(conf)
    if not cfg.get("enabled"):
        return
    base_url = str(cfg.get("secretary_bot_url") or "").rstrip("/")
    if not base_url:
        return

    payload = {
        "stream_id": stream_data.get("id"),
        "title": stream_data.get("title"),
        "game_name": stream_data.get("game_name"),
        "started_at": stream_data.get("started_at"),
        "channel_name": conf.get("channel_name", ""),
        "thumbnail_url": stream_data.get("thumbnail_url", ""),
    }

    try:
        r = requests.post(
            f"{base_url}/api/obs/archive-stream/start",
            json=payload,
            headers=_headers(cfg),
            timeout=int(cfg.get("timeout") or 10),
        )
        msg = (
            f'[OBS] Archive stream start notified (stream_id={payload["stream_id"]}, '
            f'status={r.status_code})'
        )
        if not r.ok:
            msg = (
                f'[OBS] Archive stream start failed: {r.status_code} {r.text[:200]}'
            )
        if log_fn:
            log_fn(msg)
        else:
            log.info(msg)
    except Exception as e:
        msg = f"[OBS] Archive stream start error: {e}"
        if log_fn:
            log_fn(msg)
        else:
            log.warning(msg)


def notify_stream_end(conf: dict, stream_data: dict | None, ended_at: str | None = None,
                      log_fn=None) -> None:
    """secretary-bot に配信終了を通知する。OBS 録画停止を依頼。"""
    cfg = _obs_cfg(conf)
    if not cfg.get("enabled"):
        return
    base_url = str(cfg.get("secretary_bot_url") or "").rstrip("/")
    if not base_url:
        return

    payload = {
        "stream_id": stream_data.get("id") if stream_data else None,
        "title": stream_data.get("title") if stream_data else None,
        "game_name": stream_data.get("game_name") if stream_data else None,
        "started_at": stream_data.get("started_at") if stream_data else None,
        "ended_at": ended_at,
        "channel_name": conf.get("channel_name", ""),
    }

    try:
        r = requests.post(
            f"{base_url}/api/obs/archive-stream/end",
            json=payload,
            headers=_headers(cfg),
            timeout=int(cfg.get("timeout") or 10),
        )
        msg = (
            f'[OBS] Archive stream end notified (stream_id={payload["stream_id"]}, '
            f'status={r.status_code})'
        )
        if not r.ok:
            msg = (
                f'[OBS] Archive stream end failed: {r.status_code} {r.text[:200]}'
            )
        if log_fn:
            log_fn(msg)
        else:
            log.info(msg)
    except Exception as e:
        msg = f"[OBS] Archive stream end error: {e}"
        if log_fn:
            log_fn(msg)
        else:
            log.warning(msg)
