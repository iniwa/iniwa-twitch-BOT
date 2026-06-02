from flask import Blueprint, redirect, url_for, jsonify, request
import re
import threading
import config as c
from services.download import (
    execute_download, bulk_download_task,
    request_cancel_download, delete_vod_file, get_download_progress
)
from services.storage import load_stream_index, save_stream_index
from services.twitch_api import sync_vod_history

bp = Blueprint('vod', __name__)


def _validate_stream_id(stream_id):
    return bool(stream_id and re.match(r'^[a-zA-Z0-9_-]+$', stream_id))


def _vod_admin_required() -> bool:
    """OBS archive 有効時は admin_mode が必要。True = 許可。"""
    conf = c.load_config()
    if not conf.get('obs_archive', {}).get('enabled'):
        return True
    return c.is_admin_mode()


@bp.route('/api/download_progress')
def api_download_progress():
    return jsonify(get_download_progress())


@bp.route('/download_vod/<stream_id>', methods=['POST'])
def download_vod_manual(stream_id):
    if not _validate_stream_id(stream_id):
        return redirect(url_for('analytics.analytics_list'))
    if not _vod_admin_required():
        c.log("[VOD] ブロック: OBS archive 有効時は管理者モードが必要です")
        return redirect(url_for('analytics.analytics_list'))
    conf = c.load_config()
    threading.Thread(target=execute_download, args=(conf, stream_id)).start()
    return redirect(url_for('analytics.analytics_list'))


@bp.route('/download_all_vods', methods=['POST'])
def download_all_vods():
    if not _vod_admin_required():
        c.log("[VOD] ブロック: OBS archive 有効時は管理者モードが必要です")
        return redirect(url_for('analytics.analytics_list'))
    conf = c.load_config()
    threading.Thread(target=bulk_download_task, args=(conf,)).start()
    return redirect(url_for('analytics.analytics_list'))


@bp.route('/cancel_download/<stream_id>', methods=['POST'])
def cancel_download(stream_id):
    if not _validate_stream_id(stream_id):
        return redirect(url_for('analytics.analytics_list'))
    if not _vod_admin_required():
        c.log("[VOD] ブロック: OBS archive 有効時は管理者モードが必要です")
        return redirect(url_for('analytics.analytics_list'))
    request_cancel_download(stream_id)
    return redirect(url_for('analytics.analytics_list'))


@bp.route('/delete_vod/<stream_id>', methods=['POST'])
def delete_vod(stream_id):
    if not _validate_stream_id(stream_id):
        return redirect(url_for('analytics.analytics_list'))
    if not _vod_admin_required():
        c.log("[VOD] ブロック: OBS archive 有効時は管理者モードが必要です")
        return redirect(url_for('analytics.analytics_list'))
    delete_vod_file(stream_id)
    return redirect(url_for('analytics.analytics_list'))


@bp.route('/update_stream_info', methods=['POST'])
def update_stream_info():
    stream_id = request.form.get('stream_id', '')
    new_title = request.form.get('title')
    new_game = request.form.get('game')

    if not _validate_stream_id(stream_id):
        return redirect(url_for('analytics.analytics_list'))

    idx = load_stream_index()
    if stream_id in idx:
        if new_title:
            idx[stream_id]['title'] = new_title
        if new_game:
            idx[stream_id]['game_name'] = new_game
        save_stream_index(idx)
        c.log(f"[EDIT] 配信情報を手動更新しました: {stream_id}")

    return redirect(url_for('analytics.analytics_list'))


@bp.route('/force_sync_history', methods=['POST'])
def force_sync_history():
    conf = c.load_config()
    threading.Thread(target=sync_vod_history, args=(conf, True), daemon=True).start()
    return redirect(url_for('analytics.analytics_list'))
