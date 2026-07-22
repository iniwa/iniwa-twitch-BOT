# プログラム改善チェックリスト

コードベースを調査して洗い出した改善候補の一覧。

**運用方法**: 着手したい項目にチェック `[x]` を入れる → Codex が handoff
(`docs/handoffs/`) を作成し、Claude Code (auto モード) が実装する。
handoff を挟むまでもない小粒な項目は Claude Code に直接依頼してもよい。
実装完了した項目は「完了アーカイブ」へ移動する。

- 機能追加・未検証項目はこのファイルの対象外 (`docs/issues.md` 等で管理)。
- 優先度: **高** = 稼働中の安定性に直結 / **中** = 保守性・性能 / **低** = 任意。

---

## 1. 安定性 (常駐ワーカー・スレッド)

## 2. 保守性・構造

## 3. 性能・応答性

- [ ] **【低】ダッシュボード表示時の同期 Twitch API 呼び出しを避ける**
  - 現状: `routes/dashboard.py:200` (`index`) が `get_current_prediction`
    を同期呼び出しし、Twitch API のタイムアウト (10 秒) までページ表示が
    ブロックされ得る。`/api/current_settings` (`dashboard.py:270`) も同様。
  - 対応案: 予想状態をワーカー側キャッシュまたはフロントの遅延フェッチ
    (`/api/...` ポーリング) に寄せる。
  - 制約: 予想カードの表示内容・操作フローを変えない。

## 4. テスト

- [ ] **【中】中核フローのテストカバレッジを引き上げる**
  - 現状: カバレッジ全体 23% (2026-07-07 計測、pytest-cov)。特に
    `services/irc.py` 6%、`services/twitch_api.py` 9%、
    `services/download.py` 12%、`services/storage.py` 15%。
    テストは 12 件 (flask 導入環境で全パス)。
  - 対応案: 純関数に近い箇所から追加する — `parse_tags` /
    `handle_privmsg` / `handle_usernotice` (irc.py)、
    `fix_dangling_states` / `sanitize_filename` (storage.py)、
    `_find_video_url` (download.py、requests はモック)。
  - 制約: 計測ツール (pytest-cov) はローカル install のみ。
    requirements.txt / CI には追加しない。

## 5. 見送り (現方針では対応しない)

- [ ] **【低】全 POST エンドポイントへの認証・CSRF 保護**
  - ローカルネットワーク専用 + Cloudflare Tunnel 側で認証済みのため
    不要と判断 (利用者メモ)。外部公開形態が変わる場合は再評価する。

---

## 完了アーカイブ

### 2026-07-07: Codex implementation batch

- [done] `shutdown_workers()` wired for process exit and VOD route thread daemon flags made consistent.
  Verification: `python -m py_compile app.py routes\vod.py services\workers.py`; `python -m pytest tests/test_vod_routes.py tests/test_workers_snapshot.py -q` (5 passed, 1 skipped).
- [done] `current_session_viewers` dictionary iteration race fixed.
  Verification: `python -m pytest tests/test_session_viewers.py tests/test_stream_status.py -q` (1 passed, 2 skipped; Flask unavailable tests skipped).
- [done] viewers.json / stream_index.json read-modify-write lock update.
  Verification: `python -m py_compile config.py routes\dashboard.py routes\vod.py services\twitch_api.py services\workers.py services\download.py`; `python -m pytest tests/test_workers_snapshot.py tests/test_vod_routes.py tests/test_session_viewers.py -q` (5 passed, 2 skipped).
- [done] Offline `current_minute_stats` accumulation fixed.
  Verification: `python -m py_compile services\workers.py tests\test_workers_snapshot.py`; `python -m pytest tests/test_workers_snapshot.py -q` (5 passed).
- [done] Rule execution state index drift fixed.
  Verification: `python -m py_compile config.py routes\rules.py tests\test_rules_state.py`; `python -m pytest tests/test_rules_state.py -q` (1 passed).
- [done] `data.db` removed from Git tracking while preserving the local file.
  Verification: `git ls-files data.db` returned no tracked file; `Get-ChildItem data.db` confirmed the local file remains.
- [done] `data/history/...` relative paths unified through `config.HISTORY_DIR` / `config.STREAM_INDEX_FILE`.
  Verification: `python -m py_compile config.py services\storage.py services\workers.py routes\analytics.py tests\test_paths.py`; `python -m pytest tests/test_paths.py -q` (2 passed).
- [done] `analytics.py` stream_index direct reads unified through `services.storage.load_stream_index()`.
  Verification: `python -m py_compile routes\analytics.py`; `rg` confirmed no direct stream_index file open remains in `routes/analytics.py`.

### 2026-06 以前: Gemini 産コードレビュー起点の改善 (旧チェックリストから移行)

検証: 旧形式のため個別記録なし。コミット範囲: `6e1e907` 前後まで。

- ✅ XSS 対策 → `escHtml()` 適用・`data-*` 属性方式へ統一
- ✅ パストラバーサル対策 → `stream_id` バリデーション (`_validate_stream_id`)
- ✅ 入力バリデーション → routes 全体の型・長さチェック、トークン形式チェック
- ✅ gunicorn 導入・起動時エラーハンドリング (`app.py`)
- ✅ エラーハンドリング統一 (predictions / presets / twitch_api)
- ✅ スレッド安全性 → `raids` ディープコピー、ロック順序、index 読み書き競合の主要部
- ✅ グレースフルシャットダウン → `_shutdown_event` 導入 (※配線は §2 に残項目あり)
- ✅ I/O 最適化 → IRC 視聴者更新のバッチ化、フォロワー同期のロック時間短縮
- ✅ フロントエンド → `DocumentFragment` 化、重複レンダラー統一、`setTimeout` チェーン化
- ✅ API 効率 → ページネーション上限 (`MAX_PAGINATION_PAGES`)、`API_TIMEOUT` 定数化
- ✅ Docker → python:3.12-slim、HEALTHCHECK、UID/GID の ARG 化
- ✅ 依存 → requirements.txt バージョンピン、.dockerignore / .gitignore 整備
- ✅ コード品質 → 無視ユーザーフィルタ共通化、datetime パース統一、ポート/パス/間隔の設定化、絵文字ログ除去
- ✅ フロント構造 → JS モジュール化、CSS カラー変数統一
- ✅ UX/A11y → aria-live、`<a>` 化、プログレスバーのテキストラベル、カレンダーのモバイル対応
