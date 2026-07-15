# CLAUDE.md

## Purpose

This file contains Claude Code execution rules for `iniwa-twitch-bot`. `AGENTS.md` owns design intent, delegation policy, and Codex review.

## Read Before Editing

Read:

- `AGENTS.md`.
- The supplied handoff, when present.
- `README.md` and every file listed for inspection.
- Relevant active records under `docs/`.
- Build and deployment files only when the approved task includes them.

## Project Facts

- Python 3.12 Flask application served by gunicorn.
- Jinja2 templates and browser JavaScript provide the management dashboard.
- Twitch state, viewer data, analytics, rules, predictions, presets, and VOD workflows are handled by existing routes and services.
- yt-dlp and ffmpeg support the independent Twitch VOD download feature.
- The primary runtime is a Raspberry Pi-compatible `linux/arm64` Docker container.

## Execution Rules

- Implement and report only the current independently verifiable slice.
- A handoff defines task scope but does not override durable constraints in `AGENTS.md`.
- If the listed files are insufficient to reach the first scoped edit, stop and report the missing discovery or proposed split instead of broadening the task.
- Return unresolved requirements and design choices to Codex.
- Stop before adding a dependency or changing build tooling, packaging, CI/CD, deployment, image names, ports, host networking, storage, domains, or external exposure unless the task explicitly includes it.
- Subagents are optional and limited to clearly parallel mechanical work within the same files, scope, and constraints.
- Preserve unrelated user and other-agent changes. Treat unexpected diffs as having unknown authorship and exclude them from the current task.
- Do not commit, push, publish an image, or deploy unless explicitly requested.

## Implementation Constraints

- Keep `GET /api/stream/status` read-only and based only on actual Twitch state already held by the worker.
- Do not make a Twitch API request or external-service call while serving that endpoint.
- Do not add secretary-bot notifications, OBS control, OBS archive UI or settings, administrator-mode VOD gating, or VOD-to-OBS migration.
- Preserve the independent VOD workflows and keep automatic VOD download controlled only by `enable_vod_download`, defaulting off.
- Follow existing Flask blueprint, service, storage, threading, logging, template, and browser-script patterns.
- Preserve Raspberry Pi and `linux/arm64` compatibility.
- Prefer small, readable changes and minimal dependencies.

## Protected Files and State

Do not edit, delete, or inspect contents unless explicitly required:

- Twitch credentials, access tokens, IDs, `.env` files, and local runtime configuration.
- `data/`, `data.db`, viewer and stream-history data, downloaded media, and VOD working files.
- Production mounts, Portainer state, container runtime state, and generated heavy artifacts.
- Deployment workflow, GHCR image settings, host networking, ports, and external exposure outside an approved deployment task.

Tests must use temporary or mocked state and must not contact Twitch, secretary-bot, OBS, or another external service.

## Verification

Run the smallest relevant checks:

- Documentation-only changes: `git diff --check` and a focused reference scan.
- Python changes: compile the touched files explicitly with `python -m py_compile <files>`.
- Focused behavior: run the directly affected pytest files or test functions.
- Broader code changes: `python -m pytest tests/ -q`.
- Stream-status changes should include the focused status tests and prove that no request-time Twitch call occurs.
- VOD boundary changes should include the focused route and worker snapshot tests.
- Docker or compose checks are required only when those files are in the approved scope; do not deploy as verification.

If a dependency or runtime environment is unavailable, report the blocked check and reason.

## Report

Report:

- Changed files.
- Concise summary.
- Verification commands and results.
- Blocked checks.
- Subagent usage.
- Design questions for Codex.
