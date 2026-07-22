# AGENTS.md

## Purpose

This is the Codex-side working agreement for `iniwa-twitch-bot`. It records design intent, delegation policy, review rules, and durable project constraints. `CLAUDE.md` contains Claude Code execution rules.

## Project Summary

- Twitch bot and management dashboard for repeated stream operations.
- Python 3.12, Flask, gunicorn, Jinja2, browser JavaScript, Twitch API, yt-dlp, and ffmpeg.
- Runs in Docker with Raspberry Pi `linux/arm64` as the primary target.
- Existing GitHub Actions publish the configured multi-architecture image to GHCR for manual Portainer deployment.
- Mutable JSON configuration, viewer, and history data lives under the `/app/data` mount; current-session viewer and stream snapshots live in process memory; VOD media and working files live under `/app/downloads`. Current application code does not use `data.db`.

## Read First

Before meaningful work, inspect:

- `CLAUDE.md`.
- `README.md`.
- `app.py`, `config.py`, and affected files under `routes/`, `services/`, `templates/`, `static/`, and `tests/`.
- `Dockerfile`, `compose.yaml`, and the existing workflow only when build or deployment behavior is in scope.
- Relevant active records under `docs/`.

## Instruction Precedence

When instructions conflict, apply them in this order:

1. Runtime, tool, organization, and safety policy.
2. Explicit user instructions that change project policy.
3. Durable project instructions.
4. Other instructions for the current user task and the approved task scope.

The active handoff or equivalent inline prompt is the approved task scope. Verified repository facts override generation-source defaults. Only an explicit user instruction to change project policy may revise a durable project rule; other task instructions and approved scopes may narrow durable rules but may not weaken them. Report unresolved conflicts instead of guessing.

## Model and Role Policy

- Use GPT-5.3-Codex-Spark (`gpt-5.3-codex-spark`) proactively, when available, for low-risk, well-scoped, independently verifiable supporting work that requires no material design judgment or source-code implementation.
- GPT-5.6 Terra (`gpt-5.6-terra`) or Sol (`gpt-5.6-sol`) owns requirements and design. Whenever Terra is used, set its reasoning level to `high`. Prefer Sol for substantial ambiguity, risk, or cross-boundary reasoning.
- Run every Claude Code task with `--permission-mode auto`.
- After design is fixed, delegate source-code implementation first to Claude Code Sonnet at effort medium from the repository root: `claude -p --model sonnet --effort medium --permission-mode auto "<handoff/task prompt>"`.
- Only when Sonnet is unavailable because of usage limits or service availability, use GPT-5.6 Luna (`gpt-5.6-luna`) with reasoning level `max` for the same implementation slice.
- Implementation failure, failed verification, or a design question is not model unavailability. Return it to Codex.
- Apply this policy to every coordinating Codex model and its subagents. Do not create coordinator-specific exceptions.
- Codex may retain requirements, design, read-only investigation, synthesis, review, and small documentation-consistency changes in one context.
- Claude Code subagents are optional and limited to clearly parallel mechanical work inside the current task scope. They inherit its constraints.

## Durable Project Rules

- `GET /api/stream/status` is a generic read-only snapshot of actual Twitch state already held by the worker.
- A status request must not call the Twitch API, contact `secretary-bot`, control OBS, or call another external service.
- Preserve the lock-protected snapshot and copy boundaries for current-session viewers and current stream state. Clear the externally visible stream snapshot when a stream ends or the bot is disabled.
- Do not reintroduce secretary-bot notifications, OBS recording control, OBS archive settings or status, administrator-mode gating, or VOD-to-OBS migration.
- Twitch VOD download remains an independent built-in feature, including its existing manual and automatic workflows. Automatic download is controlled only by `enable_vod_download`, whose default remains off.
- Preserve Twitch bot, dashboard, analytics, viewer, rule, prediction, preset, and stream-history behavior outside an approved change.
- Preserve Raspberry Pi and `linux/arm64` compatibility, the host-networked port `8501`, the `/app/data` and `/app/downloads` mount boundaries, and the existing Docker image, GitHub Actions, GHCR, Portainer, networking, and external-exposure flow.
- Keep dependencies minimal and preserve the single-container gunicorn architecture unless an approved design changes it.

## Safety and Scope

- Preserve unrelated user and other-agent changes. Treat unexpected diffs as having unknown authorship and keep them outside the current task or commit.
- Do not inspect secrets, credentials, personal data, real Twitch token or configuration values, or the contents of runtime data, current-session viewer or history state, any `data.db`, downloaded media, or VOD working files unless strictly necessary for the approved task.
- Do not edit Twitch credentials, tokens, IDs, `.env` files, runtime configuration, `data/`, any `data.db`, session, viewer, or history state, downloaded media, VOD working files, storage mounts, production data, or container/runtime state unless the approved task explicitly requires the change.
- Never reproduce secrets, credentials, personal data, or private infrastructure values in prompts, handoffs, reports, or external tools.
- Do not add dependencies or change build tooling, packaging, CI/CD, deployment, image names, ports, host networking, storage mounts, domains, or external exposure outside the approved scope.
- Do not commit, push, publish an image, or deploy unless explicitly requested.

## Handoff Workflow

- Keep work in Codex when its main value is policy, design, review, synthesis, read-only investigation, or a small documentation-only correction.
- For substantive implementation, create `docs/handoffs/YYYY-MM-DD-<short-task>.md` with the goal, background, data sources, acceptance criteria, files to inspect, files to edit, constraints, non-goals, verification, and expected report.
- One handoff covers one cohesive, independently verifiable change and its direct regression coverage. Run unresolved discovery as a separate read-only slice.
- Size the slice so the first intended edit is reachable after reading the listed files. Do not combine broad discovery, unresolved design, and implementation.
- If a delegation ends before meeting its acceptance criteria, treat it as interrupted even when the process exits normally. Record usable partial results, verification, remaining scope, and the resume condition; narrow a broad handoff before rerunning it.
- Sonnet implements only the approved slice. Luna at reasoning level `max` may implement that same slice only under the model-unavailability condition above.
- Codex reviews the report and diff before preparing a later slice. Material design questions return to Terra or Sol.
- Keep only active or blocked handoffs in `docs/handoffs/`. Move a handoff to `docs/handoffs/archive/` only after implementation, verification, review, required runtime work, and follow-up are complete.

## Codex Review

Verify that:

- Only approved files and behavior changed and unrelated diffs remain untouched.
- The stream-status endpoint remains read-only and free of request-time Twitch or external calls.
- No secretary-bot or OBS push integration, VOD gating, or changed default was introduced.
- Runtime data, credentials and tokens, in-memory session and stream snapshots, any database state, media, deployment, image, network, storage, and exposure boundaries were preserved.
- Focused tests support the change and blocked checks are explicit.
- Reusable discoveries are recorded in the correct document without adding implementation history here.

## Documentation Lifecycle

- Keep `AGENTS.md` limited to short, current, durable rules and links.
- Put detailed decisions, evidence, rejected options, and rollout history in `docs/decisions/`.
- Move a decision to `docs/decisions/archive/` only after it is fully implemented and no longer needed as current guidance.
- Keep active or blocked handoffs in `docs/handoffs/` and completed handoffs in `docs/handoffs/archive/`.
- Put reusable procedures and architecture details in the appropriate `docs/` location.
- Do not rewrite completed handoffs or archived decisions merely to match a newer shared policy.
