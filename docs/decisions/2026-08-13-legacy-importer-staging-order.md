# Legacy importer staging order

Date: 2026-08-13
Status: accepted for the rebuild implementation

## Decision

Split the rebuild plan's legacy-importer phase into two implementation stages:

1. **2B1 — read-only source inspection and migration planning**
   - Inventory and checksum only allowlisted legacy files.
   - Parse fixture sources without modifying them.
   - Report missing, malformed, unknown, credential, and VOD-path conditions using safe metadata only.
   - Produce the verified manifest and cutoff required by a later import.
   - Explicitly report that persistent domain import is blocked until the target domain tables exist.
2. **2B2 — transactional domain import and database verification**
   - Begin only after migrations for streams, viewers, samples/events, presets/rules/predictions, and VOD metadata have been designed and implemented in cohesive domain slices.
   - Reuse 2B1's manifest and parser contracts, then persist normalized entities, record the import batch, and compare counts/aggregates.

The command-level `inspect`, `import`, and `verify` interface remains the target. Stage 2B1 implements the side-effect-free inspection/planning application boundary, not a misleading import command that records success without importing domain data.

## Context

Phase 2A intentionally created only six core/system tables:

- `schema_migrations`
- `settings`
- `channel_read_model`
- `operation_log`
- `processed_event_ids`
- `import_batches`

The approved legacy sources also contain viewers, stream metadata, minute samples, events, messages, presets, rules, predictions, and VOD metadata. None of the corresponding target tables exists yet. Storing those records in settings, operation logs, or opaque import-batch JSON would violate the normalized model, privacy boundaries, and the rule against silent loss.

## Consequences

- Inspection, redaction, source immutability, unsafe-path handling, and deterministic reports can be implemented and tested immediately using synthetic fixtures.
- No real runtime data or operational mount is required or accessed.
- Unknown fields and malformed lines remain represented by the immutable source artifact plus report; they are not falsely marked imported.
- A completed 2B1 report has `import_ready=false` with a stable `domain_schema_unavailable` blocker until all required destination schemas are present.
- Import idempotency and transaction rollback are fully proven in 2B2, while 2B1 proves deterministic manifests and source-change detection.
- Production entry points, legacy writers, deployment, and data mounts remain unchanged throughout both stages.

## Destination-schema sub-staging

Stage 2B2 is itself split so that a schema/repository change remains reviewable
without hiding a source import inside it:

1. **2B2A — domain destination schema and repositories** adds only the
   `streams`, `stream_samples`, `viewers`, and `vod_assets` persistence
   boundary. It has no source-reader, importer, command, or operational
   database wiring. Unknown entity metadata is accepted only through the same
   secret/path-safe immutable JSON boundary as other v2 metadata.
2. **2B2B — transactional importer and verifier** consumes a completed 2B1
   report/manifest and the 2B2A repositories. It is responsible for source
   re-verification, mapping, batch identity, rollback, aggregate comparison,
   and refusal of unresolved credentials or unsafe VOD paths.

`viewer_streams`, stream counters, normalized events/chat messages, presets,
rules, predictions, and archive jobs stay outside 2B2A. Their relation,
retention, or command semantics need separate decisions. This keeps the first
destination schema limited to what legacy stream-index, viewer, minute-sample,
  and VOD metadata can represent without storing raw JSONL payloads or media.

### Candidate-only import boundary

The first 2B2B implementation targets an explicitly supplied, disposable
candidate SQLite database only. It does not create or open the operational
default database, call `migrate()` implicitly, or provide a CLI/cutover path.
Its caller supplies a completed 2B1 report and the same staged source roots;
the importer re-verifies the manifest before parsing and again before the
candidate transaction commits.

One deterministic batch identity is derived from safe source reference,
manifest checksums, and importer version. A fresh candidate database may gain
one batch atomically; a verified matching batch is a no-op; any differing batch
or pre-existing domain state is refused. This deliberately favors rehearsal
clarity over incremental operational imports.

The first mapping imports only stream-index metadata, valid minute samples,
viewer records, and safe VOD metadata. It does not persist config/settings,
credential values, raw chat/event/census data, viewer-stream relations,
presets/rules/predictions, archive jobs, unsafe VOD paths, or unrepresentable
unknown values. Those omissions are explicit safe counts in the candidate
report while the immutable source artifact remains the lossless record.

## Rejected alternatives

### Store all legacy entities inside `import_batches`

Rejected because it turns report metadata into an unbounded raw datastore, duplicates private payloads, and bypasses normalized repositories.

### Mark only settings imported and report overall success

Rejected because most source entities would remain unpersisted while the batch appeared complete.

### Add every domain table and importer in one slice

Rejected because schema decisions, normalization, repository behavior, and migration verification would be too broad for one independently reviewable change.
