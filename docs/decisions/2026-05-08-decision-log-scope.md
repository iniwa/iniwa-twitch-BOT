# Decision Log Scope

## Context
`AGENTS.md` is read at the start of Codex and Claude Code work. If it accumulates long alternatives, background notes, and task-specific reasoning, it becomes harder to use as a working agreement.

## Decision
Keep `AGENTS.md` Decision Log entries short and durable.

Do not include `Alternatives Considered` as a default heading in `AGENTS.md`.

When rejected options or long background are worth preserving, put them in `docs/decisions/` and keep only the actionable rule or constraint in `AGENTS.md`.

## Reason
This keeps `AGENTS.md` useful as a quick source of rules while still preserving longer design history in the repository.

## Operating Rule
- Put durable, future-facing rules in `AGENTS.md`.
- Put longer background, rejected options, and detailed reasoning in `docs/decisions/`.
- Reference the docs entry from `AGENTS.md` only when future sessions need that detail.
