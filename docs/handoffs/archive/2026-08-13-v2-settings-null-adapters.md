# v2 Phase 1B completion: typed settings and Null adapters

Status: completed on 2026-08-13.

Completion verification: focused v2/settings/Null suite `20 passed`; full legacy and v2 suite `38 passed`; `compileall`, guarded stdlib import/default smoke, and `git diff --check` passed; final independent review found no actionable High/Medium issues.

## Goal

Complete the remaining side-effect-free Phase 1B foundation before SQLite work by adding a strict, credential-free v2 settings schema and deterministic unavailable adapters wired into the v2 dependency container.

## Background

The first Phase 1 slice added the lazy v2 Flask factory, explicit runtime lifecycle, health routes, and protected legacy characterization tests. The rebuild plan also requires a configuration schema and Null adapters. The legacy application remains the production entry point, so this slice must be entirely isolated under `src/twitchbot/` and tests.

## Data sources

- `AGENTS.md`, `CLAUDE.md`
- `docs/rebuild/01-product-requirements.md`
- `docs/rebuild/03-system-architecture.md`
- `docs/rebuild/04-data-and-api.md`
- `docs/rebuild/05-migration-and-delivery.md`
- `docs/rebuild/06-quality-security-operations.md`
- `config.py`, `services/workers.py`, `routes/dashboard.py`, `routes/settings.py`
- Current `src/twitchbot/` and `tests/test_v2_*.py`

## Files to edit

- New `src/twitchbot/settings.py`
- New `src/twitchbot/adapters/__init__.py`
- New `src/twitchbot/adapters/null.py`
- `src/twitchbot/container.py`
- `src/twitchbot/__init__.py` only if safe public exports are useful
- New focused tests under `tests/`
- `tests/test_v2_import_safety.py` if needed to extend the guarded import

Do not edit legacy production code, legacy tests, dependency/build/container/deployment files, or runtime data.

## Settled schema contract

Add an immutable `AppSettings` value object containing only non-secret v2 operational settings:

| Key | Type | Default / validation |
|---|---|---|
| `bot_enabled` | strict bool | `False`; canonical v2 equivalent of legacy `is_running` |
| `welcome_enabled` | strict bool | `False`; canonical v2 equivalent of legacy `enable_welcome` |
| `ignore_stream_status` | strict bool | `False`; retained diagnostic behavior, never public snapshot data |
| `enable_vod_download` | strict bool | explicit `False` |
| `stream_poll_interval_seconds` | strict int | `20`; inclusive `1..300` |
| `metrics_flush_interval_seconds` | strict int | `60`; inclusive `1..3600` |
| `hide_self_bot` | strict bool | `False` |
| `ignored_users` | immutable sequence of strings | empty; at most 100 unique lowercase Twitch-login-style values matching `[a-z0-9_]{1,25}` |

`from_mapping()` may apply defaults for omitted known keys but must reject unknown keys, credential-shaped keys, wrong scalar types, out-of-range integers, duplicate filters, invalid filter values, and oversized filter lists. Do not silently coerce strings/integers/bools or normalize legacy values in this slice. Legacy normalization belongs to the importer.

Validation errors must expose only safe field names and stable error codes. They must not include supplied values. `to_mapping()` must return a detached JSON-compatible mapping and never contain access tokens, refresh tokens, client secrets, or authorization headers.

Channel/account IDs, UI preferences, presets, rules, predictions, and layout are not part of this narrow operational schema; they will receive typed domain/settings models in later slices. Credentials remain entirely separate.

## Settled Null-adapter contract

- Provide immutable readiness/status results with `available=False` and stable code `not_configured`.
- Provide explicit Null Twitch and media adapter placeholders. Requiring either adapter must raise a deterministic typed unavailable error; no fake success.
- Provide a Null credential registry for the `bot` and `broadcaster` roles. Status may expose only role and `not_configured`; resolution must raise a typed unavailable error and must never inspect environment variables or files.
- The Null API must not accept caller-supplied token or subject values.
- Null adapters must not start threads, connect sockets, perform DNS/HTTP, create directories, write files, inspect legacy configuration, or call OBS/secretary/Twitch/media processes.
- Store a typed adapter set and `AppSettings` on each v2 `Container`. Default construction remains fully inert and runtime remains stopped.

## Acceptance criteria

- `AppSettings()` has all settled explicit defaults, including `enable_vod_download is False`.
- Strict valid/invalid mapping tests cover unknown keys, secret-shaped keys, bool-vs-int handling, bounds, filter count/shape/duplicates, and safe error redaction.
- Settings serialization is detached and contains no credential fields.
- Default Container instances do not share mutable state.
- Null adapter/credential status is deterministic and unavailable operations fail explicitly.
- Guarded import tests demonstrate that importing settings, container, and Null adapters causes no thread/network/filesystem mutation and requires no Flask import.
- Existing v2 health/runtime behavior remains intact.
- Root `app.py`, `config.py`, routes, services, Docker, compose, requirements, workflow, mounts, ports, and runtime data are unchanged.
- Focused and full tests pass in an isolated environment.
- A stable self-review and one independent bounded review find no unresolved High/Medium issue.

## Constraints

- Python standard library only; no new dependency or packaging change.
- Use relative imports within `twitchbot`.
- Preserve Python 3.12 and `linux/arm64` compatibility.
- Preserve all unrelated worktree changes.
- Do not read or write secrets, `.env`, `/app/data`, `/app/downloads`, `data.db`, runtime JSON/JSONL, viewer/session/history state, or media.
- Do not connect this schema or adapter set to production yet.

## Non-goals

- No legacy config importer or persistence.
- No SQLite schema or repository yet.
- No real Twitch/EventSub/Helix/media/credential implementation.
- No route/UI/API migration.
- No commit, push, image publication, deployment, or container runtime change.

## Verification

- `python -B -m compileall -q src/twitchbot tests`
- Guarded stdlib import/default-construction smoke.
- Focused settings/Null adapter/v2 tests.
- Full `tests` suite in an isolated temporary environment.
- `git diff --check` and final changed-file inspection.
- Independent bounded review after writer self-review.

## Expected report

- Files and contracts added.
- Focused/full test counts.
- Confirmation of credential redaction, explicit VOD default, inert construction, and unchanged production wiring.
- Any blocked check or remaining Phase 2 prerequisite.
