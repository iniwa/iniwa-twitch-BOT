# AGENTS.md

## Purpose
This file is the Codex-side working agreement for `iniwa-twitch-bot`.

Codex uses this file to preserve design intent, decide whether work should stay in Codex or be handed off to Claude Code, and review implementation results.
Claude Code uses `CLAUDE.md` for execution rules.

## Project Summary
- Project name: `iniwa-twitch-bot`
- Purpose: Twitch bot and management dashboard for streaming operations on Raspberry Pi Docker.
- Summary from project docs: Twitch bot and management dashboard for streaming operations on Raspberry Pi Docker.
- Runtime target: Raspberry Pi Docker linux/arm64
- Repository path: `D:\Git\iniwa-twitch-bot`
- Stack: Python, Flask, Twitch API, Docker

## Base References
- Codex base: `D:/Git/CLAUDEmdStrage/_base/AGENTS.md`
- Claude Code base for Windows/local projects: `D:/Git/CLAUDEmdStrage/_base/CLAUDE_windows.md`
- Claude Code base for Raspberry Pi Docker projects: `D:/Git/CLAUDEmdStrage/_base/CLAUDE_docker.md`

## Role Split
Codex is responsible for:
- clarifying requirements, non-goals, and success criteria
- identifying change type and design risk
- preserving responsibility boundaries and design intent
- preparing scoped Claude Code handoffs when execution is clear
- reviewing Claude Code output against this file and the handoff
- recording durable decisions in `AGENTS.md` or `docs/*.md`

Claude Code is responsible for:
- following the current Codex handoff and `CLAUDE.md`
- editing only allowed files unless it explains why more files are required
- running requested verification where possible
- reporting changed files, summary, verification results, blocked checks, and design questions

## Claude Code Model Orchestration
Claude Code should normally run with Opus as the primary coordinator.

Opus is responsible for:
- reading `AGENTS.md`, `CLAUDE.md`, handoff files, and relevant project context
- interpreting requirements, constraints, non-goals, and verification expectations
- deciding the implementation plan and whether subagents are appropriate
- giving Sonnet subagents narrow implementation or investigation tasks
- reviewing subagent output before final reporting
- making design-sensitive decisions only when they are already allowed by the handoff

Sonnet subagents are responsible for:
- mechanical code edits
- repetitive refactors inside an explicit file scope
- localized tests, verification, and log/code inspection
- implementation tasks where goal, files, constraints, and non-goals are already clear

Sonnet subagents must not:
- change documented design intent on their own
- expand the edit scope beyond the handoff without Opus review
- introduce dependencies, build tooling, packaging, CI/CD, deployment, or external exposure changes unless explicitly listed
- touch secrets, credentials, `.env`, or local settings
- make final architectural decisions without returning the question to Opus/Codex

For very small edits, Opus may implement directly instead of creating unnecessary subagent overhead.
If the requested Claude Code environment cannot use subagents or the intended model split, Claude Code should continue with the available model and report that limitation.

## Decision Rule
Keep work in Codex when:
- requirements are ambiguous
- design intent or responsibility boundaries may change
- the task is small enough to edit and review in one context
- the main value is planning, review, or documentation consistency

Hand off to Claude Code when:
- goal, files, constraints, non-goals, and verification are clear
- the task is mostly implementation or mechanical editing
- the allowed edit scope can be stated explicitly
- Claude Code tooling or iteration speed is useful

## Project-Specific Guidance
- Use Raspberry Pi / Docker guidance from `D:/Git/CLAUDEmdStrage/_base`.
- Preserve `linux/arm64` compatibility unless the project explicitly supports more architectures.
- Do not change deployment, image naming, Portainer, or external exposure behavior without explicit approval.

## Files To Inspect First
- README.md
- app.py
- config.py
- requirements.txt
- Dockerfile
- compose.yaml
- docs/

## Files Claude Code May Edit In Scoped Tasks
- app.py
- config.py
- requirements.txt
- Dockerfile
- compose.yaml
- docs/

## Constraints
- Preserve Raspberry Pi / arm64 Docker deployment.
- Do not commit real Twitch credentials or tokens.
- Keep dashboard workflows practical for repeated stream operation.
- Do not change deployment/external exposure without explicit approval.
- Do not commit automatically unless explicitly requested.
- Do not revert user or other-agent changes unless explicitly requested.
- Do not edit secrets, credentials, `.env`, local runtime data, or generated heavy artifacts unless explicitly requested.

## Handoff Template
When Codex hands work to Claude Code, create `docs/handoffs/YYYY-MM-DD-<short-task>.md`. Create the `docs/handoffs/` directory if it does not exist. Use this format in that file.

```md
Read AGENTS.md, CLAUDE.md, and this handoff file before implementation.
If implementation would violate constraints or require files outside this handoff, stop and ask before editing.

## Goal
...

## Background
...

## Files To Inspect
- ...

## Files To Edit
- ...

## Constraints
- ...

## Non Goals
- ...

## Verification
- ...

## Expected Report
- Changed files
- Summary
- Verification results
- Blocked checks
- Design questions for Codex
```

## Codex Review Checklist
After Claude Code returns, review:
- Did the diff stay inside the handoff?
- Did any file outside `Files To Edit` change? If yes, was it necessary?
- Did the implementation preserve stated constraints and non-goals?
- Did it introduce dependencies, build tooling, packaging, CI/CD, deployment changes, or external exposure changes unexpectedly?
- Did it touch secrets, credentials, `.env`, local settings, or runtime data?
- Did verification run, and are blocked checks explained?
- Does any discovery need to become a new `AGENTS.md` or `docs/*.md` decision?

## Knowledge Persistence
- Use `AGENTS.md` for durable workflow and design decisions.
- Use `docs/*.md` for reusable technical notes, architecture details, procedures, and project-specific knowledge.
- Before meaningful work, check relevant existing docs.
- Do not silently encode durable design decisions only in code.

## Design Record Scope
Keep `AGENTS.md` focused on short, durable rules that future Codex and Claude Code sessions must follow.

Do not add `Alternatives Considered` as a default Decision Log heading. When rejected options or longer background matter, summarize only the durable rule in `AGENTS.md` and put the detail under `docs/decisions/`.
## Decision Log

### 2026-06-22: Reverse integration — expose read-only stream status, no secretary-bot/OBS integration

Context:
- The push-notification coupling to `secretary-bot` is no longer desired. This
  project should remain usable as an independent Twitch bot and dashboard.

Decision:
- `iniwa-twitch-bot` exposes a generic, read-only current-stream status API
  (`GET /api/stream/status`) that reports only worker-held state and performs no
  Twitch API call per request and no external service call.
- This project does not call, configure, display state from, or otherwise
  integrate with `secretary-bot`, and contains no OBS recording integration.
  `secretary-bot` polls the status API and independently owns all OBS archive
  recording, file organization, encoding, previews, and retention.
- VOD download (manual, bulk, cancel, delete, history sync, and post-stream
  auto-download) is an independent built-in feature controlled solely by
  `enable_vod_download` (default off). No OBS/administrator-mode gating.

Reason:
- This project already owns Twitch stream state; reversing the direction to a
  pull model removes cross-project coupling and lets each side own its domain.

Constraints Introduced:
- `GET /api/stream/status` must stay read-only and never trigger a Twitch API
  call or contact `secretary-bot`.
- Keep VOD download independently configurable and default off.

Do Not Change Casually:
- Do not re-add secretary-bot notification, OBS archive settings/status display,
  connection tests, administrator-mode gating, or VOD-to-OBS migration.
- Detail: `docs/decisions/2026-06-01-twitch-obs-archive-recording.md` (superseded
  integration direction) and
  `D:/Git/secretary-bot/docs/decisions/2026-06-22-twitch-stream-status-pull.md`.

### 2026-06-01: Twitch detects streams, secretary-bot owns OBS archive recording

> Superseded by the 2026-06-22 decision above. The push-notification direction
> is retired; the OBS archive ownership rules remain valid as secretary-bot-owned
> behavior.

Context:
- Local streaming now records with OBS in parallel, so Twitch VOD download is no longer the normal archive source.

Decision:
- `iniwa-twitch-bot` detects Twitch start/end and notifies `secretary-bot`; `secretary-bot` and Windows Agent control OBS recording and archive media.
- Detailed implementation decisions live in `docs/decisions/2026-06-01-twitch-obs-archive-recording.md`.

Reason:
- This project already owns Twitch stream state, while `secretary-bot` owns OBS Recording Library, Windows Agent delegation, encode, preview, and retention.

Constraints Introduced:
- On Twitch stream end, request OBS recording stop if OBS is recording, even if it was already recording before the integration event.
- Keep Twitch VOD download as administrator/fallback functionality; do not remove it.
- Do not add direct OBS WebSocket or recording file move ownership to this project.

Do Not Change Casually:
- Do not make Twitch VOD download the default local archive path again without a new design review.
- Do not bypass `secretary-bot` for OBS archive recording management.

### YYYY-MM-DD: Decision title

Context:
- What problem or requirement caused this decision?

Decision:
- What did we decide?

Reason:
- Why is this the right tradeoff now?

Constraints Introduced:
- What should future implementation preserve?

Do Not Change Casually:
- What would cause design drift if changed without review?
