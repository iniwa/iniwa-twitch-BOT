from flask import Blueprint, request, redirect, url_for, jsonify
import requests
import config as c
from services.storage import delete_history_data
from services.twitch_api import force_update_followers

bp = Blueprint('settings', __name__)


@bp.route('/toggle', methods=['POST'])
def toggle():
    conf = c.load_config()
    conf['is_running'] = not conf['is_running']
    c.save_config(conf)
    return redirect(url_for('dashboard.index'))


@bp.route('/toggle_admin_mode', methods=['POST'])
def toggle_admin_mode():
    enabled = c.toggle_admin_mode()
    c.log(f"[Admin] 管理者モード {'有効' if enabled else '無効'}")
    return redirect(request.referrer or url_for('dashboard.index'))


@bp.route('/save_config', methods=['POST'])
def save_config_route():
    conf = c.load_config()

    for k in ['client_id', 'access_token', 'broadcaster_id', 'bot_user_id', 'channel_name']:
        val = request.form.get(k, '').strip()
        conf[k] = val

    broadcaster_token = request.form.get('broadcaster_token', '').strip()
    conf['broadcaster_token'] = broadcaster_token
    conf['debug_mode'] = 'debug_mode' in request.form
    conf['ignore_stream_status'] = 'ignore_stream_status' in request.form
    conf['enable_welcome'] = 'enable_welcome' in request.form
    conf['hide_self_bot'] = 'hide_self_bot' in request.form
    conf['enable_vod_download'] = 'enable_vod_download' in request.form
    conf.pop('vod_download_path', None)
    conf['ignored_users'] = [
        x.strip().lower()
        for x in request.form.get('ignored_users_list', '').replace(',', '\n').replace('\r', '').split('\n')
        if x.strip()
    ]

    obs_archive = conf.setdefault('obs_archive', {})
    obs_archive['enabled'] = 'obs_archive_enabled' in request.form
    obs_archive['secretary_bot_url'] = request.form.get('obs_archive_url', '').strip()
    obs_archive['token'] = request.form.get('obs_archive_token', '').strip()
    try:
        obs_archive['timeout'] = int(request.form.get('obs_archive_timeout', '10').strip() or '10')
    except (ValueError, TypeError):
        obs_archive['timeout'] = 10

    # OBS archive 有効 + admin_mode OFF は自動 VOD DL を強制オフ
    if obs_archive.get('enabled') and not c.is_admin_mode():
        conf['enable_vod_download'] = False

    c.save_config(conf)
    return redirect(url_for('dashboard.index'))


@bp.route('/api/obs_archive/test', methods=['POST'])
def obs_archive_test():
    """保存済み OBS archive 設定で secretary-bot への疎通を確認する。
    OBS 録画の開始・停止は行わない。"""
    conf = c.load_config()
    cfg = conf.get('obs_archive', {})
    if not cfg.get('enabled') or not cfg.get('secretary_bot_url', '').strip():
        return jsonify({"ok": False, "error": "OBS archive が無効か URL 未設定です"})
    url = cfg['secretary_bot_url'].rstrip('/') + '/api/obs/archive-stream/status'
    timeout = int(cfg.get('timeout') or 10)
    headers = {}
    token = cfg.get('token', '').strip()
    if token:
        headers['X-Bot-Token'] = token
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        body = None
        try:
            body = r.json()
        except Exception:
            pass
        return jsonify({"ok": r.ok, "status_code": r.status_code, "body": body})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@bp.route('/debug_update_followers', methods=['POST'])
def debug_update_followers():
    conf = c.load_config()
    msg = force_update_followers(conf)
    c.log(f"Debug Result: {msg}")
    return redirect(url_for('dashboard.index'))


@bp.route('/delete_debug_history', methods=['POST'])
def delete_debug_history():
    delete_history_data('debug_stream')
    return redirect(url_for('dashboard.index'))
