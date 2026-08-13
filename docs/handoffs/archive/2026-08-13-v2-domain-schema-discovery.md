# v2 domain schema discovery for staged legacy import

Status: completed on 2026-08-13.

Outcome: the smallest coherent destination boundary is `streams`,
`stream_samples`, `viewers`, and `vod_assets`; the accepted implementation
scope is now `2026-08-13-v2-domain-destination-schema.md`. No files were
edited during discovery and no runtime data, credentials, downloads, or
operational database were inspected.

## Goal

Settle the smallest cohesive next domain-persistence slice after completed 2B1
source inspection. The result must define a forward-only schema/repository
boundary that can later receive inspected legacy stream, viewer, sample, and
VOD metadata without falsely claiming a full legacy import.

## Background

The v2 core schema is complete and has only system tables. Completed 2B1 can
inspect a staged legacy source safely but always returns `import_ready=false`
until destination domain tables exist. The staging decision is in
`docs/decisions/2026-08-13-legacy-importer-staging-order.md`.

## Read-only data sources

- `AGENTS.md`, `CLAUDE.md`
- `docs/rebuild/04-data-and-api.md`, especially logical model and legacy
  inventory sections
- `docs/rebuild/05-migration-and-delivery.md`
- `src/twitchbot/adapters/persistence/`, `src/twitchbot/application/persistence.py`
- `tests/test_v2_persistence.py`
- completed source-inspector contracts under `src/twitchbot/migration/`

Do not inspect runtime `data/`, credentials, downloaded media, `data.db`, or
production configuration.

## Questions to settle

1. Which tables form the smallest internally consistent migration after the
   core schema, including keys, constraints, foreign keys, timestamps,
   revision/concurrency, and approved indexes?
2. What precise mapping can safely cover legacy stream index, viewers, minute
   samples, and VOD metadata while preserving unknown fields without raw
   payload duplication?
3. Which data remains deferred (events, chat bodies, counters, viewer-stream
   relations, presets/rules/predictions, VOD jobs), and why?
4. How should a future importer stage writes, make reruns idempotent, ensure
   atomic rollback, and avoid credential/media/source mutation?
5. What focused test matrix proves the schema/repository contract without
   reading real sources or opening the operational database?

## Deliverable

A concise evidence-backed proposal with exact table/field contracts, known
ambiguities, test acceptance criteria, and a recommended single implementation
slice. No source edits, database creation, migration execution, or runtime
wiring.
