# v2 Phase 4B: legacy Flask publication bridge for the read-only pilot

Status: complete (source integration only; rollout remains separately authorized).

## Goal

Expose the already-built v2 read-only Live pilot from the existing production
Flask application at `/v2/live`, `/api/v2/live`, and `/api/v2/health`, without
adding a second process, worker, database, external request, persistent write,
or legacy navigation link.

The current Raspberry Pi audit confirmed that `gunicorn app:app` is healthy and
that `/api/stream/status` is 200, while all pilot routes are 404.  The v2
factory is deliberately separate under `src/`, so its routes are not part of
the legacy app object that gunicorn serves.

## Evidence and scope

- `app.py` builds the one legacy Flask app, registers `routes`, then starts the
  existing workers.  Docker runs `gunicorn ... app:app`.
- `routes/__init__.py` is the one blueprint-registration seam.
- `config.get_current_stream()` returns a lock-protected detached current
  Twitch snapshot.  `routes/dashboard.py:/api/stream/status` proves that this
  state can be read without request-time Twitch/external calls.
- `src/twitchbot/web/live.py` contains only the read-only pilot routes, but
  container Python does not automatically add `/app/src` to `sys.path`.
- The real target was audited read-only only: it is arm64 and healthy; no
  runtime data, credentials, media, configuration contents, Portainer state,
  image pull, restart, or file write was performed.

## Files to inspect

- `AGENTS.md`, `CLAUDE.md`, active/blocked Phase 4A handoff
- `app.py`, `config.py`, `routes/__init__.py`, `routes/dashboard.py`
- `services/workers.py` only for the public snapshot write/clear lifecycle
- `src/twitchbot/application/live.py`, `container.py`, `web/live.py`, template
  and CSS
- focused v2/legacy status/worker tests
- `Dockerfile`, `compose.yaml`, and workflow only to preserve the current
  deployment boundary; do not edit them.

## Files to edit

- `config.py`
- New `routes/v2_pilot.py`
- `routes/__init__.py`
- `src/twitchbot/application/live.py` and `src/twitchbot/web/live.py` only for
  truthful unknown bot intent or collision-free static route behavior
- `src/twitchbot/web/templates/v2/live.html` only if the unknown bot label
  requires it
- New or focused tests: `tests/test_v2_pilot_bridge.py`, and existing v2/live
  or protected snapshot tests only as needed
- New decision/handoff documentation only as required by this handoff

Do not edit `app.py` unless route registration cannot use the existing
`routes.register_blueprints` seam.  Do not edit legacy templates/static,
workers, Docker, compose, workflow, image/deployment settings, runtime data,
credentials, VOD media, or storage mounts.

## Settled design

### One-app bridge

Register the existing v2 `live` Flask blueprint on the existing legacy Flask
app from `routes.register_blueprints`.  Do not call `twitchbot.create_app()` or
create a second Flask app/runtime supervisor.  Attach one inert v2 `Container`
with a bridge provider to `app.extensions["twitchbot.container"]`; this key is
new to the legacy app and the v2 health blueprint is not registered.

Because Docker copies the repository root but does not add `/app/src` to Python
path, the bridge may import the source package as the root-resolvable namespace
`src.twitchbot`.  It must not mutate `sys.path`, add packaging, change
`PYTHONPATH`, or alter Docker/deployment.  Verify a root-Python import smoke.

Give the v2 blueprint a collision-free static URL prefix such as `/v2-static`.
The legacy app already owns `/static`; the pilot CSS must resolve via the v2
blueprint rather than depending on Flask route ordering.

### Read-only legacy snapshot provider

Add `LegacyCurrentStreamLiveProvider` in the root bridge module.  Each
`snapshot()` must call only an injected/default `config.get_current_stream_observation`
function, which takes the existing stream lock and returns detached data plus
the latest observation timestamp.  It must not call `load_config`, any service,
Twitch API, filesystem, database, environment, network, subprocess, media, or
worker control.

- On a valid current snapshot, return `state="live"` with only `id`, title,
  game name, started time, current observation time, and `stale=false`.
- On a cleared snapshot with a recorded observation, return truthful
  `state="offline"` and that clear-observation timestamp.
- Before any stream observation, or for malformed legacy input, return
  `unavailable`/`degraded` with stale truthfulness and no raw input/error.
- Do not synthesize viewer metrics, connection readiness, or bot enabled state.
  Bot intent is unknown (`null`) and bot state/connections are `unavailable`.
- Preserve v2 model allowlists, immutable output, ETag/no-store/GET-only
  behavior, and never expose legacy `channel_name`, private/debug extras, or
  a source/error string.

Add a lock-protected observation timestamp in `config.py`: `set_current_stream`
records an `observed_at` timestamp if absent; `clear_current_stream` records the
clear observation without publishing a stream.  The legacy status endpoint must
continue returning exactly its existing public fields and must never return
`observed_at`.

## Acceptance criteria

- A plain legacy Flask app using `register_blueprints` serves all three v2
  GET routes, CSS at its v2-specific URL, and has no second app/runtime/worker.
- Bridge live/offline/unavailable/degraded behavior uses only lock-protected
  copied memory state and preserves no-request-time Twitch/external calls.
- `GET /api/stream/status` retains its exact schema and cache-only behavior;
  stream end/disabled clears remain visible as non-live in the bridge.
- No request opens config/data/database/media, calls Twitch/OBS/secretary,
  starts a thread, or mutates a legacy/v2 snapshot.  The only new memory write
  is worker-time/explicit clear observation bookkeeping in `config.py`.
- Static assets cannot conflict with legacy `/static` routing.
- v2 bot unknown is shown as unknown, not disabled; v2 API has no connection
  or viewer data that legacy memory does not supply.
- Focused bridge/v2/status/worker tests and the full suite pass in isolated
  venv; compileall and diff check pass; independent final review passes.

## Non-goals

- No navigation flag/link, browser work beyond previously blocked visual QA,
  database/read model, session viewers, live polling, settings/actions,
  Twitch/EventSub/OAuth, imports, data migration, production config, Docker/
  workflow/image update, registry publish, SSH write, restart, Portainer
  action, or deployment.

## Deployment boundary

This handoff ends at tested source code.  A separate explicit publish/deploy
step is required before altering Git history, GHCR image state, Portainer, or
the Raspberry Pi container.  Remote validation after a user-approved rollout
is HTTP header/status and pilot page inspection only; never inspect payloads
that could contain stream/person data without a separate authorization.

## Verification

- isolated focused bridge + v2 live + `test_stream_status.py` + worker snapshot
  tests, then full `tests`
- `python -B -m compileall -q app.py config.py routes services src/twitchbot tests`
- `git diff --check` and root-package import smoke
- one independent final review

## Expected report

- Why the 404 occurred and how the one-app bridge resolves it.
- Exact route/static behavior and snapshot truthfulness boundary.
- Focused/full verification results and browser visual-QA blocker.
- Explicit confirmation that deployment/remote writes remain out of this slice.

## Completion record

- The existing Flask application now registers the v2 blueprint without
  creating a second app, runtime, or worker.
- The bridge reads only the lock-protected, detached in-memory stream
  observation.  It performs no request-time Twitch, network, storage, media,
  database, worker, or configuration I/O.
- `/v2/live`, `/api/v2/live`, `/api/v2/health`, and
  `/v2-static/v2/live.css` are covered on a plain legacy Flask app.  The
  protected legacy stream-status behavior remains covered separately.
- Verification: focused bridge/v2/status/worker suite `59 passed`; full suite
  `243 passed, 2 skipped`; `compileall`, root-package import smoke, and
  `git diff --check` passed.  A final independent review found no material
  issue.
- The earlier Phase 4A browser visual check remains blocked because this
  environment has no browser binding.  It is not a request-time or route
  correctness blocker for this source-only bridge.
- No Git history, image registry, Portainer state, Raspberry Pi container,
  runtime configuration/data, credentials, or media was changed.
