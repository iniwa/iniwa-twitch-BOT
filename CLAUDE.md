# CLAUDE.md

This is a compatibility boundary for Claude-oriented readers. Durable project
rules, role selection, approvals, verification, and documentation lifecycle
are defined in [AGENTS.md](AGENTS.md).

## Read first

Read [AGENTS.md](AGENTS.md), the active handoff or approved inline scope, and
the files named by that scope. Follow the repository's existing commands and
preserve project-specific protected behavior.

## Compatibility rules

- The approved scope may narrow durable rules but cannot weaken them.
- Claude Code is not an approved execution route unless the user explicitly
  changes project policy.
- Preserve unrelated work, secrets, credentials, local settings, runtime and
  production state, and protected data. Do not add dependencies or alter
  deployment, CI/CD, exposure, or persistent state outside approved scope.
- Do not commit, push, publish, or deploy unless explicitly requested.

## Reporting

Return changed files, concise rationale, verification results, blocked checks,
partial edits, and unresolved design questions. Run the focused checks required
by AGENTS.md, including git diff --check.
