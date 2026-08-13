# v2 Phase 2A: SQLite core schema and repositories

Status: completed on 2026-08-13 after contract reset and privacy correction.

Completion verification: persistence/import-safety focused suite `44 passed`; full legacy and v2 suite `81 passed`; guarded import, `compileall`, and `git diff --check` passed. Independent review confirmed all earlier migration/repository High/Medium findings were resolved; its final Medium privacy finding was corrected with absolute-path rejection and an allowlisted import-manifest schema, then reverified by focused/full tests and final primary review.

## Goal

Add an isolated, standard-library SQLite persistence foundation for v2: safe database location policy, per-operation connections, forward-only checksummed migrations, the core/system schema, and transactional repositories. Do not import legacy data or connect persistence to production yet.

## Background

Phase 1 and its typed-settings/Null-adapter completion are implemented and verified. The rebuild plan's next stage is SQLite plus a legacy importer. This handoff covers only Slice 2A. Slice 2B inspect/import/verify commands and all legacy file reads remain out of scope.

## Data sources

- `AGENTS.md`, `CLAUDE.md`
- `docs/rebuild/03-system-architecture.md`
- `docs/rebuild/04-data-and-api.md`
- `docs/rebuild/05-migration-and-delivery.md`
- `docs/rebuild/06-quality-security-operations.md`
- Current `src/twitchbot/` and `tests/test_v2_*.py`

## Files to edit

- New package under `src/twitchbot/adapters/persistence/`
- New persistence DTO/protocol files under `src/twitchbot/application/` only where needed to keep application records independent of `sqlite3`
- New focused tests under `tests/`
- Existing v2 import-safety test only if needed to extend its guarded imports

Do not edit root legacy code/tests, the v2 web/runtime/settings/Null behavior except for a necessary import-only compatibility correction, dependency/build/container/deployment files, or runtime data.

## Database location policy

- Operational default constant: `/app/data/twitchbot-v2.sqlite3`.
- Never open, inspect, migrate, create, or alias a file whose case-insensitive basename is `data.db`.
- Explicit database paths are allowed only through constructor/command input for per-test temporary databases and later migration rehearsal. They must be absolute filesystem paths and use a `.sqlite3` suffix.
- Object construction and module import must not open or create a database. Opening an explicitly requested connection may create the target SQLite file, but must not create missing parent directories.
- This slice must not open the operational default in tests.

## Connection policy

- Use Python's standard-library `sqlite3` only.
- Return a fresh connection for each repository operation/explicit context; never cache or share a connection between threads. Retain SQLite's same-thread enforcement.
- Set and verify on every connection:
  - `PRAGMA foreign_keys=ON`
  - `PRAGMA busy_timeout=5000`
  - `PRAGMA journal_mode=WAL`
- Use `sqlite3.Row`. Transactions must be explicit and short; no network, subprocess, media, or credential work may occur inside them.
- Provide a `quick_check` operation that fails with a safe typed persistence error unless SQLite returns exactly `ok`.
- Do not enable or invent destructive recovery behavior for corrupt/busy databases.

## Migration contract

- Define immutable migrations with positive contiguous versions starting at 1, stable human-readable names, ordered SQL statements, and SHA-256 checksum derived deterministically from version, name, and exact statements.
- Apply migrations forward only, one migration per explicit transaction. A failed migration rolls back its DDL/DML and migration record.
- Re-running the same migration set is idempotent.
- Persist `version`, `name`, UTC RFC 3339 `applied_at`, and checksum in `schema_migrations`.
- Fail closed with safe typed errors when:
  - stored name/checksum differs from code;
  - stored versions are non-contiguous or not a prefix of known migrations;
  - the database schema is newer than the code;
  - migration definitions are empty, duplicated, non-contiguous, or otherwise invalid;
  - SQLite execution/integrity fails.
- Do not implement downgrade or automatic repair.
- Inject a clock callable for deterministic migration/repository tests; require timezone-aware UTC values and serialize with `Z`.

## Migration 0001 schema

Create only the documented core/system tables and their directly useful indexes. Add ordinary `NOT NULL`, primary-key, revision/non-negative, and JSON-validity constraints without inventing domain behavior.

1. `schema_migrations(version, name, applied_at, checksum)`
2. `settings(key, value_json, revision, updated_at)`
3. `channel_read_model(channel_id, title, game_id, game_name, tags_json, active_preset_id, observed_at, source, revision)`
4. `operation_log(id, operation_type, target_type, target_id, state, message_code, request_id, started_at, finished_at, safe_details_json)`
5. `processed_event_ids(message_id, message_type, received_at, expires_at)` plus expiry index
6. `import_batches(id, importer_version, imported_at, cutoff_at, source_manifest_json, source_base_reference, result, report_reference)`

Defer streams/samples/events/chat/viewers/presets/rules/predictions/VOD assets/jobs to later domain slices. Do not add credential/token/secret/authorization/password columns or tables.

## Repository contract

Keep immutable value records independent of Flask and `sqlite3`. Concrete repositories receive the connection factory and open a fresh connection per operation.

### SettingsRepository

- `load()` returns `AppSettings`, aggregate revision, and latest update time. An empty table returns code-defined defaults at revision 0.
- `save(settings, expected_revision)` writes every allowlisted `AppSettings` field atomically using canonical JSON, assigns one new aggregate revision to all rows, and returns the stored snapshot.
- Reject negative/non-integer expected revisions. A stale expected revision raises a typed `revision_conflict` without leaking values.
- Unknown, malformed, or inconsistent stored rows fail closed; never load credential-shaped settings or silently coerce values.

### ChannelReadModelRepository

- Get by configured `channel_id`; put uses create-at-revision-0/update-at-exact-revision optimistic concurrency and returns an immutable detached record with incremented revision.
- Tags cross the adapter boundary as an immutable string tuple and are stored as canonical JSON.
- Reads never call Twitch.

### OperationLogRepository

- Append immutable operation records and get by ID. Duplicate IDs fail; no upsert.
- `safe_details` must be a JSON object, be detached through canonical JSON, and recursively reject keys containing token, secret, password, authorization, or credential. Errors never echo values.
- Do not store chat bodies, viewer notes, raw upstream payloads, credentials, or absolute private paths in fixtures/tests.

### ProcessedEventRepository

- `record_if_new(...)` atomically returns true only for the first message ID.
- Provide contains and expiry-prune operations. Duplicate EventSub delivery must not create a second row.

### ImportBatchRepository

- Append/get immutable batch metadata; duplicate IDs fail.
- Source manifest is a detached JSON object and recursively rejects credential-shaped keys. It contains only synthetic relative names, sizes, and checksums in tests—not source file contents or absolute private paths.

## Credentials separation skeleton

- Do not implement a credential file/env reader or secret-bearing repository in this slice.
- SQLite schema and concrete repositories must contain no credential columns and must not inspect environment variables.
- Settings persistence accepts only `AppSettings`, so caller-supplied token/secret keys cannot be written through it.
- Retain the Phase 1B `NullCredentialRegistry` as the only default credential boundary. Real actor-bound credential storage belongs to Phase 3.

## Acceptance criteria

- Importing all persistence modules and constructing database/repository objects causes no filesystem mutation, connection, thread, Flask import, environment discovery, or network access.
- The operational default path is exact, `data.db` is rejected, invalid/relative paths fail safely, and tests use only `tmp_path`.
- Fresh connections verify foreign keys, 5000 ms busy timeout, WAL, row factory, and same-thread enforcement.
- Migration 0001 creates exactly the six approved tables plus approved indexes; no domain-heavy or credential table is introduced.
- Migration idempotency, checksum/name drift, schema-too-new, invalid definitions, failure rollback, and quick-check behavior have deterministic tests.
- Repository optimistic concurrency, detached values, JSON corruption, duplicate handling, dedupe/prune, and secret-key rejection have focused tests.
- No real DNS/Twitch/media process, runtime data, credentials, legacy JSON/JSONL, `/app/data`, `/app/downloads`, or `data.db` is touched.
- Existing focused and full test suites pass.
- Stable writer self-review and one independent bounded review leave no unresolved High/Medium issue.

## Constraints

- Python 3.12 and `linux/arm64`; standard library only.
- Preserve single-container/gunicorn/port/mount/deployment architecture without changing it.
- Preserve all unrelated worktree changes.
- Use package-relative imports and `apply_patch`.
- Safe exception strings contain stable codes/context names, not supplied JSON values, paths, credentials, or private data.
- No production wiring or implicit initialization.

## Non-goals

- No legacy inspect/import/verify/export or source-file access.
- No schema for domain tables beyond the six core/system tables.
- No real credential storage, token refresh, Twitch adapter, EventSub, downloader, route, UI, runtime, or health readiness integration.
- No Docker/compose/requirements/workflow change, commit, push, image publication, deployment, or live database creation.

## Verification

- `python -B -m compileall -q src/twitchbot tests`
- Guarded stdlib import/construction smoke.
- Focused migration/connection/repository tests with per-test temporary `.sqlite3` files.
- Full `tests` suite in the existing isolated verification venv.
- `git diff --check` and changed-file/status inspection.
- Independent bounded review after stable self-review.

## Expected report

- Schema, migration, repository, and error contracts added.
- Focused/full test counts and commands.
- Confirmation that credentials and all legacy/runtime data were untouched.
- Remaining work for Slice 2B importer.

## Contract reset after correction verification

Status: active; implementation is not accepted yet.

The first review found substantive repository and migration gaps. A comprehensive correction was returned, but isolated pytest then failed before the new exit gate was met. Under the project delegation policy, further work uses this narrowed verification-hardening contract rather than another broad implementation pass.

Observed failures:

1. The credential-column scan in `tests/test_v2_persistence.py` references an undefined generator variable and never evaluates the schema assertion.
2. The non-contiguous-history fixture attempts to update migration version to `0`, which is rejected by the table's own positive-version constraint before `SQLiteDatabase.migrate()` can classify the history.

Required reset scope:

- Correct those two tests without weakening production constraints. Exercise non-contiguous lower history with a valid positive stored history and a custom two-migration code set, or another deterministic fixture that reaches `_read_existing()`.
- Complete the missing acceptance coverage from the original handoff and first review, using focused tests rather than broad combined tests:
  - exact approved tables and expiry index; no credential-shaped table or column names;
  - same-thread enforcement;
  - migration SQL failure and clock/timestamp failure rollback, including absence of partial DDL and migration rows;
  - quick-check non-`ok` and SQLite-error mapping;
  - invalid migration item/version/name/statement shape, future version, non-contiguous history, name drift, checksum drift;
  - settings empty/default, save/load, stale revision, partial/unknown/malformed/mixed revision/mixed timestamp corruption on both load and save, and proof failed save leaves rows unchanged;
  - channel create revision 1, update increment, omitted/invalid/stale expected revision, invalid tag container/element, stored JSON corruption;
  - operation append/get, duplicate, nested secret rejection, immutable/detached nested JSON, corrupt read, missing-table typed error;
  - processed-event first/duplicate/contains/prune and missing-table typed errors;
  - import-batch append/get, duplicate, nested secret rejection, immutable/detached manifest, corrupt read, missing-table typed error;
  - non-finite JSON number rejection and invalid/non-UTC timestamp mapping where accepted DTO inputs can reach an adapter.
- Fix implementation defects exposed by these tests only within the existing persistence/DTO boundary. Preserve stable safe `PersistenceError` codes and never include stored values, SQLite messages, or paths.
- The reset exit gate is: focused persistence tests pass; full suite passes; guarded import, compileall, and diff check pass; final independent review finds no unresolved High/Medium issue.

Do not start Slice 2B, edit production wiring, add dependencies, open operational/default databases, or access legacy/runtime/credential data during this reset.

### Reset verification run 2

The isolated reset run reached 28 focused tests but four fixtures still failed before exercising their intended application boundary:

- The custom two-migration fixture omitted creation of `schema_migrations`, so its initial migrate failed before a non-contiguous history could be formed.
- Three stored-JSON corruption fixtures were correctly blocked by migration 0001 `json_valid` constraints, so repository defense-in-depth reads were never exercised.

Keep the production constraints. Correct only the fixtures:

- Build the two-migration fixture with migration 1 containing the real migration-0001 statements (and migration 2 adding a synthetic table), apply both, then delete only the version-1 history row so valid positive version 2 remains and `_read_existing()` classifies it as non-contiguous.
- For deliberate corruption tests only, enable SQLite `PRAGMA ignore_check_constraints=ON` on that temporary test connection, write the malformed JSON, commit, restore the pragma to off, and then call the repository. Assert ordinary application writes still encounter the production constraints.

Re-run focused and full pytest. No source/schema weakening or new scope is authorized by this verification correction.

### Final review privacy correction

The final independent review confirmed the earlier migration/repository findings were resolved and found one remaining Medium privacy issue: generic JSON metadata rejects credential-shaped keys but still accepts absolute path strings, and import manifests are not yet constrained to the documented safe shape.

Required final correction:

- Recursively reject POSIX and Windows absolute path string values in operation `safe_details`, using a stable safe error that never includes the value.
- Validate import manifests as an exact object with a `files` array. Each file entry has only `name`, `size`, and `checksum`: `name` is a non-empty relative path without parent traversal, `size` is a strict non-negative integer, and `checksum` is a lowercase 64-character SHA-256 hex string. Reject unknown/missing fields, absolute/drive/UNC names, `..` traversal, wrong types, booleans as size, and malformed checksums. Empty `files` is allowed.
- Continue recursive credential-shaped-key rejection as defense in depth.
- Add positive and negative focused tests for POSIX/Windows paths, traversal, schema/type/field violations, valid nested relative names, and error redaction.

No new table, importer command, source-file read, or production integration is authorized.
