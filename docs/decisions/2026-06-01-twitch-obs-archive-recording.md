# Twitch-to-OBS Archive Recording Compatibility

> **Superseded (2026-06-22).** The push-notification integration direction
> described below is no longer in effect. `iniwa-twitch-bot` no longer calls,
> configures, or displays state from `secretary-bot`, and it contains no OBS
> recording integration. It now exposes only a generic, read-only Twitch stream
> status API (`GET /api/stream/status`); `secretary-bot` polls that API and
> independently owns all OBS archive recording. VOD download remains an
> independent built-in feature controlled solely by `enable_vod_download`
> (default off). See
> `D:/Git/secretary-bot/docs/decisions/2026-06-22-twitch-stream-status-pull.md`.
> The OBS archive layout, filename, metadata, and Windows Agent ownership rules
> below remain valid as `secretary-bot`-owned behavior.

## Context

The local streaming workflow now runs Twitch streaming and OBS recording in
parallel. The normal archive source should be the local OBS recording, so this
project no longer needs to download Twitch VODs for the standard archive path.

This project remains a public Twitch bot and management dashboard, so the VOD
download feature should remain available for administrator/fallback use.

## Decision

Use `iniwa-twitch-bot` as the Twitch stream-state detector and notify
`secretary-bot` when the stream starts or ends.

Responsibility split:

- `iniwa-twitch-bot` owns Twitch live/offline detection and stream metadata.
- `iniwa-twitch-bot` sends archive recording start/end events to
  `secretary-bot`.
- `secretary-bot` and its Windows Agent own OBS recording control, file moves,
  encode, preview generation, and OBS Recording Library state.

Target flow:

```text
Twitch live detected
  -> notify secretary-bot archive-stream start
  -> OBS starts recording, or no-ops if already recording

Twitch offline confirmed
  -> notify secretary-bot archive-stream end
  -> OBS stops recording, or no-ops if already stopped
  -> recording is organized by secretary-bot under Streaming
```

## Recording Stop Rule

On Twitch stream end, the integration should request OBS recording stop whenever
OBS is recording.

Do not try to protect recordings that were already active before the Twitch
integration noticed the stream. For this deployment, Twitch stream end means OBS
archive recording should stop.

The operation should remain idempotent:

- OBS recording active: request stop
- OBS recording inactive: no-op success
- secretary-bot or OBS unavailable: log and surface a visible failure

## VOD Download Mode

Keep Twitch VOD download support, including manual and bulk operations, but
treat it as administrator/fallback functionality when OBS archive recording is
enabled.

Normal local archive mode:

- Do not auto-download Twitch VODs.
- Use secretary-bot / Windows Agent OBS recordings as the archive source.

Administrator/fallback mode:

- Manual VOD history sync remains available.
- Manual VOD download remains available.
- Bulk VOD download remains available where the UI exposes administrator tools.

## Metadata To Send

When notifying `secretary-bot`, include Twitch metadata where available:

- `stream_id`
- `title`
- `game_name`
- `started_at`
- `ended_at` for end events
- `channel_name`
- optional `thumbnail_url`

`secretary-bot` may write this into a sidecar next to the organized recording,
but the media workflow remains owned by `secretary-bot`.

## Constraints

- Preserve Raspberry Pi / arm64 Docker deployment.
- Do not add OBS WebSocket control or media file moves directly to this project.
- Do not store or commit real Twitch credentials.
- Do not delete VOD download code as part of OBS archive integration.
- Keep failure logging practical for repeated stream operation.
