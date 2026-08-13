# 00. 現行監査と改善提案

## 1. Audit scope

2026-08-13 時点の repository を read-only で確認した。runtime data、real config、credentials、
viewer/history contents、`data.db`、VOD files、container state は確認していない。

主な根拠:

- entry/config: [`app.py`](../../app.py)、[`config.py`](../../config.py)
- routes: [`routes/`](../../routes)
- background/integration/storage: [`services/`](../../services)
- UI: [`templates/`](../../templates)、[`static/`](../../static)
- regression contracts: [`tests/`](../../tests)
- current operations: [`README.md`](../../README.md)、[`Dockerfile`](../../Dockerfile)、
  [`compose.yaml`](../../compose.yaml)

## 2. Current capability map

| Domain | Current capability | Main implementation |
|---|---|---|
| Live | live/offline、game、viewer count、cached external status | `routes/dashboard.py`, `services/workers.py` |
| Bot/chat | IRC connection、chat receive/send、welcome、automation | `services/irc.py`, `services/twitch_api.py`, `services/workers.py` |
| Audience | session viewers、cumulative record、memo、followers、SO | `routes/viewers.py`, dashboard routes/workers |
| Automation | game-scoped timed rules、minimum comments、order | `routes/rules.py`, worker scheduler |
| Presets | title/game/tags/social tags CRUD/apply | `routes/presets.py` |
| Predictions | presets、start、resolve、cancel | `routes/predictions.py`, `services/predictions.py` |
| Activity | chat/sub/gift/raid/Bits/points/events/logs | IRC accumulator、dashboard status |
| Insights | list/calendar/trends/detail/chart/chat/emotes | `routes/analytics.py`, analytics templates/JS |
| Archive | Twitch VOD sync、manual/bulk/auto、progress/cancel/delete | `routes/vod.py`, `services/download.py` |
| Settings | credentials、Bot flags、debug/follower actions | `routes/settings.py`, settings modal |
| Runtime | 3 daemon threads、gunicorn 1 worker/4 threads | `app.py`, `services/workers.py`, `Dockerfile` |
| Persistence | config/viewers/index JSON、per-stream JSONL | `config.py`, `services/storage.py` |

## 3. Strengths to preserve

### Clear deployment fit

Python/Flask、single container、one gunicorn worker、arm64 image、port `8501`、host networking、
two mount boundaries は、Raspberry Pi での個人運用に対して理解しやすく、過剰な infrastructure を
必要としない。

### Useful feature completeness

配信準備から配信中の viewer/event/prediction、自動 chat、配信後 analytics/VOD まで、一つの
product boundary に必要な機能が既に揃っている。v2 は機能発見から始める必要がなく、task flow と
reliability に集中できる。

### Protected stream snapshot

current stream と current session viewers は lock と detached copy で保護され、tests が live/offline、
request-time Twitch call 禁止、end/disabled clear、debug state 非公開を固定している。これは v2 の
compatibility nucleus としてそのまま残す価値がある。

### Independent VOD boundary

VOD download は OBS/secretary/admin mode から切り離され、manual/automatic flow が project 内で
完結している。`enable_vod_download` の default off と `/app/downloads` boundary は安全な設計である。

### Incremental hardening history

XSS escaping、path validation、locks、graceful shutdown、pagination bounds、Docker non-root、
responsive/accessibility の一部改善が既に入り、危険な旧 integration は削除されている。

## 4. Current problems

### A. UI の目的が混在している

Dashboard は viewer、preset、rule、prediction、monitor、event、log、settings modal を一画面に置く。
一方で analytics page に VOD action が混在する。利用者の「配信前・配信中・配信後」という文脈に
合わせて information priority が変わらず、初見で主要 task が分かりにくい。

Evidence: `templates/dashboard.html`、`templates/partials/*`、`templates/analytics_list.html`。

### B. Interaction/accessibility の基礎が統一されていない

inline `onclick`、絵文字/icon-only button、clickable `<th>`、ARIA のない tabs、inline display で
開閉する modal、focus/escape/return-focus 不在がある。small font、color-only state、overflow-heavy
layout も keyboard/mobile での利用を難しくする。

Evidence: `templates/base.html`, `templates/dashboard.html`, analytics templates, current CSS/JS。

### C. Page/query と Twitch command の境界が弱い

Dashboard page と current-settings query が同期 Twitch API call を行い、timeout まで initial load を
block し得る。query が local state か upstream state かを API 名から判別しづらい。

Evidence: `routes/dashboard.py` の `index`, `/api/current_settings`, `/api/search_games`。

### D. Runtime lifecycle が import side effect

Flask app module import 時に worker が開始する。gunicorn 1 worker では動くが、test/CLI/reloader/
future process model で duplicate start や network side effect を避けにくい。

Evidence: `app.py`, `services/workers.py`。

### E. Global mutable state と責務が分散している

stream ID/game、session viewers、rule execution index、minute counters、logs/events、download progress が
複数 module global と lock に分かれる。ownership と state transition が型/API で表現されず、route と
worker が implementation detail を共有する。

Evidence: `config.py`, `services/workers.py`, `services/download.py`。

### F. JSON persistence が entity 増加に追いつかない

file lock は thread 内の競合を抑えるが、atomic replace/transaction/index/query/schema migration がない。
viewer、stream index、JSONL、VOD state の cross-file update は crash 後に repair が必要になる。
一部の設定 key は `DEFAULT_CONFIG` に明示されず、code reference が実質 schema になっている。

Evidence: `config.py`, `services/storage.py`, `services/download.py`。

### G. Twitch transport と authentication が将来の中心設計になっていない

chat/event ingestion は IRC が中心で、Twitch が新規 chatbot に推奨する EventSub + Chat API の
reconnect/deduplication/scope/token lifecycle が一級概念になっていない。Access token refresh と
feature-level scope readiness も中央管理されていない。さらに Bot/Broadcaster の ID と token は
分けられる一方、操作ごとの credential actor routing と subject validation が明示 model ではない。

Evidence: `services/irc.py`, `services/twitch_api.py`。公式方針は
[Twitch Chat](https://dev.twitch.tv/docs/chat/) と
[IRC migration](https://dev.twitch.tv/docs/chat/irc-migration/)。

### H. Long-running VOD operation が durable job ではない

progress/cancel は process memory、stream index status は JSON であり、restart、concurrent bulk、
phase recovery、operation history が明示 state machine になっていない。

Evidence: `services/download.py`, `services/storage.py`, `routes/vod.py`。

### I. HTTP mutation contract が一貫しない

多くの POST route は HTML form/redirect を中心とし、revision、idempotency、problem response、CSRF、
async job response が統一されていない。Cloudflare/LAN boundary を前提にしても、browser mutation の
defense-in-depth と retry safety は別問題である。

Evidence: `routes/rules.py`, `presets.py`, `predictions.py`, `settings.py`, `viewers.py`, `vod.py`。

### J. Test coverage が protected slice に偏っている

snapshot/VOD gate/path/rule reset の tests は重要だが、Twitch API failures、IRC reconnect、token refresh、
download subprocess、CRUD validation、thread lifecycle、migration、browser journey がほぼ未検証である。

Evidence: `tests/` と [`docs/improvements.md`](../improvements.md)。

## 5. Improvement backlog

| Priority | Improvement | Expected outcome | Main risk |
|---|---|---|---|
| P0 | protected contracts を characterization test 化 | rewrite 中の silent regression を防ぐ | legacy behavior の曖昧さ |
| P0 | side-effect-free app factory/runtime supervisor | duplicate worker、test network を防ぐ | gunicorn lifecycle integration |
| P0 | SQLite + source-preserving importer | transaction、query、migration、job durability | data mapping/rollback |
| P0 | public snapshot dependency firewall | external consumer contract を恒久保護 | accidental adapter coupling |
| P1 | task-oriented IA と design system | 配信中の判断/操作を短縮 | feature discoverability |
| P1 | EventSub + Helix central gateway | reconnect/dedupe/scope/rate limit を標準化 | missing events/auth migration |
| P1 | durable VOD job state machine | restart/cancel/retry を明確化 | filesystem/process races |
| P1 | application commands/queries | route、worker、legacy/v2 の一 write path | temporary adapter complexity |
| P1 | typed settings/credentials separation | safe defaults、secret non-disclosure | re-authorization UX |
| P2 | aggregate cached query APIs | no upstream page blocking、smaller polling | freshness semantics |
| P2 | accessible responsive components | keyboard/mobile/zoom parity | browser verification cost |
| P2 | structured health/operation log | failure location と recovery を明示 | privacy/log retention |
| P3 | comparison analytics/export/retention UI | 配信改善と data control | scope expansion |

## 6. Recommended target by problem

| Current problem | Target design |
|---|---|
| one dense dashboard | six task areas + state-dependent `/live` |
| modal-driven settings | stable settings routes and forms |
| sync API during view | local query/read model + explicit sync command |
| module globals | owner services + immutable snapshots |
| index-based rule state | stable rule IDs + `rule_runtime` table |
| JSON cross-file writes | SQLite transactions + migration report |
| IRC-first | EventSub receive + Helix send + reconciliation |
| memory-only VOD progress | durable archive jobs + restart recovery |
| form-specific errors | versioned JSON API + safe problem details |
| toast/log ambiguity | domain activity + operation result + component health |

## 7. What not to optimize yet

- Multi-channel/multi-user abstractions。
- Generic plugin system。
- Distributed task queue。
- Cloud analytics or external observability stack。
- Full SPA/component framework。
- Automatic deployment。

これらは将来の選択肢を閉じないが、現在の reliability、UI clarity、migration safety より先に
導入すると、Raspberry Pi 運用と verification の負担を増やす。

## 8. Audit conclusion

現行版は「機能が足りない」のではなく、追加された機能を日常 task と failure state に合わせて
再編する段階にある。最小リスクの全面再構築は、stack を全面交換することではなく、
UI、state ownership、persistence、Twitch transport、test boundary を一から定義し直しながら、
deployment と protected behavior を維持することである。
