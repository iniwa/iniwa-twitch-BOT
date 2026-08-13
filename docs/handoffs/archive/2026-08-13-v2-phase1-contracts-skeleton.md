# v2 Phase 1: protected contracts and side-effect-free skeleton

Status: completed on 2026-08-13.

Completion verification: focused v2/characterization suite `7 passed`; full legacy and v2 suite `25 passed`; `compileall`, isolated import/runtime probe, and `git diff --check` passed; independent final review found no actionable High/Medium issues.

## Goal

Start the approved rebuild incrementally by locking down protected legacy behavior and adding a side-effect-free v2 application skeleton that is not connected to production.

## Background

The current root `app.py` creates the Flask application and starts three background workers during module import. The production container still launches gunicorn with `app:app`. The rebuild design in `docs/rebuild/` calls for a strangler migration: characterize protected behavior first, then introduce a clean application/runtime boundary without changing the production entry point.

This slice deliberately stops before route migration, worker migration, data migration, or production cutover.

## Data sources and records

- `AGENTS.md` and `CLAUDE.md`
- `docs/rebuild/README.md`
- `docs/rebuild/00-current-state-audit.md`
- `docs/rebuild/01-product-requirements.md`
- `docs/rebuild/02-information-architecture-and-ui.md`
- `docs/rebuild/03-system-architecture.md`
- `docs/rebuild/04-data-and-api.md`
- `docs/rebuild/05-migration-and-delivery.md`
- `docs/rebuild/06-quality-security-operations.md`
- Existing implementation and tests listed below

## Files to inspect

- `app.py`
- `config.py`
- `routes/dashboard.py`
- `services/workers.py`
- `tests/conftest.py`
- `tests/test_stream_status.py`
- `tests/test_workers_snapshot.py`
- `tests/test_session_viewers.py`
- `tests/test_vod_routes.py`
- `tests/test_paths.py`

## Files to edit

- `tests/conftest.py`
- New focused test files under `tests/`
- New package files under `src/twitchbot/`

Do not edit the legacy production entry point, legacy routes, workers, storage code, configuration defaults, templates, static assets, dependencies, container files, or deployment files in this slice.

## Required implementation

1. Add a `src/twitchbot/` package with a callable `create_app` entry point.
2. Keep importing `twitchbot` side-effect free. Import must not start a thread, open a network connection, create a directory, or write a file.
3. Keep Flask loading lazy enough that importing the package does not itself construct an application or start runtime behavior.
4. Add an explicit runtime supervisor boundary with idempotent `start()` and `stop()` behavior. It must not start automatically during import or application creation.
5. Add a small dependency container owned by the v2 package and stored on the Flask application when the factory is invoked.
6. Add isolated v2 liveness/readiness endpoints suitable for testing the new boundary. They must not call Twitch or read/write legacy runtime data.
7. Add characterization coverage for the protected legacy contracts not already explicit:
   - current-stream snapshots are returned as detached values;
   - `/api/stream/status` exposes only the approved public fields even if an internal snapshot contains additional fields;
   - automatic VOD download remains off when the flag is absent/defaulted;
   - importing the new package has no thread, network, directory-creation, or file-write side effects.
8. Update the test path setup only as needed to import the `src` package. Do not introduce packaging/build-tool changes.

## Acceptance criteria

- Root `app.py` and the Docker gunicorn target remain unchanged and continue to own production behavior.
- The v2 package imports without constructing a Flask app, loading legacy configuration, starting runtime components, touching `/app/data` or `/app/downloads`, or contacting any service.
- `create_app()` returns an isolated Flask app and does not start the runtime supervisor.
- `/health/live` returns a successful liveness result without external I/O.
- `/health/ready` reflects runtime readiness without external I/O.
- Runtime start/stop calls are idempotent and have focused unit coverage.
- Characterization tests preserve the stream-status allowlist, copy boundary, and VOD opt-in invariant.
- No dependency, Docker, compose, CI/CD, port, network, mount, image, deployment, or production-data change is present.
- No secretary-bot, OBS, administrator gate, or VOD-to-OBS behavior is introduced.
- The writer performs a stable self-review before handoff; a separate bounded review checks side-effect, compatibility, and regression risks.

## Constraints

- Preserve all unrelated user and agent changes.
- Do not inspect or edit secrets, tokens, runtime configuration, `data/`, history/viewer/session state, databases, downloads, or media.
- Use relative imports inside the v2 package to avoid collisions with legacy `config` and `routes` modules.
- Keep dependencies minimal; use the existing Flask dependency and Python standard library only.
- Tests must not perform real DNS, Twitch calls, network connections, background thread starts, or persistent filesystem writes.
- Maintain Python 3.12 and `linux/arm64` compatibility.

## Non-goals

- No production entry-point cutover.
- No legacy route, worker, Twitch client, IRC, EventSub, download, analytics, or UI migration.
- No JSON schema or data migration.
- No authentication implementation.
- No Docker image publication, commit, push, deployment, Portainer change, or live-environment action.

## Verification

- Run a syntax/import compilation check for the new package and tests.
- Run focused tests for the v2 package and the added characterization contracts.
- Run the full existing test suite when the available environment supports its declared dependencies.
- If the host lacks test dependencies, use an isolated, non-persistent container when practical; otherwise report the blocked check explicitly.
- Inspect the final diff and repository status to confirm that only approved files changed.
- Obtain one independent bounded review after the writer's stable self-review.

## Expected report

- Files added or changed.
- Behavior now covered by tests.
- Verification commands and results, including any environment blocker.
- Confirmation that production wiring and protected boundaries remain unchanged.
- Remaining scope for Phase 2.
