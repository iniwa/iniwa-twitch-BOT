# v2 Phase 2B2B: candidate-only legacy importer and verifier

Status: completed — implementation, verification, and final independent review complete (2026-08-13).

## Goal

Implement a source-preserving, offline-only application boundary that imports a
completed 2B1 staged-source inspection into an explicitly supplied disposable
candidate v2 SQLite database, then verifies count/aggregate parity. It must be
fully transactional and deterministic, with no operational database, cutover,
runtime, UI, or CLI integration.

## Background

2B1 provides safe source inventory/inspection and manifests. 2B2A provides the
only destination tables currently suitable for this work: `streams`,
`stream_samples`, `viewers`, and `vod_assets`, plus existing `import_batches`.
The staged decision is in
`docs/decisions/2026-08-13-legacy-importer-staging-order.md`, including the
candidate-only boundary added for this slice.

## Data sources

- `AGENTS.md`, `CLAUDE.md`
- `docs/rebuild/04-data-and-api.md` sections 4.2, 4.3, 4.6, 6–7, 15
- `docs/rebuild/05-migration-and-delivery.md` Phase 2 and rollback/exit gates
- `docs/rebuild/06-quality-security-operations.md`
- `docs/decisions/2026-08-13-legacy-importer-staging-order.md`
- archived 2B1 and 2B2A handoffs
- `src/twitchbot/migration/inspector.py`
- `src/twitchbot/application/persistence.py`
- `src/twitchbot/adapters/persistence/{sqlite.py,migrations.py,repositories.py}`
- v2 persistence and inspector tests

All test sources, downloads roots, and databases are synthetic `tmp_path`
fixtures. Do not inspect runtime `data/`, credentials, downloaded media,
`data.db`, production configuration, or an operational database.

## Files to edit

- New `src/twitchbot/migration/importer.py`
- `src/twitchbot/migration/__init__.py`
- `src/twitchbot/migration/inspector.py` only if a small public, read-only VOD
  classification helper is necessary to avoid duplicating its containment
  policy; retain all 2B1 behavior/tests
- New focused `tests/test_v2_candidate_importer.py`
- `tests/test_v2_import_safety.py` only to guard the new module import
- Existing v2 persistence/inspector tests only for necessary contract coverage

Do not edit migration 0001/0002, domain DTOs/repositories, legacy production
code/tests, web/runtime/settings/null adapters, build/container/deployment
files, runtime data, credentials, VOD media, or the operational default DB.
No CLI, route, command-line report writer, or cutover action is in scope.

## Public candidate-import boundary

Add immutable migration-package records and a small service:

- `CandidateImportError(code, context)` is a safe typed error; its string never
  contains supplied IDs, field values, notes, tokens, source paths, VOD paths,
  SQLite messages, or raw JSON.
- `CandidateImportReport` is immutable and exposes only safe source reference,
  deterministic batch ID, report cutoff, result/no-op state, safe manifest
  file metadata (relative name/size/checksum), per-entity read/imported/skipped
  /rejected/deferred counts, parity aggregates, deferred-category counts, VOD
  result-code counts, and `source_unchanged` / `credentials_redacted` flags.
  Its `to_safe_mapping()` has no record IDs, names, notes, chat/event text,
  tokens, absolute paths, raw values, or operational candidate path.
- `CandidateImporter(source_root, downloads_root, source_reference, database,
  *, clock=...)` is inert: constructor validates only supplied types/absolute
  lexical paths and candidate-database policy. It must reject an exact
  `DEFAULT_DATABASE_PATH` candidate without opening it. It must not call
  `database.migrate()`; callers explicitly migrate synthetic candidate DBs.
- `import_report(report)` and `verify_import(report)` accept only a completed
  `InspectionReport` with matching source reference and current manifest. They
  make no network/thread/subprocess/environment calls and do not access any
  default/operational database.

The importer owns a separate `LegacySourceInspector` configured from its input
roots/reference. Before parsing it must call `verify_unchanged(report)` and
perform a fresh semantic inspection comparison (manifest, unsupported entries,
documents, issues, unknown fields, credential states, and VOD aggregate
classes; ignore only clock-derived cutoff/elapsed values). It must re-verify
the original report immediately before commit, while the candidate transaction
is still open. A source change at any point rolls back all candidate writes and
raises a safe `source_changed` error.

## Candidate target / batch rules

- Only an explicitly supplied non-default `SQLiteDatabase` may be used. The
  importer never initializes/migrates it. Missing/incorrect candidate schema
  maps to a safe candidate-schema error.
- Candidate import requires a valid `config.json` with a non-empty string
  `broadcaster_id`; this is the `streams.channel_id`. Config settings are not
  imported in this slice.
- Any configured credential state in the inspection report fails closed with
  `credential_validation_required`; access/broadcaster token values are never
  parsed into output/database/error. Missing/not-configured credential keys do
  not by themselves block a synthetic candidate import.
- Main viewer/index documents may be absent/invalid or contain rejected records
  only if the report and result explicitly record those records as deferred;
  malformed/blank/oversized/invalid JSONL lines are similarly skipped while
  later valid lines continue. A malformed/absent config or no valid
  broadcaster ID fails before candidate writes.
- Derive a deterministic opaque batch ID from canonical safe data only:
  importer version, source reference, cutoff, and sorted manifest
  `(name,size,checksum)`. Never use absolute roots or source content. Insert a
  canonical manifest in `import_batches` with a fixed safe importer version,
  result `completed`, and no report file reference.
- Target must be a fresh candidate state. If a matching batch exists and
  independently verifies source/candidate parity, return an immutable no-op
  report with no write. If that batch has different safe manifest/cutoff/source
  metadata or verification fails, return `batch_conflict`/
  `candidate_verification_failed`; if another batch or any domain row exists,
  return `candidate_not_empty`. Never delete/upsert existing candidate data.
- For a fresh candidate, one `BEGIN IMMEDIATE` transaction inserts batch,
  streams, samples, viewers, then VOD assets. Any parsing, mapping, duplicate,
  FK, SQLite, source-change, or verification failure rolls back every row,
  including the batch. No network/media/source action happens in the
  transaction except the final non-mutating source inventory verification.

## Honest mapping / deferrals

Only map validated legacy values; do not coerce booleans, non-finite numbers,
naive timestamps, malformed duration strings, or unknown shaped values.
Legacy offset timestamps are parsed as aware instants and stored canonical UTC.
All errors/reports use codes/counts rather than values.

### Streams

- Each valid `history/stream_index.json` key/record becomes a stream only when
  the key is non-empty text, title is non-empty text, and `start_time` is an
  aware timestamp. Map key → `id`, config broadcaster ID → `channel_id`, title,
  game name, thumbnail, valid integer max/follower/comment aggregates, finite
  average viewers, parsed `HH:MM:SS`/`MM:SS` duration, and `source='imported'`.
- Tags may be taken from valid corresponding JSONL `stream_info.tags`; otherwise
  remain an empty tuple. Use `completeness='partial'` when at least one valid
  sample is imported and `metadata_only` otherwise. Do not claim `full`.
- Do not store raw/unknown/transient index values in this slice. Count them as
  deferred using existing inspection unknown-field results; use empty safe
  legacy metadata. The immutable source artifact remains the lossless record.

### Samples

- A `history/stream_<id>.jsonl` line maps only when that stream was imported,
  its timestamp is aware, and its documented metric fields have compatible
  numeric types. Map viewer/chat/message-rate/bits/gifts/follower-total into
  `stream_samples`; omitted fields remain `NULL`.
- Use a bounded line reader and strict duplicate/non-finite checks. Invalid,
  blank, oversized, malformed, orphan-stream, or structurally incompatible
  lines are counted deferred/rejected while later valid lines continue. A
  duplicate `(stream_id, timestamp)` fails the entire candidate transaction
  rather than silently changing aggregates. Raw messages/events/census/emotes
  /badges/subs/points/raids remain deferred; no raw payload is stored.

### Viewers

- Valid `viewers.json` key/record maps to `ViewerRecord` with exact legacy
  field names: `name→display_name`, `login`, visits/duration/comments/bits,
  subscription/gift/streak fields, aware timestamps (or numeric epoch only for
  `last_seen_ts`/`last_sub_ts` when valid), `last_stream_id`, and `memo→note`.
- A malformed/incompatible record is rejected/deferred, not coerced. Notes and
  viewer IDs may exist inside the candidate DB but never enter reports/errors.
  Unknown values remain deferred/source-preserved rather than silently stored.

### VOD metadata

- Create at most one `vod_assets` row per imported stream only when safe legacy
  VOD metadata exists (`vod_id`, status, or a classifier-approved path).
- Reuse/extend 2B1's VOD containment policy without opening or reading media.
  Store only a classifier-approved safe relative path; convert a native
  absolute-inside path to relative form only after containment/link checks.
  Other file paths are not persisted and are counted by safe VOD result code.
- Map legacy statuses conservatively to non-empty local state codes
  (`downloaded→present`, `not_downloaded→missing`, `failed→failed`,
  `downloading→deferred`, otherwise `unknown`); remote state is `known` only
  for a non-empty string VOD ID, otherwise `unknown`. This importer never
  reads/moves/deletes/downloads VOD bytes or creates archive jobs.

Deferred: all config/settings/layout/presets/rules/predictions, credentials and
actor validation, viewer-stream relations, counters, raw messages/events/
census, archive jobs, unsafe/unrepresentable VOD path values, and unknown raw
entity values. Candidate reports must make these omissions visible as safe
categories/counts.

## Verification contract

`verify_import(report)` reparses/revalidates the same source and checks the
candidate batch's safe metadata plus exact counts and safe numeric aggregates:
stream/viewer/sample/VOD count; sum of non-null sample viewer/chat/bits/gift
values; and stream max/follower/comment sums. It returns a safe immutable
report or raises `candidate_verification_failed` without modifying either
source or candidate DB. `import_report` runs this parity check before reporting
success/no-op.

## Acceptance criteria

- Constructor/import/module imports are inert until explicit method call; no
  default DB creation/open, source write, report file, network, thread,
  subprocess, environment lookup, Flask, legacy module import, or media read.
- Valid synthetic source imports only into explicitly migrated candidate DB,
  produces deterministic safe batch/report, preserves source bytes+mtime, and
  maps all four approved domain classes with nullable values/UTC/aggregate
  parity.
- Config credentials block safely; config/mapping/source/report mismatch,
  unsafe VOD values, malformed JSONL continuation, unknown/deferred source
  fields, duplicate sample, candidate schema/nonempty/conflicting batch, and
  injected SQL failure are safely handled.
- Failure after any proposed row insertion leaves no batch/domain row; a
  matching verified rerun is a no-op with no growth; modified source/manifest
  rejects with no candidate write.
- Source change during parse/transaction is detected by final verification and
  rolls back. Candidate verification detects changed/deleted candidate rows.
- Tests inspect report/error/repr with synthetic token, identity, note, chat,
  and path sentinels and prove no leak.
- Focused importer + affected v2 persistence/inspector/import-safety tests and
  full suite pass in the isolated verification venv; `compileall` and
  `git diff --check` pass; a stable writer self-review and one independent
  final review leave no High/Medium issue.

## Constraints

- Python 3.12, standard library, arm64-compatible.
- Use `apply_patch`, package-relative imports, fresh SQLite connection, short
  explicit transaction, and `PRAGMA foreign_keys=ON` from existing factory.
- Never inspect/read/write actual mounts or VOD media. Tests own all synthetic
  source/download/candidate paths.
- Preserve every protected legacy behavior, including cached stream status and
  automatic VOD download default off.

## Non-goals

- No production migration/cutover/backup/rollback exporter, operational DB,
  CLI, route, UI, worker, live runtime, EventSub/Twitch/OAuth, or settings
  import.
- No import of presets/rules/predictions/layout, viewer-streams, counters,
  raw events/chat/census, archive jobs, or unknown raw entity values.
- No media operation, secret storage, dependency/build/deployment change,
  commit, push, image publication, or deployment.

## Verification

- `python -B -m compileall -q src/twitchbot tests`
- Focused `tests/test_v2_candidate_importer.py` plus affected persistence,
  inspector, and import-safety tests in the isolated verification venv.
- Full `tests` suite in that venv.
- Guarded construction/import/source/candidate smoke; source mtime/checksum
  comparison; `git diff --check`; changed-file/status review; one independent
  final review.

## Expected report

- Candidate importer/report API and explicitly limited mappings delivered.
- Focused/full test counts and commands.
- Evidence of candidate-only atomic/no-op/rollback/verification behavior and
  source/media/credential privacy.
- Explicit remaining production cutover, settings import, raw activity,
  command, runtime, and UI work.

## Independent-review correction (2026-08-13)

The first implementation passed its focused and full suites, but an independent
review found one High and two Medium gaps.  This correction is limited to the
candidate importer and its focused tests; do not broaden the slice.

- Preserve the accepted `InspectionReport` cutoff when deriving the stable
  batch identity after a fresh semantic/source validation.  A later inspection
  may have a different clock-derived cutoff, but the same unchanged accepted
  report must deterministically find and independently verify the existing
  batch, then return `no_op`; it must not report `candidate_not_empty`.
- Validate the candidate schema shape/version before beginning a write
  transaction.  A database that merely has the five table names but has a
  missing/wrong table definition must fail closed as `candidate_schema_invalid`,
  never as an incidental write error.
- Add synthetic regression coverage for the above, plus duplicate sample
  rollback, injected SQL/write failure rollback, source change during the
  parse/transaction window, unsafe VOD classifications without media-byte
  reads, nonempty/batch-conflict candidate variants, strict UTC/nullable
  mapping, and report/error/repr privacy sentinels.  The tests must use a
  normally advancing inspector/importer clock for the stable no-op case.

Re-run the isolated-venv focused and full suites, compileall, and diff check.
After the correction, obtain one fresh independent final review before moving
this handoff to the archive.

## Contract reset (2026-08-13): commit-boundary source immutability

The first correction was implemented and independently reviewed, but the final
review found that the source check preceded an in-transaction aggregate query.
A source change in that query window could therefore be observed only after a
successful commit.  Reset this last narrow concern before any further work:

- In the candidate transaction, complete all destination reads/writes and
  aggregate calculation first.  Call `verify_unchanged(original_report)` as
  the final operation immediately before `commit()`; any failure must roll
  back the batch and every domain row.
- Add a synthetic regression that mutates a source document from the aggregate
  hook (without raising) and proves `source_changed` plus zero candidate rows.
- Do not alter schema, mapping, runtime, or any legacy behavior.  Re-run the
  focused/full isolated-venv suites, compileall, diff check, and one final
  independent review after this reset.

## Completion evidence

- Candidate importer and its focused synthetic tests were implemented without
  touching operational data, media, credentials, runtime wiring, or legacy
  production code.
- Isolated verification: focused affected v2 tests `155 passed, 2 skipped`;
  full suite `192 passed, 2 skipped`; `python -B -m compileall -q
  src/twitchbot tests` and `git diff --check` passed.
- The final independent review found no High or Medium issue.  It specifically
  confirmed the source check is the final operation before commit and the
  aggregate-mutation rollback regression leaves every candidate table empty.
