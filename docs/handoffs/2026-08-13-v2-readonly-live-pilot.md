# v2 Phase 4A: read-only Live control-room pilot

Status: blocked — implementation, automated verification, and final independent review complete; browser visual validation awaits an available Browser binding.

## Goal

Build the first visible v2 surface: an isolated, server-rendered `/v2/live`
control-room preview plus permanent read-only `GET /api/v2/live` and
`GET /api/v2/health` query endpoints.  It must render the designed offline,
live, degraded, and unavailable states from explicitly injected immutable
snapshots, without connecting to Twitch, legacy globals, a default database,
or any runtime data.

This is a UI/query pilot, not a production cutover.  The legacy dashboard
remains the sole persistent writer and no production navigation link is added.

## Background and evidence

- `docs/rebuild/02-information-architecture-and-ui.md` sections 1–5 and
  13–15 define the Calm Control Room, `/live` priority, responsive/accessibility
  requirements, and state-specific display.
- `docs/rebuild/03-system-architecture.md` sections 9–13 require side-effect
  free factories, local query-only reads, and component health without secrets.
- `docs/rebuild/04-data-and-api.md` section 10 defines `/api/v2/live` and
  `/api/v2/health` as versioned read queries; the live aggregate is a memory
  snapshot and supports ETag.
- `docs/rebuild/05-migration-and-delivery.md` Phase 4 limits v2 pages to
  `/v2/*`, forbids persistent mutation, requires freshness visibility, and
  keeps legacy as the only writer.
- Current v2 factory is isolated in `src/twitchbot/web/app.py`; it registers
  only health routes and has no database/Twitch/legacy integration.

## Files to inspect

- `AGENTS.md`, `CLAUDE.md`
- the four rebuild documents above
- `src/twitchbot/{container.py,runtime.py,adapters/null.py,web/app.py,web/health.py}`
- current v2 application records and v2 tests
- legacy route/tests only for the protected `/api/stream/status` contract;
  do not access any runtime source data.

## Files to edit

- New `src/twitchbot/application/live.py` and its export in
  `src/twitchbot/application/__init__.py`
- `src/twitchbot/container.py`
- New `src/twitchbot/web/live.py`
- `src/twitchbot/web/app.py`
- New `src/twitchbot/web/templates/v2/live.html`
- New `src/twitchbot/web/static/v2/live.css`
- New focused `tests/test_v2_live_pilot.py`
- `tests/test_v2_import_safety.py` only if needed to guard the new module

Do not change legacy routes/templates/static assets, the production entrypoint,
runtime/worker behavior, migrations/repositories/importer, credentials,
runtime data, VOD media, Docker, dependencies, deployment, or existing health
endpoint semantics.

## Settled design

### Dependency boundary

Add an immutable application-level live snapshot model and a small read-only
provider protocol.  The provider returns only already-observed data.  Its
default implementation returns an explicit `unavailable` snapshot and does not
open a database, read environment/configuration, or start anything.  A static
provider may be injected by tests and later by a reconciler/temporary legacy
snapshot adapter, but this slice must not implement that adapter or any writer.

Add this provider as an explicit `Container` dependency.  Keep the factory
side-effect free and preserve the current null adapters and runtime lifecycle.

The snapshot/API shape must be immutable and safe:

- stream state: `unavailable | offline | live | degraded`, a `stale` flag,
  observed/generated UTC timestamps, revision, and optional stream metadata
  (`id`, title, game, started time, viewer count);
- bot enabled/state, connection state codes, and compact session counters only;
- no credentials, tokens, memo, viewer identity/list, raw chat/event text,
  local path, database path, or internal/debug fields;
- no mutable nested object escapes; timestamps are canonical UTC strings in
  output; invalid/non-finite/naive values fail closed in the model/provider.

`GET /api/v2/live` serializes only this detached snapshot, sets `Cache-Control:
no-store`, and exposes a stable ETag based on content/revision rather than
response generation time.  Matching `If-None-Match` returns 304.  It must
perform no Twitch/OBS/secretary/database/legacy/config/media/network call.

### Health query

Add `GET /api/v2/health` as a safe UI health query.  It derives component state
only from `RuntimeSupervisor`, the null adapter availability/status, and the
live snapshot state; it never resolves credentials or opens a database.  It
may report `healthy`, `stopped`, `degraded`, `action_required`, or `unavailable`
with a stable message code, but no secret/error value.  Keep `/health/live`
and `/health/ready` unchanged; the latter's present 200/503 behavior remains
the container readiness contract.

### SSR pilot

Register a separate v2 blueprint with only these three `GET` routes:

- `/v2/live` — server-rendered preview page;
- `/api/v2/live` — JSON live aggregate;
- `/api/v2/health` — JSON component health.

The page uses the API model server-side, is truthful about unavailable/stale
data, and contains no form, mutation action, inline handler, inline script,
or polling.  It is intentionally not linked from legacy navigation yet.

Use a compact Calm Control Room shell: skip link, header preview/read-only
label, textual state indicator, observed/freshness message, one primary live
state panel, and global component-health list.  Japanese copy is preferred.
Use semantic landmarks, one `h1`, descriptive labels in addition to color,
`aria-current="page"`, tabular numeric styling, system Japanese fonts, responsive
single-column behavior at narrow widths, `prefers-reduced-motion`, and
forced-colors-safe tokens.  Default/unavailable must say data is unavailable,
not render made-up zeros.

## Acceptance criteria

- v2 imports/factory/constructor remain inert; no default DB or source file is
  opened or created, and no legacy module, network, thread, subprocess, or
  runtime start is introduced.
- `GET /api/v2/live` returns a safe detached snapshot, never calls an external
  service, supports conditional ETag 304, and represents each configured state
  truthfully.
- `GET /api/v2/health` reveals no credential values and correctly reflects
  stopped/running runtime and unavailable adapters; old health endpoints retain
  their exact behavior.
- `/v2/live` renders unavailable and injected live/degraded examples with the
  required semantic/accessibility structure and without POST-capable controls.
- `POST`, `PUT`, `PATCH`, and `DELETE` under these pilot paths return 405.
- Protected legacy `/api/stream/status` remains cache-only/no-request-time
  Twitch and its existing tests keep passing.
- Browser visual verification checks desktop and 320px responsive rendering
  from synthetic injected data; no user browser data is accessed.
- Focused and full tests pass in the isolated venv; `compileall`, `git diff
  --check`, and one independent final review pass.

## Non-goals

- No `/live` or `/` cutover, pilot feature flag/navigation modification,
  temporary legacy snapshot adapter, database/read-model integration, current
  viewer list, activity, preset/rule/prediction UI, live polling, commands,
  OAuth/Twitch/EventSub work, migration/import action, or production data use.
- No SPA framework, external CSS/JS/CDN, assets, dependency, container, CI,
  deployment, or runtime change.

## Verification

- `python -B -m compileall -q src/twitchbot tests`
- Focused `tests/test_v2_live_pilot.py` plus v2 import/runtime/settings/persistence
  and legacy status contract tests in the isolated venv
- full `tests` suite in that venv and `git diff --check`
- local synthetic Flask browser visual check at desktop and 320px only
- one independent final review after writer self-review

## Expected report

- Snapshot/provider boundary and v2 GET-only route behavior.
- How the UI expresses unavailable, live, and degraded/freshness states.
- Focused/full test results and browser check.
- Explicit confirmation that legacy/prod/data/credentials/media/deployment were
  not changed, and remaining adapter/runtime/cutover work.

## Independent-review correction (2026-08-13)

The first implementation passed its initial tests but an independent review
found that the live query boundary was not sufficiently immutable or
allowlisted.  Keep this correction inside the existing Phase 4A owned files;
do not add adapters, databases, runtime wiring, or commands.

- Store nested connection/session values in a deeply immutable representation
  and return fresh detached JSON mappings.  Mutating an input mapping or a
  snapshot's public nested value must never alter a later API response or ETag.
- Replace arbitrary mapping/string fields with a narrow, typed allowlist.
  Reject secret-shaped connection names, invalid/non-string or oversized
  metadata, non-JSON values, arbitrary bot/connection state codes, and
  unsupported session fields.  The model/API must not offer an escape hatch
  for credentials, memo, identities, raw errors, paths, or debug data.
- Add focused coverage for deep immutability/detachment, invalid and
  secret-shaped input rejection, all four live states in JSON and SSR, health
  stopped/running/degraded/unavailable branches, all pilot-path unsafe methods,
  ETag behavior, and the no-external-call boundary.
- Browser visual validation is separately blocked because no Browser binding is
  available in this execution environment; retain the existing responsive CSS
  and add only source-level structural checks as appropriate.  Do not substitute
  an unrelated browser automation tool.

Re-run isolated-venv focused/full tests, compileall, and diff check.  After the
correction, request one fresh final review.  The handoff remains active until
the browser visual validation can be completed in an environment with a
Browser binding.

## Contract reset (2026-08-13): complete the pilot query contract

The first correction hardened the model, but its focused test coverage still
does not prove the state and HTTP contracts listed above.  Before another
review, reset the remaining work to this specific cohesive outcome:

- Keep the narrow immutable model, but make its supported state codes useful
  and explicit: bot state must be able to represent `running`, `stopped`,
  `unavailable`, and `action_required`; connection health must include the
  documented `healthy`, `stopped`, `degraded`, `unavailable`, and
  `action_required` states.  Reject every other state and unsafe/empty
  identifier/metadata value.  `StaticLiveProvider` must reject a non-snapshot
  value rather than leaking an arbitrary object into a route.
- Expand `tests/test_v2_live_pilot.py` into clear, independent coverage for:
  deep provider/API detachment; invalid/secret-shaped input; unavailable,
  offline, live, and degraded JSON and SSR copy/freshness; health stopped,
  running+unavailable, degraded, and healthy branches; all unsafe mutation
  verbs on all three pilot paths; ETag/no-store/304; old health endpoint
  behavior; and template/CSS structural accessibility/responsive tokens.
- Prove the API does not touch a default database, legacy module, external
  adapter, network, thread, media, or configuration source by injecting
  synthetic guards at its explicitly reachable boundaries.  Never substitute
  runtime data for test fixtures.
- Keep the browser visual validation marked blocked, rather than claiming it
  passed.  No replacement browser tool is permitted.

This reset stays within the original Phase 4A owned files.  Re-run isolated
focused/full tests, compileall, diff check, then obtain one final independent
review of the corrected contract.  The handoff remains active pending the
unavailable Browser visual check.

### Partial implementation record

The delegated writer completed the model allowlist/deep-freeze changes, but
returned with only two focused tests and did not meet the reset's required HTTP
and state-coverage matrix.  Those source changes are usable; the remaining
work is a narrow primary-session test-completion pass over the listed pilot
files, followed by one final review.  Do not begin a new feature slice or
delegate another overlapping writer until that pass is complete.

## Final-review correction (2026-08-13): health query isolation

The contract-reset implementation passed its expanded tests, but final review
found that the health route still called an unconstrained injected adapter and
echoed its arbitrary code.  Correct this in the primary session before a single
last review:

- The v2 pilot health query must not invoke `Container.adapters` at all.  Derive
  its Twitch component state only from the already-safe live snapshot's
  allowlisted `connections["twitch"]` value, with a missing value as
  `unavailable`.  Return only allowlisted state/message codes; never echo an
  adapter-provided code or error.  Add a synthetic adapter whose `status()`
  raises and prove all pilot GET queries still succeed without calling it.
- Render both `bot_state` and enabled intent on the SSR page, and reject the
  logically contradictory disabled/running model combination.  Test each
  supported state is truthful in output.
- Keep all previous no-I/O, immutability, GET-only, and legacy-health tests.
  Re-run the isolated suite, compileall, and diff check; then one final
  independent review.  Browser visual verification remains blocked and the
  handoff remains active.

## Completion evidence except browser visual QA

- The pilot now exposes only `GET /v2/live`, `GET /api/v2/live`, and
  `GET /api/v2/health`.  It uses immutable, allowlisted injected snapshots and
  never opens a database, reads a legacy/runtime source, starts runtime, or
  calls a container adapter from any of these GET queries.
- The final health correction is covered with an injected adapter whose
  `status()` raises; all three pilot GET routes return successfully and the
  adapter call count remains zero.
- Isolated verification: focused v2/legacy-status set `49 passed`; full suite
  `234 passed, 2 skipped`; `python -B -m compileall -q src/twitchbot tests` and
  `git diff --check` passed.
- Final independent review found no High or Medium issue.
- Browser visual QA was attempted through the required Browser skill after a
  synthetic localhost preview was started.  The browser runtime reported no
  available binding (`[]`), so no alternate browser automation tool was used;
  the temporary preview server was stopped.  This is the only remaining
  condition before this handoff can be archived.
