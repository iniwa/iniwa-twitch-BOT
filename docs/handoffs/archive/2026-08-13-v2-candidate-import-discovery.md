# v2 Phase 2B2B candidate importer discovery

Status: completed on 2026-08-13.

Outcome: the approved next slice is candidate-only, source-preserving,
single-transaction import plus verification, recorded in
`2026-08-13-v2-candidate-importer.md`. No files were edited during discovery
and no runtime data, credential, media, or operational database was inspected.

## Goal

Settle the smallest safe implementation slice for importing a completed 2B1
inspection result into an explicitly supplied temporary/candidate v2 database,
then verifying its counts and aggregates. No operational cutover, production
database, source mutation, or runtime integration is allowed.

## Background

Completed 2B1 can inspect a staged legacy JSON/JSONL source safely, establish a
manifest/cutoff, and report `import_ready=false` before domain tables existed.
Completed 2B2A now provides isolated core plus streams, samples, viewers, and
VOD destination repositories. The staged-import decision remains authoritative
in `docs/decisions/2026-08-13-legacy-importer-staging-order.md`.

## Read-only sources

- `AGENTS.md`, `CLAUDE.md`
- `docs/rebuild/04-data-and-api.md` sections 4, 6–7, 15
- `docs/rebuild/05-migration-and-delivery.md` Phase 2 / rollback / exit gates
- `docs/rebuild/06-quality-security-operations.md`
- `docs/decisions/2026-08-13-legacy-importer-staging-order.md`
- archived 2B1 / 2B2A handoffs
- `src/twitchbot/migration/inspector.py`
- `src/twitchbot/application/persistence.py`
- `src/twitchbot/adapters/persistence/`
- v2 focused tests

Do not inspect `data/`, credentials, downloads/media, `data.db`, production
configuration, or actual operational database.

## Questions to settle

1. What application API accepts only an already inspected/re-verified synthetic
   source and explicit candidate `SQLiteDatabase`, with no default DB path?
2. What mappings from config/viewers/stream index/valid JSONL/VOD metadata are
   honest with 2B2A's four tables, and what remains reported/deferred?
3. How are batch identity, source manifest/cutoff, idempotent rerun, atomic
   rollback, malformed line continuation, unknown metadata, unresolved
   credentials, and VOD-path rejection defined?
4. What output is a safe immutable verification report, avoiding identity,
   note/chat/token/path values?
5. What test matrix proves source invariance, candidate-only writes, offline
   boundaries, failure rollback, rerun no-op, changed source rejection, and
   count/aggregate parity?

## Deliverable

An evidence-backed proposal for one cohesive future implementation handoff,
including exact application/repository interfaces, staging order, privacy and
failure semantics, tables used, deferred entities, and test acceptance. No
edits, imports, DB creation, source reads outside code/docs, or runtime wiring.
