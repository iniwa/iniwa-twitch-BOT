# CLAUDE.md

## Purpose

This file contains Claude Code execution rules for `iniwa-twitch-bot`. `AGENTS.md` owns design intent, delegation policy, and Codex review.

## Read Before Editing

Read:

- `AGENTS.md`.
- The supplied handoff or equivalent inline task scope.
- `README.md` and every file listed for inspection.
- Relevant active records under `docs/`.
- Build and deployment files only when the approved task includes them.

## Project Facts

- Python 3.12 Flask application served by gunicorn.
- Jinja2 templates and browser JavaScript provide the management dashboard.
- Twitch state, viewer data, analytics, rules, predictions, presets, and VOD workflows are handled by existing routes and services.
- yt-dlp and ffmpeg support the independent Twitch VOD download feature.
- The primary runtime is a Raspberry Pi-compatible `linux/arm64` Docker container.
- Mutable JSON configuration, viewer, and history data is mounted at `/app/data`; current-session viewer and stream snapshots are in-memory shared state; VOD media and working files are mounted at `/app/downloads`. Current application code does not use `data.db`.
- Gunicorn serves the host-networked application on port `8501`. The existing workflow publishes `linux/amd64` and `linux/arm64` images for manual Portainer deployment.

## Execution Rules

- Implement and report only the current independently verifiable slice.
- The handoff or equivalent inline scope is the approved task scope. It may narrow durable constraints in `AGENTS.md` but may not weaken them. If instructions conflict, stop and return the conflict to Codex.
- Before editing, capture `git status --short` when Git is available. After editing, compare the final status and diff with that baseline. Do not reset, clean, stage, or rewrite pre-existing changes.
- If the listed files are insufficient to reach the first scoped edit, stop and report the missing discovery or proposed split instead of broadening the task.
- Return unresolved requirements and design choices to Codex.
- Stop before adding a dependency or changing build tooling, packaging, CI/CD, deployment, image names, ports, host networking, storage, domains, or external exposure unless the task explicitly includes it.
- Subagents are optional and limited to clearly parallel mechanical work within the same files, scope, and constraints.
- Preserve unrelated user and other-agent changes. Treat unexpected diffs as having unknown authorship and exclude them from the current task.
- Do not commit, push, publish an image, or deploy unless explicitly requested.

## Implementation Constraints

- Keep `GET /api/stream/status` read-only and based only on actual Twitch state already held by the worker.
- Do not make a Twitch API request or external-service call while serving that endpoint.
- Preserve the existing lock-protected copy and snapshot semantics for current-session viewers and current stream state. Tests must use detached or mocked state, and external stream state must clear at stream end or when the bot is disabled.
- Do not add secretary-bot notifications, OBS control, OBS archive UI or settings, administrator-mode VOD gating, or VOD-to-OBS migration.
- Preserve the independent VOD workflows and keep automatic VOD download controlled only by `enable_vod_download`, defaulting off.
- Follow existing Flask blueprint, service, storage, threading, logging, template, and browser-script patterns.
- Preserve Raspberry Pi and `linux/arm64` compatibility.
- Prefer small, readable changes and minimal dependencies.

## Protected Files and State

- Do not inspect secrets, credentials, personal data, real Twitch token or configuration values, or the contents of runtime data, current-session viewer or history state, any `data.db`, downloaded media, or VOD working files unless strictly necessary for the approved task.
- Do not edit Twitch credentials, tokens, IDs, `.env` files, local runtime configuration, `data/`, any `data.db`, session, viewer, or history state, downloaded media, VOD working files, production mounts, Portainer state, container runtime state, or generated heavy artifacts unless the approved task explicitly requires the change.
- Never reproduce secrets, credentials, personal data, or private infrastructure values in prompts, handoffs, reports, or external tools.
- Do not change the deployment workflow, GHCR image settings, host networking, port `8501`, `/app/data` or `/app/downloads` mounts, domains, or external exposure unless the approved task explicitly requires the change.

Tests must use temporary or mocked state and must not contact Twitch, secretary-bot, OBS, or another external service.

## Verification

Run the smallest relevant checks:

- Documentation-only changes: `git diff --check` and a focused reference scan.
- Python syntax changes: `python -m compileall -q app.py config.py routes services`.
- Stream-status changes: `python -m pytest tests/test_stream_status.py -q`; prove that no request-time Twitch call occurs.
- VOD and worker-boundary changes: `python -m pytest tests/test_vod_routes.py tests/test_workers_snapshot.py -q`.
- Broader code changes: `python -m pytest tests/ -q`.
- Compose changes: `docker compose config`. Dockerfile or image changes require an architecture-compatible build check, but publishing or deploying is not verification.
- Rendering, routing, accessibility, or interaction changes require an available browser-level check against an isolated test instance; never use production tokens, state, mounts, or media.

If a dependency or runtime environment is unavailable, report the blocked check and reason.

## Report

Report:

- Completion status: `complete` or `interrupted`.
- Changed files.
- Concise summary.
- Verification commands and results.
- Blocked checks.
- Baseline and final worktree status/diff comparison.
- Partial results, remaining scope, and the resume condition when interrupted.
- Subagent usage.
- Confirmation that credentials, runtime configuration/data, session state, database state, media, storage mounts, deployment, and external exposure were preserved.
- Design questions for Codex.
