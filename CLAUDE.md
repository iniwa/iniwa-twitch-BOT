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

## Model / Subagent Policy
- Use Opus as the primary Claude Code coordinator by default.
- Opus owns context reading, requirement interpretation, planning, design-sensitive judgment, and final review.
- Use Sonnet subagents for scoped implementation work, mechanical edits, localized refactors, code/log inspection, and verification when the task is clear enough to delegate.
- Give each Sonnet subagent a narrow goal, explicit file scope, constraints, non-goals, and expected report.
- Sonnet subagents must not change documented design intent, expand scope, add dependencies, alter build/deploy/external exposure, touch secrets, or make architectural decisions without returning to Opus.
- For small edits, Opus may implement directly rather than creating unnecessary subagent overhead.
- If subagents or the intended model split are unavailable, continue with the available model and report that limitation.

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

## Tooling
- Use **Serena MCP** tools for code navigation and editing to maximize efficiency (symbol search, overview, replace, insert, etc.)
- Use **Tavily MCP** tools for web search and research:
  - `tavily_search` — General web search for documentation, error messages, library usage, etc.
  - `tavily_crawl` — Crawl a specific website for detailed information
  - `tavily_extract` — Extract structured content from a URL
  - `tavily_research` — In-depth research on a topic (use for complex or multi-faceted questions)

## Knowledge Persistence
Durable project workflow decisions belong in AGENTS.md. Surface implementation discoveries that should guide future sessions so Codex can decide whether to record them.
Detailed design history belongs in `docs/decisions/`. Keep `AGENTS.md` focused on short, durable rules; do not add `Alternatives Considered` as a default Decision Log heading there.
