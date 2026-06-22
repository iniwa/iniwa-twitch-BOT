Read AGENTS.md, CLAUDE.md, and this handoff file before implementation.
If implementation would violate constraints or require files outside this handoff, stop and ask before editing.

## Goal

Remove the secretary-bot-specific OBS archive integration from
`iniwa-twitch-bot`, preserve the independent Twitch/VOD features, and expose a
generic read-only current-stream status API for external consumers.

## Background

The integration direction is changing. This project must no longer call or
configure `secretary-bot`. `secretary-bot` will poll this project's generic
stream status API and independently own all OBS recording behavior.

The current project contains:

- `obs_archive` configuration and settings UI
- secretary-bot start/end notification calls
- OBS archive state polling and analytics display
- a connection test
- OBS-specific administrator-mode gating
- downloaded-VOD-to-OBS migration routes, service, and UI

All of those secretary-bot-specific surfaces are to be removed.

The existing Twitch bot, analytics, stream history, and Twitch VOD downloader
must remain functional. Automatic VOD download remains controlled only by
`enable_vod_download` and defaults off.

The approved cross-project decision is recorded in secretary-bot at:

`D:/Git/secretary-bot/docs/decisions/2026-06-22-twitch-stream-status-pull.md`

## Files To Inspect

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `app.py`
- `config.py`
- `routes/dashboard.py`
- `routes/settings.py`
- `routes/analytics.py`
- `routes/vod.py`
- `services/workers.py`
- `services/obs_notifier.py`
- `services/obs_archive_status.py`
- `services/vod_migration.py`
- `templates/base.html`
- `templates/analytics_list.html`
- `templates/partials/_modal_settings.html`
- `docs/decisions/2026-06-01-twitch-obs-archive-recording.md`
- existing tests, if present

## Files To Edit

- `app.py`
- `config.py`
- `routes/`
- `services/`
- `templates/`
- `static/` only where obsolete OBS integration UI assets exist
- `tests/`
- `README.md`
- `docs/`

## Required Behavior

### Generic status API

Add:

```text
GET /api/stream/status
```

Return HTTP 200 with a stable JSON shape.

Live example:

```json
{
  "ok": true,
  "live": true,
  "stream": {
    "id": "123456",
    "title": "stream title",
    "game_name": "Final Fantasy XIV",
    "started_at": "2026-06-22T12:00:00Z",
    "channel_name": "iniwa"
  },
  "checked_at": "2026-06-22T12:00:15Z"
}
```

Offline example:

```json
{
  "ok": true,
  "live": false,
  "stream": null,
  "checked_at": "2026-06-22T12:00:15Z"
}
```

Requirements:

- Report the stream state already held by the worker.
- Do not perform a Twitch API call inside the HTTP request.
- Do not contact secretary-bot.
- Include the current stream id and the latest known title, game, start time,
  and channel name when live.
- Protect shared in-memory state using the project's existing synchronization
  pattern.
- `checked_at` is the response creation time in ISO 8601 UTC.

If the current code does not retain all required live metadata, retain a
minimal in-memory current-stream snapshot when the existing poll worker accepts
a live Twitch response, and clear it when that stream ends.

### Remove secretary-bot integration

Remove:

- `obs_archive` from default config and settings persistence
- Secretary-Bot URL, token, timeout, enabled toggle, and connection-test UI/API
- start/end notification threads and `services/obs_notifier.py`
- post-stream OBS archive status polling and
  `services/obs_archive_status.py`
- OBS archive status fields written by these services
- OBS archive status/refresh display in analytics
- OBS-specific administrator-mode toggle, gating, and UI
- OBS VOD migration routes, service, UI, and JavaScript

Existing stale `obs_archive` keys in user config must be harmless. They may be
ignored rather than destructively removed from runtime config files.

### Preserve Twitch VOD behavior

Preserve:

- manual VOD download
- bulk VOD download
- cancel and delete operations
- VOD history synchronization
- automatic post-stream VOD download controlled by `enable_vod_download`

Remove the OBS/admin-mode dependency from VOD routes and templates. Access and
behavior should return to the original VOD settings and route rules.

`enable_vod_download` must remain independently configurable and default false.

### Documentation

Update project documentation and the 2026-06-01 decision to state:

- this project exposes generic Twitch stream state only
- it has no secretary-bot or OBS recording integration
- OBS archive behavior is owned externally by secretary-bot
- VOD download remains an independent built-in feature

Update the durable rule in `AGENTS.md` consistently. Do not remove unrelated
user changes already present in `AGENTS.md`, `CLAUDE.md`, or `.claudeignore`.

## Constraints

- Preserve Raspberry Pi Docker and linux/arm64 compatibility.
- Do not add OBS WebSocket or media file ownership.
- Do not alter Twitch credentials, real config, `data.db`, downloaded media, or
  runtime data.
- Do not remove or weaken unrelated Twitch bot features.
- Do not add dependencies unless necessary; report before doing so.
- Preserve existing API compatibility outside the explicitly removed
  secretary-bot/OBS surfaces.
- The worktree already contains unrelated changes. Do not revert or include
  them in this task without explicit attribution and approval.

## Non Goals

- Implementing the secretary-bot poller
- Controlling OBS
- Moving or encoding media
- Migrating existing downloaded VOD files
- Deleting stale keys from real config files
- Deployment or external exposure changes

## Verification

- Python syntax checks for changed modules
- Existing project test suite
- Add tests for:
  - live status response
  - offline status response
  - API reads cached worker state without a Twitch HTTP call
  - stream snapshot cleared at end
  - VOD manual/bulk/cancel/delete routes no longer depend on OBS/admin mode
  - automatic VOD download still follows `enable_vod_download`
- Search verifies no runtime import or call remains for:
  - `obs_notifier`
  - `obs_archive_status`
  - `vod_migration`
  - `secretary_bot_url`
- `git diff --check`

Do not modify runtime data or perform a real VOD download.

## Expected Report

- Changed and deleted files
- Summary
- Status API response/state source
- Removed secretary-bot integration surfaces
- Preserved VOD behavior
- Verification results
- Blocked runtime checks
- Confirmation that credentials, runtime config/data, and media were untouched
- Design questions for Codex

## Codex Review Follow-Up

Before this handoff is complete, address these findings:

1. `ignore_stream_status` currently creates the synthetic `debug_stream` and
   writes it to the external stream snapshot. The public status API must report
   actual observed Twitch live state only. Debug/ignore mode may continue to
   drive internal bot behavior, but it must not make
   `GET /api/stream/status` return `live: true`.
2. Turning `is_running` off currently leaves the last stream snapshot cached.
   Clear the external stream snapshot when the bot transitions to or observes
   the disabled state, so consumers do not see a stale live stream
   indefinitely.

Add regression tests for both cases. Preserve the existing internal
`ignore_stream_status` behavior and do not trigger Twitch API calls from the
status endpoint.
