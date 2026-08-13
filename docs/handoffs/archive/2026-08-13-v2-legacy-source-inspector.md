# v2 Phase 2B1: read-only legacy source inspector

Status: completed on 2026-08-13.

Completion verification: isolated focused inspector/import-safety tests `24 passed, 2 skipped`; full suite `104 passed, 2 skipped`; `compileall` and `git diff --check` passed. The skips are capability-based synthetic symlink cases, with deterministic link-detection coverage retained. Final independent review found no actionable High/Medium issue.

## Goal

Implement a fixture-first, side-effect-free legacy source inspector and migration planner. It must create a deterministic verified manifest, safely characterize known/unknown/malformed data and VOD paths, redact credentials, and detect source mutation. It must not claim or perform persistent domain import while the destination domain tables do not exist.

## Background

Phase 2A added only the six approved core/system SQLite tables. The legacy source contains many domain entities that cannot yet be stored honestly. The staging decision is recorded in `docs/decisions/2026-08-13-legacy-importer-staging-order.md`.

This slice implements the application boundary behind a future `migrate inspect` command. It returns immutable report objects in memory; no CLI and no report-file writer are added yet.

## Data sources

- `AGENTS.md`, `CLAUDE.md`
- `docs/decisions/2026-08-13-legacy-importer-staging-order.md`
- `docs/rebuild/04-data-and-api.md` sections 6–7
- `docs/rebuild/05-migration-and-delivery.md` Slice 2B and rollback sections
- `docs/rebuild/06-quality-security-operations.md` persistence/test-isolation sections
- Legacy format-defining code in `config.py`, `services/storage.py`, `services/workers.py`, and `services/irc.py`
- Current v2 settings and persistence contracts

## Files to edit

- New package under `src/twitchbot/migration/`
- New SQLite-independent immutable migration/report DTOs under `src/twitchbot/application/` only where needed
- New focused fixture tests under `tests/`
- Existing v2 import-safety test only if needed to guard the new module imports/construction

Do not edit legacy production code/tests, Phase 1/2A behavior, migrations/schema/repositories, dependencies, Docker/deployment, runtime data, or credentials.

## Public application boundary

Provide a small API with these roles; exact class/function names may follow local style:

- `LegacySourceInspector(source_root, downloads_root, source_reference, clock, monotonic)`
  - construction validates only argument shapes and is filesystem-inert;
  - `inspect()` performs the explicit read-only inspection and returns an immutable `InspectionReport`;
  - `verify_unchanged(report)` re-inventories the same allowlisted source and fails if name/size/checksum/mtime changed.
- `build_migration_plan(report)` returns an immutable plan with `import_ready=False` and blocker `domain_schema_unavailable`. It may add `invalid_source` or `credential_validation_required` blockers from the report, but must never mark domain import successful.
- Report/plan DTOs expose `to_safe_mapping()` for later JSON serialization. Returned mappings are detached and contain only fields approved below.

Module import, object construction, and plan construction must not touch the filesystem, environment, network, threads, Flask, SQLite, subprocesses, or legacy modules.

## Source path and inventory policy

- `source_root` and `downloads_root` must be absolute paths. They are accessed only by `inspect()`/`verify_unchanged()`.
- `source_reference` is a caller-provided opaque safe identifier matching `[A-Za-z0-9._-]{1,128}`; never derive it from or expose the absolute source path.
- On inspection, source root must exist as a real directory. Reject symlink/junction roots and symlink/junction `history` directories/files. Never follow source symlinks.
- Allowlist only:
  - `config.json`
  - `viewers.json`
  - `history/stream_index.json`
  - `history/stream_<id>.jsonl`, where `<id>` matches `[A-Za-z0-9_-]{1,128}`
- Inventory is sorted by POSIX-style relative name. Each manifest entry is exactly `name`, non-negative byte `size`, and lowercase SHA-256 `checksum`, compatible with the Phase 2A import-manifest validator.
- Record `mtime_ns` separately for mutation detection and the safe inspection report. Do not place it in the stored import manifest.
- Unsupported regular files/directories are reported by safe relative name and are not opened or hashed. Unsafe/traversing names and special filesystem entries fail closed.
- Hash in bounded binary chunks. JSONL parsing is streaming; never load a complete JSONL file into memory.
- Capture the manifest/stat state before parsing and again after parsing. Any name, size, checksum, or mtime difference raises safe `source_changed` and returns no successful report.
- Missing allowlisted documents and missing `history` are reported deterministically; they do not cause creation of files/directories.

## Safe report surface

The immutable `InspectionReport` and `to_safe_mapping()` may contain only:

- importer/report schema version;
- caller-supplied `source_reference`;
- UTC RFC 3339 cutoff;
- elapsed milliseconds;
- sorted manifest entries (`name`, `size`, `checksum`) and separate (`name`, `mtime_ns`) observations;
- document statuses and aggregate record/valid/rejected counts;
- issue records containing only relative file name, optional line number, entity category, stable code, and optional safe field/key path;
- unknown-field summaries containing only entity category, safe field path, and occurrence count;
- credential summaries containing only role/key name and `configured` or `not_configured`; subject validation is explicitly deferred;
- VOD path summary counts by stable result code;
- `credentials_redacted=true`, `source_unchanged=true`, and plan blockers.

Never include source absolute paths, downloads absolute paths, JSON values, tokens, IDs used as JSON object keys, viewer/login/display names, memos, chat text, event payloads, VOD path strings, raw file contents, exception messages from parsers/filesystem, or environment values in DTO repr, mappings, errors, logs, or tests.

All errors are safe typed errors with stable code/context and no supplied path/value.

## JSON parsing policy

- UTF-8 only; reject a BOM and invalid UTF-8 safely.
- Reject non-standard constants (`NaN`, `Infinity`), duplicate JSON object keys, empty files, non-object document roots, and oversized JSON documents with stable issue codes.
- Maximum parsed size for `config.json`, `viewers.json`, and `stream_index.json`: 64 MiB each. Larger files remain in the manifest but are not parsed and receive `document_too_large`.
- Maximum JSONL line length: 2 MiB. Oversized lines are reported/rejected and parsing continues at the next line.
- JSONL blank/malformed/non-object/invalid-shape lines are reported with relative file and one-based line number; other valid lines continue.
- Parser/OS exception strings never enter reports.

## Config inspection

- Recognize the documented/default/code-read keys:
  - identity/non-secret: `client_id`, `broadcaster_id`, `bot_user_id`, `channel_name`;
  - typed operational: `is_running`, `enable_welcome`, `ignore_stream_status`, `enable_vod_download`, `hide_self_bot`, `ignored_users`;
  - deferred domain/UI: `rules`, `presets`, `prediction_presets`, `layout`, `debug_mode`, `current_title`, `current_tweet_tags`;
  - credential: `access_token`, `broadcaster_token`.
- Any other credential-shaped key containing token/secret/password/authorization/credential is classified as a credential key, never as an unknown value.
- Map the six legacy operational values into `AppSettings`; poll/flush intervals retain code defaults. Missing `enable_vod_download` maps explicitly to `False`. Apply strict v2 validation with no coercion. A validation failure reports only the safe v2 field and code.
- Unknown non-credential keys are counted/reported by key name only. Their values remain solely in the immutable source artifact for later quarantine; they are not returned.
- Credential state is based only on presence of a non-empty string: Bot `access_token`, broadcaster `broadcaster_token`. Report only key/role and `configured`/`not_configured`. Do not validate, normalize, hash, compare, or store token values. A configured credential produces plan blocker `credential_validation_required`; malformed shape produces a safe issue.

## Viewer and stream-index inspection

- Root must be an object. Entity IDs remain private and are never copied into report issues.
- Viewer values must be objects. Recognize the documented optional viewer fields; aggregate unknown field names and invalid-record counts without returning viewer IDs or values.
- Stream-index values must be objects. Recognize the documented fields plus known transient view fields `sid`, `encode_status`, `archive_file_size`, and `duration_short`; classify transient fields separately and never treat them as target domain data.
- Unknown entity fields are summarized by entity type and field name, not dropped or returned with values.
- No viewer/stream/VOD entity is persisted in this slice.

## JSONL inspection

- Recognize the documented top-level keys: `timestamp`, `stream_info`, `metrics`, `emotes`, `subs`, `raids`, `points`, `badges`, `messages`, `events`, `census`.
- Validate the root object and the container shapes listed in the rebuild inventory. Validate list items are objects and documented required identifying/count/text fields have the expected JSON scalar/container kind without reporting their values.
- Unknown fields at top level and documented nested objects/list entries are summarized as safe schema paths with occurrence counts.
- Missing/invalid required structural fields make the line rejected; optional missing metrics remain unknown/not-collected and are not normalized to zero.
- Malformed/rejected lines remain only in the untouched source artifact and report; valid later lines continue.

## VOD path inspection

- Never open/read media bytes or invoke yt-dlp/ffmpeg.
- Treat `downloads_root` as the only allowed base. Validate lexically and by resolved containment without returning paths.
- Classify absent/empty, safe relative, absolute inside mount and normalizable to relative, traversal, absolute outside, Windows drive/UNC outside, and symlink escape using stable result codes and aggregate counts.
- A relative path must not contain empty, `.` or `..` components. An existing symlink component is rejected. Nonexistent final media is allowed as a separate `missing_target` result; no directory/file is created.

## Migration plan contract

- Always include `domain_schema_unavailable`, so `import_ready` is false in 2B1.
- Add `invalid_source` when structural/encoding/path safety issues prevent a faithful later import.
- Add `credential_validation_required` when a candidate token is configured; no network validation occurs.
- Malformed JSONL lines and unknown fields are explicit report counts, never silent. Whether they block later import is deferred to 2B2 policy, but the plan must not hide them.
- Plan/report equality is deterministic for identical fixture bytes, metadata, cutoff, and injected clocks.

## Acceptance criteria

- Construction/import are inert and standard-library only.
- Synthetic fixtures cover missing/empty/malformed documents, known+unknown config, credential redaction, viewer/index invalid and unknown records, JSONL valid/bad/blank/oversized/continued lines, unsupported files, source symlinks, source mutation, and deterministic order/checksums.
- VOD fixture matrix covers safe relative, inside absolute, outside, traversal, Windows/UNC, nonexistent, and symlink escape without media reads.
- Source names/checksums/mtime remain identical before/after successful inspect; `verify_unchanged` detects byte or mtime mutation.
- Guarded tests fail on network, thread start, subprocess, SQLite connect, environment discovery, filesystem writes, or legacy-module import while inspection still succeeds.
- Safe mapping/repr/error tests use sentinel token, memo, chat text, viewer ID/name, and private absolute paths and assert none appear.
- `build_migration_plan` cannot report import-ready or success in this slice.
- Existing focused and full tests pass; independent review leaves no unresolved High/Medium issue.

## Constraints

- Python 3.12 / `linux/arm64`; standard library only.
- Tests use only `tmp_path` synthetic data and fake clocks. Do not inspect repository `data/`, `downloads/`, `data.db`, `/app/data`, `/app/downloads`, `.env`, or configured credentials.
- Use `apply_patch` and package-relative imports.
- Preserve all unrelated worktree changes and production wiring.

## Non-goals

- No database writes, `import_batches` record, settings/channel persistence, domain schema, normalized entity import, verify-against-DB, rollback exporter, CLI, or report file writer.
- No OAuth/token subject validation, credential store, Twitch/network call, media read/process, runtime worker, route, or UI.
- No commit, push, image publication, deployment, or production migration.

## Verification

- `python -B -m compileall -q src/twitchbot tests`
- Guarded import/construction/inspection smoke.
- Focused source-inspector tests using only synthetic temporary trees.
- Full test suite in the isolated verification venv.
- `git diff --check`, changed-file/status inspection, and one independent bounded review.

## Expected report

- Inspector/report/plan contracts added.
- Focused/full test counts.
- Proof of source immutability, credential/privacy redaction, offline behavior, and permanent `import_ready=false` for 2B1.
- Remaining destination-schema/import work for 2B2.

## Contract reset after comprehensive correction

Status: active; 2B1 is not accepted yet.

The first implementation failed focused tests. The comprehensive correction then reached 16 focused cases but still failed 6 and left material handoff coverage unimplemented. Further work is narrowed to contract completion and deterministic verification; no new product scope is authorized.

Observed defects:

1. `history/stream_index.json` is routed into the JSONL parser because routing checks `startswith("history/stream_")`; VOD inspection never runs. Route JSONL only through the exact allowlist regex/file suffix.
2. The safe `documents` surface is now a list of structured summaries, but an old test still treats it as a dictionary.
3. The viewer known-field set does not match the documented legacy inventory and would falsely classify valid fields as unknown.
4. Unsupported state records names only, so byte/mtime changes to an already-present unsupported entry are not detected.
5. Symlink checks do not cover Windows junctions, and VOD absolute-inside handling rejects every native Windows drive path before containment analysis.
6. JSONL validation still checks mainly top-level containers. It does not validate documented nested field types/list-entry requirements or aggregate nested unknown fields.
7. Entity document summaries report one document rather than entity record read/valid/rejected counts.
8. The explicit privacy, bounded-size, guarded-offline, during-inspection mutation, deterministic equality, and full VOD matrix tests remain incomplete.

Reset implementation requirements:

- Fix exact file routing first and add a regression test proving `stream_index.json` is parsed as an index while `stream_<id>.jsonl` is parsed as JSONL.
- Use the exact documented viewer fields: `name`, `login`, `total_visits`, `streak`, `total_duration`, `last_stream_id`, `last_seen_ts`, `total_comments`, `total_bits`, `is_sub`, `total_sub_months`, `last_sub_ts`, `last_sub_plan`, `total_gifts_given`, `total_gifts_received`, `followed_at`, `unfollowed_at`, `memo`. Validate basic kinds without exposing IDs/values.
- Keep exact index and transient sets. Return entity-level `records_read`, `valid`, and `rejected`; invalid record/field issues contain no entity ID/value.
- Track unsupported entries internally with safe relative name, entry kind, size, and `mtime_ns` (no checksum/content read). Compare the full internal state before/after and in `verify_unchanged`; expose only the approved safe unsupported summary.
- Detect symlink and `Path.is_junction()` where available for source/download roots, history, inventory entries, and VOD components.
- In VOD analysis, evaluate native absolute containment before classifying foreign Windows drive/UNC syntax. Reject any existing symlink/junction component. Cover absent, empty, invalid type, safe existing relative, missing target, native absolute inside existing/missing, POSIX/native outside, foreign Windows drive/UNC, traversal/dot/empty component, non-file target, and link escape. Never open media.
- JSONL requires a bounded reader and structural validation for documented `stream_info`, `metrics`, `subs`, `raids`, `points`, `messages`, `events`, and `census` shapes. Validate known fields when present; require the documented fields for list items; reject bool where a number is expected; aggregate safe nested unknown schema paths. `emotes`/`badges` must be objects and `subs` must be an object. Empty JSONL is an empty-document issue/status. Valid lines after every rejected line continue.
- Complete tests for JSON document empty/too-large/BOM/invalid UTF-8/duplicate/non-finite/non-object; JSONL blank/malformed/non-object/oversized/nested-invalid/continued lines using patched small limits.
- Complete privacy tests with sentinel identity values, token, memo, chat text, viewer/stream IDs, malicious field name, and private VOD paths across report repr, mapping, plan, and error strings.
- Complete deterministic and mutation tests: equal report/plan with fixed clocks and unchanged metadata; allowlisted byte change; mtime-only change; unsupported add/remove/content/mtime change; mutation during parsing; `verify_unchanged` for each.
- Add an explicit guarded inspection test after fixture creation. Deny socket/network, thread start, subprocess, `sqlite3.connect`, environment lookup, and write-capable filesystem APIs while inspection succeeds. Assert no legacy `config`, `routes`, or `services` module is imported.
- Constructor invalid types, non-UTC/invalid clocks, bad monotonic results, and filesystem failures must yield safe typed errors without supplied values/paths.

Reset exit gate:

- Focused inspector/import-safety tests pass with no unexpected skip; a symlink/junction case may be capability-skipped only on platforms that cannot create it, while link-detection logic also has a deterministic mocked/unit path.
- Full suite, guarded import/inspection smoke, `compileall`, and `git diff --check` pass.
- Final independent review finds no unresolved High/Medium issue.

Do not add CLI/database writes/domain schemas, weaken source or privacy rules, or access real data during this reset.

## Second contract reset: nested JSONL and broken-link containment

Status: active; this is a narrow follow-up to the independent final review. No
new product scope is authorized.

The review found two unresolved Medium risks that must be closed before 2B1 is
accepted:

1. JSONL validation checks required list-item fields, but it must also validate
   every documented optional field when present. In particular, `events` must
   type-check its supported optional fields, `messages[].badges` must have a
   bounded documented shape, and `stream_info.tags` must contain strings.
2. VOD component inspection must reject an existing broken symlink or junction.
   It must inspect link-like state with `lstat` / `is_junction()` before an
   `exists()` decision, so a broken link cannot be reported as a harmless
   missing target.

Required completion:

- Keep report values redacted and aggregate-only; do not add source IDs, media
  paths, chat content, or raw document values to any public DTO/error.
- Add focused synthetic-fixture tests for each invalid JSONL case and a broken
  symlink component (capability-skip only where creating that link is
  unavailable), plus a deterministic unit path for link detection.
- Preserve the no-write/no-network/no-thread/no-database and source-unchanged
  guarantees. No legacy imports, production wiring, schema changes, or data
  access.
- Re-run focused tests, the full suite, compileall, and diff check. A fresh
  independent final review follows this correction.
