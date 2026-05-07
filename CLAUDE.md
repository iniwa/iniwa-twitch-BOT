# CLAUDE.md

## Project Overview
- Purpose: Twitch bot and management dashboard for streaming operations on Raspberry Pi Docker.
- Runtime target: Raspberry Pi Docker linux/arm64
- Stack: Python, Flask, Twitch API, Docker

## Coding Style
- Write lightweight, efficient code. Prefer minimal dependencies.
- Follow existing project patterns before adding new abstractions.

## Codex / Claude Code Workflow
- This `CLAUDE.md` is for Claude Code execution rules.
- Codex handoffs should normally be saved under `docs/handoffs/`; when a handoff file path is provided, read it before editing.
- If the project also has `AGENTS.md`, treat it as the Codex-side source of design intent, handoff rules, and review criteria.
- When the user provides a Codex handoff, follow that handoff first, then this file, then local project conventions.
- If the task is ambiguous, requires changing documented design intent, or needs files outside the handoff, stop and ask before editing.
- Do not commit automatically unless explicitly requested.
- Report changed files, summary, verification results, blocked checks, and any design questions that should return to Codex.

## Environment
- Primary environment: Raspberry Pi Docker / linux/arm64
- Working in `D:/Git/` means Home Sub PC.
- Working in `C:/Git/` means Home Main PC.
- Working in `C:/Users/**/Documents/git/` means Remote PC with limited environment.
- Raspberry Pi is accessible via `ssh iniwapi` for reading code/logs.
- Preserve Docker and arm64 deployment behavior unless explicitly requested.

## Important Files
- README.md
- app.py
- config.py
- requirements.txt
- Dockerfile
- compose.yaml
- docs/

## Verification
- Run the checks listed in the Codex handoff.
- If verification cannot be run, report the reason.

## Reporting
- Changed files
- Summary
- Verification results
- Blocked checks
- Design questions for Codex
