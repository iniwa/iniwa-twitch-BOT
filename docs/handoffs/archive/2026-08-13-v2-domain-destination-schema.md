# v2 Phase 2B2A: domain destination schema and repositories

Status: completed on 2026-08-13.

Completion verification: focused domain/core/import-safety suite `124 passed`;
full suite `184 passed, 2 skipped`; `compileall` and `git diff --check`
passed. The two skips are capability-based synthetic symlink cases in the
source-inspector tests. A fresh final independent review found no actionable
High/Medium issue. No production database, legacy source, credentials, media,
runtime wiring, build, or deployment behavior changed.

Status: active.

## Goal

Add the smallest isolated v2 SQLite destination boundary needed before a later
legacy importer can persist inspected stream history, viewer records, minute
samples, and VOD metadata. The slice is schema/DTO/repository-only: it must
not read legacy sources, perform an import, create an operational database, or
wire v2 into the legacy runtime.

## Background

Phase 2A provides only the system/core tables. Completed 2B1 safely inspects a
synthetic staged source and permanently reports `import_ready=false` until
domain destination tables exist. The staged importer decision, including this
2B2A/2B2B split, is in
`docs/decisions/2026-08-13-legacy-importer-staging-order.md`.

## Data sources

- `AGENTS.md`, `CLAUDE.md`
- `docs/rebuild/04-data-and-api.md` sections 4.2, 4.3, 4.6, 6–7
- `docs/rebuild/05-migration-and-delivery.md` Phase 2 and rollback sections
- `docs/rebuild/06-quality-security-operations.md` persistence/test rules
- `docs/decisions/2026-08-13-legacy-importer-staging-order.md`
- `src/twitchbot/application/persistence.py`
- `src/twitchbot/adapters/persistence/{sqlite.py,migrations.py,repositories.py}`
- `tests/test_v2_persistence.py`, `tests/test_v2_legacy_source_inspector.py`

Use only synthetic `tmp_path` databases and fixtures. Do not inspect runtime
`data/`, credentials, downloaded media, `data.db`, or production configuration.

## Files to edit

- `src/twitchbot/application/persistence.py`
- `src/twitchbot/adapters/persistence/migrations.py`
- `src/twitchbot/adapters/persistence/repositories.py`
- `src/twitchbot/adapters/persistence/__init__.py`
- `tests/test_v2_persistence.py` only to preserve/clarify the Phase 2A core
  assertions after a second migration exists
- New focused `tests/test_v2_domain_persistence.py`
- `tests/test_v2_import_safety.py` only if needed to guard newly exported
  imports

Do not edit legacy production code/tests, v2 web/runtime/settings/null/migration
inspector behavior, build/deploy/container files, real data, credentials, or
downloads. No source importer, CLI, route, worker, data migration, or external
adapter is part of this handoff.

## Migration 0002 contract

Add one immutable, checksummed, contiguous migration after `core_system`, named
for this four-table domain slice. It creates exactly these tables and directly
useful indexes; no credential-shaped columns/tables:

1. `streams`
   - `id` primary key and non-empty `channel_id` identity.
   - metadata: non-null `title`, nullable `game_id`, `game_name`,
     `thumbnail_url`, and `tags_json` constrained to a JSON array.
   - time: non-null UTC `started_at`, nullable UTC `ended_at`, nullable
     non-negative integer `duration_seconds`.
   - source/completeness: `source` limited to `bot|api|imported`; completeness
     limited to `full|samples_only|metadata_only|partial`.
   - nullable non-negative aggregates `max_viewers`, `average_viewers`,
     `follower_count`, `total_comments`; `NULL` means missing and must not be
     converted to zero by this boundary.
   - non-null JSON-object `legacy_metadata_json`, nullable `import_batch_id`
     foreign key to `import_batches`, UTC `created_at`/`updated_at`, and
     non-negative `revision`.
   - add a chronological lookup index on `started_at` plus stable ID.
2. `stream_samples`
   - composite primary key (`stream_id`, `sampled_at`); stream foreign key with
     `ON DELETE CASCADE`.
   - nullable non-negative metrics: `viewer_count`, `chat_count`,
     `messages_per_minute`, `bits`, `gift_subscriptions`, `follower_total`.
     Preserve omitted values as `NULL`; accept integral or finite fractional
     message rate only through the repository.
   - add a stream/timestamp lookup index only if not redundant with the
     primary-key order; do not add speculative analytics indexes.
3. `viewers`
   - non-empty `user_id` primary key; nullable `login`, `display_name`,
     `followed_at`, `unfollowed_at`, lifetime/subscription/gift/streak numeric
     fields, `last_sub_at`, `last_sub_plan`, `last_seen_at`, `last_stream_id`,
     and private `note`.
   - `is_subscriber` is nullable or a strict SQLite boolean; omitted legacy
     state must remain distinguishable from false.
   - numeric values are nullable, non-negative values; no implicit zero
     normalization in this slice.
   - non-null safe JSON-object `legacy_metadata_json`, UTC `created_at` and
     `updated_at`, non-negative `revision`; add only login/last-seen indexes
     that support documented reads.
   - do not add a `viewer_streams` foreign-key relation yet: 2B1's census lines
     do not establish a durable relation contract.
4. `vod_assets`
   - non-empty asset `id` primary key; unique, cascading `stream_id` foreign
     key; nullable `twitch_vod_id`, `relative_path`, `size_bytes`,
     `discovered_at`, and `verified_at`; non-empty `remote_state` and
     `local_state`; non-negative revision.
   - `relative_path` may be null but, when present, is canonical safe relative
     POSIX text. The repository rejects absolute POSIX/drive/UNC values,
     backslashes, empty/dot/parent components, and non-string values. The
     schema adds basic defense-in-depth checks but never inspects or modifies
     media.

All audit/timeline fields cross the boundary as aware UTC datetimes and are
stored in the Phase 2A RFC3339 `Z` form. Constraints and repositories must
reject booleans where numbers are expected, non-finite floats, malformed JSON,
bad timestamps, unsafe metadata, stale revisions, duplicate sample keys, and
foreign-key failures with existing safe typed `PersistenceError` conventions.
No exception may echo supplied IDs, notes, metadata, paths, SQLite errors, or
stored values.

## DTO and repository contract

Add immutable, detached domain records independent of `sqlite3`, using the
existing `FrozenObject`/`freeze_json_object`/`thaw_json` pattern. The precise
record class names may follow the existing style, but their public fields must
map one-to-one to the approved columns and expose audit revision/timestamps on
reads.

- `StreamRepository`: get and optimistic put/create/update by stream ID.
  Creation uses expected revision 0 and returns revision 1; update requires an
  exact expected revision and increments it. The repository controls audit
  timestamps through its injected clock, retaining `created_at` on update.
- `StreamSampleRepository`: append and list samples in deterministic timestamp
  order. Duplicate composite keys fail rather than silently replacing data.
- `ViewerRepository`: get and optimistic put/create/update with the same
  revision semantics as streams. Viewer note is a direct private field, not
  metadata and never included in error strings/tests' safe reports.
- `VodAssetRepository`: get by asset ID and stream ID plus optimistic
  put/create/update. One asset per stream is enforced by schema and repository.

Domain legacy metadata must be a detached JSON object and pass the existing
recursive secret-shaped-key and absolute-private-path rejection policy. Unknown
source values are not parsed or persisted by this slice; a future importer can
only send already-sanitized entity metadata. Direct VOD paths use no filesystem
or environment lookup.

Existing Phase 2A repository behavior and `MIGRATIONS[0]` checksum/schema must
remain unchanged. Update broad persistence tests so they assert the full
approved eight-table schema and separately protect the exact six-table core
migration rather than retaining an obsolete total-table assertion.

## Acceptance criteria

- Import/construction remains side-effect free: no database open, source read,
  filesystem write, thread, network, subprocess, environment lookup, Flask, or
  legacy module import.
- Temporary-database migration runs forward/idempotently, verifies all exact
  columns/checks/indexes/FKs, and preserves the existing core schema/checksum.
- Repository tests cover valid create/get/update, detached nested metadata,
  stale revision, invalid DTO kinds/timestamps/numbers/JSON, corrupt stored
  JSON, duplicate samples/assets, foreign-key/cascade behavior, and safe error
  redaction.
- VOD repository tests cover only lexical safe-relative validation; no media
  read, `Path` existence check, symlink traversal, source source inspection, or
  download-root lookup is permitted in this slice.
- Tests prove nullable metrics/counters remain `NULL` instead of zero and
  stored read values use UTC.
- Existing 2B1 inspector remains `import_ready=false`; no import batch is
  created by this slice.
- Focused new and existing v2 tests, full suite, guarded import smoke,
  `compileall`, and `git diff --check` pass. One independent final review has
  no unresolved High/Medium finding.

## Constraints

- Python 3.12 / standard library / arm64 compatible.
- Use `apply_patch`, package-relative imports, fresh SQLite connections, short
  explicit transactions, and `PRAGMA foreign_keys=ON` from the existing
  factory.
- Do not open `/app/data/twitchbot-v2.sqlite3`; all tests use `tmp_path`.
- Do not add dependencies, build/deploy changes, source import, real
  credentials, runtime wiring, or media activity.
- Preserve VOD automatic-download default and all protected legacy behavior.

## Non-goals

- No 2B2B importer/verifier, source re-verification, batch creation, mapping,
  idempotent import, rollback exporter, or cutover.
- No viewer-stream relation, stream counters, events, chat bodies, presets,
  rules, predictions, archive jobs, analytics query/UI, Twitch/EventSub,
  downloader, credential storage, routes, workers, or dashboard changes.
- No commit, push, image publication, deployment, or production data access.

## Verification

- `python -B -m compileall -q src/twitchbot tests`
- Focused `tests/test_v2_domain_persistence.py` plus affected existing v2
  persistence/import-safety tests in the isolated verification venv.
- Full `tests` suite in that venv.
- Guarded import/construction smoke, `git diff --check`, changed-file/status
  inspection, writer self-review, and one bounded independent review.

## Expected report

- Exact migration/table/repository contracts delivered.
- Focused/full test counts and commands.
- Confirmation that legacy/runtime data, credentials, media, production DB,
  build/deployment, and protected routes were untouched.
- Remaining 2B2B importer and later UI/API work stated explicitly.

## Contract reset: domain read validation and strict identity types

Status: active; the first implementation is not accepted yet. An independent
review found two Medium safety gaps. This reset is limited to correcting those
gaps and completing their focused regression coverage; it authorizes no new
product scope.

1. Repository read paths must fail closed if a temporary/test corruption
   bypasses SQLite constraints. Before constructing any domain DTO, validate
   stored types, UTC timestamps, revision, enum/state values, nullable
   non-negative/finite metrics, JSON object/array shape, strict nullable
   booleans, and lexical VOD relative paths. Stored malformed values must raise
   a stable `PersistenceError` without echoing values, IDs, notes, paths, or
   SQLite messages.
2. DTO input validation must use exact string/non-empty checks for all
   identities and state/enum strings before membership checks. Invalid types,
   including unhashable values, must yield safe `PersistenceError`, never
   `TypeError` or implicit SQLite TEXT coercion.

Required tests:

- With `PRAGMA ignore_check_constraints=ON` in temporary databases only, inject
  representative corrupt rows for every domain read path (`streams`, samples,
  `viewers`, and VOD assets) and assert each fails closed/redacted.
- Exercise invalid identity/state/enum types, booleans/non-finite/negative
  numerics, invalid timestamp and JSON shapes, stale revisions, duplicate/FK
  failures, and safe VOD lexical variants through public repositories.
- Add direct schema/index/FK checks sufficient to protect the approved
  migration-0002 contract. Keep tests synthetic and do not open the
  operational database.

Preserve no source import, no media/source filesystem access, no runtime
wiring, and the Phase 2A migration checksum. Re-run focused and full tests,
compileall, and diff check. One fresh final independent review follows this
correction.

## Second contract reset: direct migration-0002 schema protection

Status: active. The fresh final review found one remaining Medium issue: tests
exercise repositories but do not directly protect the approved migration-0002
database contract. This reset is test-only unless an assertion exposes a real
schema defect. No new schema/product scope is authorized.

Add synthetic temporary-database tests that directly assert:

- exact approved domain table columns and migration-0002 table set;
- `streams_started_at_id_idx`, `viewers_login_idx`, and
  `viewers_last_seen_idx` key order;
- the `stream_samples(stream_id, sampled_at)` composite primary-key order;
- foreign-key targets/actions for samples and VOD assets, including VOD's one
  asset per stream uniqueness;
- representative SQL constraint failures for invalid stream source/completeness
  or tags shape, negative sample metrics, invalid viewer boolean/numeric
  values, and unsafe/duplicate VOD values.

The tests must use only `tmp_path` SQLite databases and must not embed private
values. Do not weaken existing migrations or constraints to make the tests
pass. Retain all previous source/media/runtime isolation guarantees. Re-run the
focused suite, full suite, compileall, and diff check, then obtain one final
independent review.

## Third contract reset: independent schema-regression assertions

Status: active. The prior test-only correction still left two Medium test
quality gaps. This is a further test-only refinement, not authorization to
change production code or scope.

- Assert the complete application table set as exactly the six protected core
  tables plus the four migration-0002 domain tables; a subset assertion is not
  sufficient.
- Make every representative raw-SQL constraint failure independent: valid tags
  with invalid `source`; valid tags/source with invalid `completeness`; valid
  enum values with non-array tags; one negative viewer metric; one invalid
  viewer boolean; VOD stream uniqueness; and one absolute or traversal VOD
  path. A single row must not rely on two failing constraints at once.

Use only harmless synthetic identifiers/paths in `tmp_path` databases. Do not
alter schemas, repositories, production wiring, legacy sources, media, or
runtime behavior. Re-run focused/full verification, then one final independent
review.

## Fourth contract reset: component-safe VOD SQL and complete repository coverage

Status: active. The latest independent review found two Medium issues. This
reset replaces the prior acceptance gate; implementation is not accepted until
both are resolved. It remains strictly within the existing domain
schema/repository/test boundary.

1. Align the migration-0002 VOD `relative_path` SQL defense with the repository
   contract. It must reject absolute paths, backslashes, empty components, and
   `.` / `..` *components*, but must permit safe filename text containing two
   dots (for example `archive/name..part.mp4`). Update only migration 0002
   and its direct regression tests; migration 0001 must remain byte-for-byte
   unchanged. No existing operational v2 database is opened or migrated.
2. Complete focused domain repository coverage rather than relying on a few
   smoke cases. With synthetic temporary DBs only, prove:
   - successful create/update with revisions and retained creation timestamp;
   - nested metadata detachment and recursive secret/absolute-path rejection;
   - safe error redaction for DTO and corrupted stored values;
   - invalid identity/state/enum types (including unhashable types), nullable
     and required timestamps, bool/non-finite/negative metrics, invalid JSON
     metadata/tags, stale revisions, duplicate samples/VOD assets, and missing
     foreign keys;
   - fail-closed stored-row behavior across every domain read/list path for
     JSON metadata/tags, timestamps, nullable numbers/booleans, enum/state,
     revisions, and lexical VOD paths;
   - repository-level VOD uniqueness/FK behavior without any media/path
     filesystem access.

Tests must preserve values' privacy: sentinels in IDs, note, metadata, and
paths may be used only to assert they do not appear in `PersistenceError` text
or public safe records. Use `PRAGMA ignore_check_constraints=ON` only in
temporary corruption fixtures and restore it in `finally`. Add no importer,
source scan, runtime wiring, dependencies, production DB access, media access,
or scope beyond the approved four tables. Re-run focused/full tests,
compileall, and diff check. The next review must be a fresh independent review.

## Fifth contract reset: SQLite literal correctness and auditable test matrix

Status: active. The fourth correction did not meet its own exit gate. A fresh
review reproduced a single-backslash VOD path being accepted by migration 0002
and confirmed material test-matrix gaps. This reset is narrowly limited to
those defects; do not begin import work or change unrelated behavior.

### Production correction

In migration 0002 only, make the generated SQLite `LIKE` pattern match one
literal backslash, not a pair. A raw SQL insert of a synthetic
`folder\\file.mp4` path must fail, while `archive/name..part.mp4` must succeed.
The DDL must continue to reject absolute, empty, `.` and `..` path components.
Do not change migration 0001, open an operational database, or attempt a
runtime migration.

### Required auditable test matrix

Expand `tests/test_v2_domain_persistence.py` with small, named synthetic tests
or a clearly readable parameterized matrix. Each item below needs a direct
assertion, not a broad catch-all smoke assertion.

1. **Input boundaries**
   - Every repository rejects non-string/empty identities before SQL; stream
     source/completeness reject invalid and unhashable values without leaking
     `TypeError`.
   - Required/optional timestamps reject missing, naive, non-UTC and wrong
     types; numeric fields reject booleans, negatives, and non-finite floats.
   - Tags and legacy metadata reject wrong containers/elements and recursively
     reject credential-shaped keys and absolute paths. Test error redaction
     with synthetic sentinel values for ID/note/metadata/path.
   - VOD IDs/states, optional Twitch VOD id, size, and all lexical path cases
     (safe dotted, one backslash, slash/double slash, empty/dot/parent,
     absolute/drive/UNC) are tested through repository APIs where applicable.
2. **Write/update boundary**
   - Stream and viewer creation/update use exact optimistic revisions and keep
     `created_at`; VOD update increments revision.
   - Samples reject duplicate composite keys and missing stream FKs.
   - VOD repository rejects missing-stream FKs, duplicate asset IDs, and a
     second asset for a stream; update collision behavior is tested through the
     repository, not only raw SQL.
3. **Stored-row fail-closed boundary**
   - `StreamRepository.get`: corrupt tags JSON / metadata JSON, audit and
     source/completeness values, a nullable numeric, and revision/timestamp.
   - `StreamSampleRepository.list`: corrupt timestamp and nullable count/rate,
     including bool/non-finite where SQLite permits representation.
   - `ViewerRepository.get`: corrupt metadata JSON, timestamps, nullable
     numeric, subscriber boolean, and revision.
   - both `VodAssetRepository.get` and `get_by_stream`: corrupt relative path,
     timestamps, nullable size, states, and revision.
   - Each case must assert a safe `PersistenceError` whose string excludes the
     injected sentinel. Use `PRAGMA ignore_check_constraints=ON` only around a
     committed mutation in `try/finally`, restoring it to `OFF` even on failure.
4. **Direct DDL contract**
   - Retain exact table/index/PK/FK/unique and independent raw-SQL constraints
     from prior resets; add one raw single-backslash VOD failure and safe-dotted
     success to prove the corrected literal semantics.

If SQLite cannot store a given synthetic non-finite or type value directly,
test that repository input rejects it and document the SQLite limitation in a
brief test comment; do not weaken the production constraints. Keep test code
clear enough for a reviewer to trace every handoff bullet. After implementation
run focused/full tests, compileall and diff check. A fresh independent reviewer
must find no High/Medium issue before acceptance.

## Sixth contract reset: migration-0001 compatibility and remaining boundary cases

Status: active. The fifth review found no production defect, but two Medium
test-contract gaps remain. This is test-only unless an assertion reveals an
actual defect. Do not alter migration 0001 or any production behavior.

1. Add a fixed golden regression assertion for `MIGRATIONS[0]`: version, name,
   and SHA-256 checksum must be exact. The expected checksum is derived once
   from the currently accepted core migration; do not compute the expected
   value from the subject under test. Retain the existing core table/column
   checks so both history compatibility and physical schema are protected.
2. Add concise direct tests for wrong domain metadata containers (not merely
   secret/path content) and non-UTC optional viewer/VOD timestamps. Keep the
   existing stream coverage; do not weaken UTC rules.
3. The old stored-row corruption test must use the existing `_corrupt` helper
   or an equivalent `try/finally` so `PRAGMA ignore_check_constraints` is
   restored to `OFF` even if the mutation/assertion raises. Prefer removing
   redundant older test code if the expanded fail-closed matrix already covers
   it, rather than retaining two subtly different fixtures.

Use only synthetic temporary DBs; no operational DB, source, media, runtime,
or legacy changes. Run focused/full tests, compileall, diff check, then one
fresh independent final review.
