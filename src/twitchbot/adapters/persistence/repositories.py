"""Short-transaction SQLite repositories for the approved core tables."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import json
import re
import sqlite3
import math
from typing import Any

from ...application.persistence import (
    ChannelReadModel, ImportBatch, OperationRecord, PersistenceError,
    RevisionConflictError, SettingsSnapshot, FrozenObject, freeze_json_object, thaw_json,
    StreamRecord, StreamSample, ViewerRecord, VodAsset,
)
from ...settings import AppSettings, SettingsValidationError
from .sqlite import SQLiteDatabase, from_rfc3339, to_rfc3339, utc_now

_FORBIDDEN = ("token", "secret", "password", "authorization", "credential")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _canonical(value: Any, context: str) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise PersistenceError("invalid_json", context) from error


def _is_absolute_private_path(value: str) -> bool:
    return value.startswith("/") or value.startswith("\\\\") or bool(_WINDOWS_ABSOLUTE_RE.match(value))


def _safe_object(value: Mapping[str, Any], context: str, *, reject_absolute_paths: bool = False) -> tuple[FrozenObject, str]:
    try:
        frozen = freeze_json_object(value)
        detached = thaw_json(frozen)
    except PersistenceError as error:
        raise PersistenceError(error.code, context) from error

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if any(word in key.casefold() for word in _FORBIDDEN):
                    raise PersistenceError("forbidden_secret_key", context)
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
        elif reject_absolute_paths and isinstance(item, str) and _is_absolute_private_path(item):
            raise PersistenceError("forbidden_absolute_path", context)
    walk(detached)
    return frozen, _canonical(detached, context)


def _load_safe_object(value: str, context: str, *, reject_absolute_paths: bool = False) -> FrozenObject:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError) as error:
        raise PersistenceError("invalid_stored_json", context) from error
    if not isinstance(decoded, dict):
        raise PersistenceError("invalid_stored_json", context)
    return _safe_object(decoded, context, reject_absolute_paths=reject_absolute_paths)[0]


def _validate_import_manifest(value: Mapping[str, Any]) -> None:
    if set(value) != {"files"} or not isinstance(value.get("files"), list):
        raise PersistenceError("invalid_import_manifest", "import_batch")
    for entry in value["files"]:
        if not isinstance(entry, dict) or set(entry) != {"name", "size", "checksum"}:
            raise PersistenceError("invalid_import_manifest", "import_batch")
        name, size, checksum = entry["name"], entry["size"], entry["checksum"]
        if type(name) is not str or not name or _is_absolute_private_path(name):
            raise PersistenceError("invalid_import_manifest", "import_batch")
        parts = name.replace("\\", "/").split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise PersistenceError("invalid_import_manifest", "import_batch")
        if type(size) is not int or size < 0:
            raise PersistenceError("invalid_import_manifest", "import_batch")
        if type(checksum) is not str or _SHA256_RE.fullmatch(checksum) is None:
            raise PersistenceError("invalid_import_manifest", "import_batch")


class _Repository:
    def __init__(self, database: SQLiteDatabase, *, clock: Callable[[], datetime] = utc_now) -> None:
        self._database = database
        self._clock = clock

    @staticmethod
    def _expected(value: int) -> None:
        if type(value) is not int or value < 0:
            raise PersistenceError("invalid_expected_revision", "revision")

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass


class SettingsRepository(_Repository):
    @staticmethod
    def _parse(rows: list[sqlite3.Row]) -> SettingsSnapshot:
        if not rows:
            return SettingsSnapshot(AppSettings(), 0, None)
        revisions = {row["revision"] for row in rows}
        timestamps = {row["updated_at"] for row in rows}
        if len(revisions) != 1 or len(timestamps) != 1:
            raise PersistenceError("inconsistent_settings", "settings")
        revision = next(iter(revisions))
        if type(revision) is not int or revision < 0:
            raise PersistenceError("inconsistent_settings", "settings")
        values: dict[str, Any] = {}
        for row in rows:
            if type(row["key"]) is not str or row["key"] in values:
                raise PersistenceError("inconsistent_settings", "settings")
            try:
                values[row["key"]] = json.loads(row["value_json"])
            except (TypeError, ValueError) as error:
                raise PersistenceError("invalid_stored_json", "settings") from error
        if set(values) != set(AppSettings().to_mapping()):
            raise PersistenceError("inconsistent_settings", "settings")
        try:
            settings = AppSettings.from_mapping(values)
        except SettingsValidationError as error:
            raise PersistenceError("invalid_stored_settings", "settings") from error
        return SettingsSnapshot(settings, revision, from_rfc3339(next(iter(timestamps))))

    def load(self) -> SettingsSnapshot:
        try:
            with self._database.connection() as connection:
                return self._parse(connection.execute("SELECT key, value_json, revision, updated_at FROM settings ORDER BY key").fetchall())
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("settings_load_failed", "settings") from error

    def save(self, settings: AppSettings, expected_revision: int) -> SettingsSnapshot:
        self._expected(expected_revision)
        if not isinstance(settings, AppSettings):
            raise PersistenceError("invalid_settings", "settings")
        now = to_rfc3339(self._clock())
        values = settings.to_mapping()
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = self._parse(connection.execute("SELECT key, value_json, revision, updated_at FROM settings ORDER BY key").fetchall())
                if current.revision != expected_revision:
                    self._rollback(connection)
                    raise RevisionConflictError("settings")
                next_revision = current.revision + 1
                connection.execute("DELETE FROM settings")
                connection.executemany("INSERT INTO settings(key, value_json, revision, updated_at) VALUES (?, ?, ?, ?)",
                    [(key, _canonical(value, "settings"), next_revision, now) for key, value in values.items()])
                connection.commit()
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("settings_save_failed", "settings") from error
        return SettingsSnapshot(settings, next_revision, from_rfc3339(now))


class ChannelReadModelRepository(_Repository):
    def get(self, channel_id: str) -> ChannelReadModel | None:
        try:
            with self._database.connection() as connection:
                row = connection.execute("SELECT * FROM channel_read_model WHERE channel_id=?", (channel_id,)).fetchone()
            return None if row is None else self._row(row)
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("channel_load_failed", "channel") from error

    def put(self, model: ChannelReadModel, expected_revision: int) -> ChannelReadModel:
        self._expected(expected_revision)
        if not isinstance(model, ChannelReadModel) or type(model.tags) is not tuple or any(type(tag) is not str for tag in model.tags):
            raise PersistenceError("invalid_channel", "channel")
        payload = (model.title, model.game_id, model.game_name, _canonical(list(model.tags), "channel"), model.active_preset_id, to_rfc3339(model.observed_at), model.source)
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute("SELECT revision FROM channel_read_model WHERE channel_id=?", (model.channel_id,)).fetchone()
                if current is None:
                    if expected_revision != 0:
                        self._rollback(connection); raise RevisionConflictError("channel")
                    revision = 1
                    connection.execute("INSERT INTO channel_read_model(channel_id,title,game_id,game_name,tags_json,active_preset_id,observed_at,source,revision) VALUES (?,?,?,?,?,?,?,?,?)", (model.channel_id, *payload, revision))
                else:
                    if current["revision"] != expected_revision:
                        self._rollback(connection); raise RevisionConflictError("channel")
                    revision = expected_revision + 1
                    connection.execute("UPDATE channel_read_model SET title=?,game_id=?,game_name=?,tags_json=?,active_preset_id=?,observed_at=?,source=?,revision=? WHERE channel_id=?", (*payload, revision, model.channel_id))
                connection.commit()
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("channel_save_failed", "channel") from error
        return ChannelReadModel(model.channel_id, model.title, model.game_id, model.game_name, tuple(model.tags), model.active_preset_id, model.observed_at, model.source, revision)

    @staticmethod
    def _row(row: sqlite3.Row) -> ChannelReadModel:
        try:
            tags = json.loads(row["tags_json"])
            if not isinstance(tags, list) or any(type(tag) is not str for tag in tags):
                raise ValueError
            return ChannelReadModel(row["channel_id"], row["title"], row["game_id"], row["game_name"], tuple(tags), row["active_preset_id"], from_rfc3339(row["observed_at"]), row["source"], row["revision"])
        except (TypeError, ValueError, PersistenceError) as error:
            raise PersistenceError("invalid_stored_channel", "channel") from error


class OperationLogRepository(_Repository):
    def append(self, record: OperationRecord) -> OperationRecord:
        frozen, encoded = _safe_object(thaw_json(record.safe_details), "operation", reject_absolute_paths=True)
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("INSERT INTO operation_log VALUES (?,?,?,?,?,?,?,?,?,?)", (record.id, record.operation_type, record.target_type, record.target_id, record.state, record.message_code, record.request_id, to_rfc3339(record.started_at), None if record.finished_at is None else to_rfc3339(record.finished_at), encoded))
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise PersistenceError("duplicate_operation", "operation") from error
        except sqlite3.Error as error:
            raise PersistenceError("operation_append_failed", "operation") from error
        return OperationRecord(record.id, record.operation_type, record.target_type, record.target_id, record.state, record.message_code, record.request_id, record.started_at, record.finished_at, frozen)

    def get(self, record_id: str) -> OperationRecord | None:
        try:
            with self._database.connection() as connection:
                row = connection.execute("SELECT * FROM operation_log WHERE id=?", (record_id,)).fetchone()
            if row is None: return None
            return OperationRecord(row["id"], row["operation_type"], row["target_type"], row["target_id"], row["state"], row["message_code"], row["request_id"], from_rfc3339(row["started_at"]), None if row["finished_at"] is None else from_rfc3339(row["finished_at"]), _load_safe_object(row["safe_details_json"], "operation", reject_absolute_paths=True))
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("operation_load_failed", "operation") from error


class ProcessedEventRepository(_Repository):
    def record_if_new(self, message_id: str, message_type: str, received_at: datetime, expires_at: datetime) -> bool:
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute("INSERT OR IGNORE INTO processed_event_ids VALUES (?,?,?,?)", (message_id, message_type, to_rfc3339(received_at), to_rfc3339(expires_at)))
                connection.commit()
                return cursor.rowcount == 1
        except sqlite3.Error as error:
            raise PersistenceError("event_record_failed", "events") from error

    def contains(self, message_id: str) -> bool:
        try:
            with self._database.connection() as connection:
                return connection.execute("SELECT 1 FROM processed_event_ids WHERE message_id=?", (message_id,)).fetchone() is not None
        except sqlite3.Error as error:
            raise PersistenceError("event_contains_failed", "events") from error

    def prune_expired(self, now: datetime) -> int:
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute("DELETE FROM processed_event_ids WHERE expires_at <= ?", (to_rfc3339(now),))
                connection.commit()
                return cursor.rowcount
        except sqlite3.Error as error:
            raise PersistenceError("event_prune_failed", "events") from error


class ImportBatchRepository(_Repository):
    def append(self, batch: ImportBatch) -> ImportBatch:
        manifest = thaw_json(batch.source_manifest)
        frozen, encoded = _safe_object(manifest, "import_batch", reject_absolute_paths=True)
        _validate_import_manifest(manifest)
        try:
            with self._database.connection() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("INSERT INTO import_batches VALUES (?,?,?,?,?,?,?,?)", (batch.id, batch.importer_version, to_rfc3339(batch.imported_at), to_rfc3339(batch.cutoff_at), encoded, batch.source_base_reference, batch.result, batch.report_reference))
                connection.commit()
        except sqlite3.IntegrityError as error:
            raise PersistenceError("duplicate_import_batch", "import_batch") from error
        except sqlite3.Error as error:
            raise PersistenceError("import_batch_append_failed", "import_batch") from error
        return ImportBatch(batch.id, batch.importer_version, batch.imported_at, batch.cutoff_at, frozen, batch.source_base_reference, batch.result, batch.report_reference)

    def get(self, batch_id: str) -> ImportBatch | None:
        try:
            with self._database.connection() as connection:
                row = connection.execute("SELECT * FROM import_batches WHERE id=?", (batch_id,)).fetchone()
            if row is None: return None
            manifest = _load_safe_object(row["source_manifest_json"], "import_batch", reject_absolute_paths=True)
            _validate_import_manifest(thaw_json(manifest))
            return ImportBatch(row["id"], row["importer_version"], from_rfc3339(row["imported_at"]), from_rfc3339(row["cutoff_at"]), manifest, row["source_base_reference"], row["result"], row["report_reference"])
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("import_batch_load_failed", "import_batch") from error


_SOURCES = {"bot", "api", "imported"}
_COMPLETENESS = {"full", "samples_only", "metadata_only", "partial"}

def _text(value: Any, context: str, *, nonempty: bool = False) -> str | None:
    if value is None and not nonempty:
        return None
    if type(value) is not str or (nonempty and not value):
        raise PersistenceError("invalid_value", context)
    return value

def _identity(value: Any, context: str) -> str:
    if type(value) is not str or not value:
        raise PersistenceError("invalid_identity", context)
    return value

def _stored_text(value: Any, context: str, *, nonempty: bool = False) -> str | None:
    return _text(value, context, nonempty=nonempty)

def _stored_number(value: Any, context: str, *, integer: bool = True) -> int | float | None:
    if value is None: return None
    if isinstance(value, bool) or (integer and type(value) is not int) or (not integer and type(value) not in (int, float)):
        raise PersistenceError("invalid_stored_value", context)
    if value < 0 or (isinstance(value, float) and not math.isfinite(value)):
        raise PersistenceError("invalid_stored_value", context)
    return value

def _stored_revision(value: Any, context: str) -> int:
    if type(value) is not int or value < 0: raise PersistenceError("invalid_stored_value", context)
    return value

def _stored_timestamp(value: Any, context: str, *, required: bool = False) -> datetime | None:
    if value is None and not required: return None
    if type(value) is not str: raise PersistenceError("invalid_stored_value", context)
    return from_rfc3339(value)

def _stored_path(value: Any, context: str) -> str | None:
    try: return _path(value)
    except PersistenceError as error: raise PersistenceError("invalid_stored_value", context) from error

def _number(value: Any, context: str, *, integer: bool = True, finite: bool = False) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or (integer and type(value) is not int) or (not integer and not isinstance(value, (int, float))):
        raise PersistenceError("invalid_number", context)
    if value < 0 or (finite and isinstance(value, float) and not __import__("math").isfinite(value)):
        raise PersistenceError("invalid_number", context)
    return value

def _dt(value: datetime | None, context: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    return to_rfc3339(value)  # type: ignore[arg-type]

def _path(value: str | None) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value or value in {".", ".."} or "\\" in value or value.startswith("/") or value.startswith("\\\\") or bool(re.match(r"^[A-Za-z]:", value)):
        raise PersistenceError("unsafe_relative_path", "vod")
    parts = value.split("/")
    if any(not p or p in {".", ".."} for p in parts):
        raise PersistenceError("unsafe_relative_path", "vod")
    return value

def _domain_object(value: FrozenObject | Mapping[str, Any], context: str) -> tuple[FrozenObject, str]:
    source = thaw_json(value) if isinstance(value, FrozenObject) else value
    return _safe_object(source, context, reject_absolute_paths=True)


class StreamRepository(_Repository):
    def put(self, record: StreamRecord, expected_revision: int) -> StreamRecord:
        self._expected(expected_revision)
        if not isinstance(record, StreamRecord) or type(record.id) is not str or not record.id or type(record.channel_id) is not str or not record.channel_id or not isinstance(record.tags, tuple) or any(type(x) is not str for x in record.tags) or type(record.source) is not str or not record.source or record.source not in _SOURCES or type(record.completeness) is not str or not record.completeness or record.completeness not in _COMPLETENESS:
            raise PersistenceError("invalid_stream", "stream")
        metadata, encoded = _domain_object(record.legacy_metadata, "stream")
        values = (record.id, record.channel_id, _text(record.title, "stream", nonempty=True), _text(record.game_id, "stream"), _text(record.game_name, "stream"), _text(record.thumbnail_url, "stream"), _canonical(list(record.tags), "stream"), _dt(record.started_at, "stream", required=True), _dt(record.ended_at, "stream"), _number(record.duration_seconds, "stream"), record.source, record.completeness, _number(record.max_viewers, "stream"), _number(record.average_viewers, "stream", integer=False, finite=True), _number(record.follower_count, "stream"), _number(record.total_comments, "stream"), encoded, _text(record.import_batch_id, "stream"),)
        now = to_rfc3339(self._clock())
        try:
            with self._database.connection() as c:
                c.execute("BEGIN IMMEDIATE")
                current = c.execute("SELECT revision,created_at FROM streams WHERE id=?", (record.id,)).fetchone()
                if current is None:
                    if expected_revision != 0: self._rollback(c); raise RevisionConflictError("stream")
                    revision, created = 1, now
                    c.execute("INSERT INTO streams VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*values, created, now, revision))
                else:
                    if current["revision"] != expected_revision: self._rollback(c); raise RevisionConflictError("stream")
                    revision, created = expected_revision + 1, current["created_at"]
                    c.execute("UPDATE streams SET channel_id=?,title=?,game_id=?,game_name=?,thumbnail_url=?,tags_json=?,started_at=?,ended_at=?,duration_seconds=?,source=?,completeness=?,max_viewers=?,average_viewers=?,follower_count=?,total_comments=?,legacy_metadata_json=?,import_batch_id=?,updated_at=?,revision=? WHERE id=?", (*values[1:], now, revision, record.id))
                c.commit()
        except PersistenceError:
            raise
        except sqlite3.IntegrityError as error:
            raise PersistenceError("stream_save_failed", "stream") from error
        except sqlite3.Error as error:
            raise PersistenceError("stream_save_failed", "stream") from error
        return StreamRecord(record.id, record.channel_id, record.title, record.game_id, record.game_name, record.thumbnail_url, tuple(record.tags), record.started_at, record.ended_at, record.duration_seconds, record.source, record.completeness, record.max_viewers, record.average_viewers, record.follower_count, record.total_comments, metadata, record.import_batch_id, from_rfc3339(created), from_rfc3339(now), revision)

    create = put
    update = put

    def get(self, stream_id: str) -> StreamRecord | None:
        stream_id = _identity(stream_id, "stream")
        try:
            with self._database.connection() as c: row = c.execute("SELECT * FROM streams WHERE id=?", (stream_id,)).fetchone()
            if row is None: return None
            tags = json.loads(row["tags_json"]); metadata = _load_safe_object(row["legacy_metadata_json"], "stream", reject_absolute_paths=True)
            if not isinstance(tags, list) or any(type(x) is not str for x in tags): raise PersistenceError("invalid_stored_value", "stream")
            if type(row["id"]) is not str or not row["id"] or type(row["channel_id"]) is not str or not row["channel_id"] or type(row["title"]) is not str:
                raise PersistenceError("invalid_stored_value", "stream")
            if type(row["source"]) is not str or row["source"] not in _SOURCES or type(row["completeness"]) is not str or row["completeness"] not in _COMPLETENESS: raise PersistenceError("invalid_stored_value", "stream")
            return StreamRecord(row["id"], row["channel_id"], row["title"], _stored_text(row["game_id"],"stream"), _stored_text(row["game_name"],"stream"), _stored_text(row["thumbnail_url"],"stream"), tuple(tags), _stored_timestamp(row["started_at"],"stream",required=True), _stored_timestamp(row["ended_at"],"stream"), _stored_number(row["duration_seconds"],"stream"), row["source"], row["completeness"], _stored_number(row["max_viewers"],"stream"), _stored_number(row["average_viewers"],"stream",integer=False), _stored_number(row["follower_count"],"stream"), _stored_number(row["total_comments"],"stream"), metadata, _stored_text(row["import_batch_id"],"stream"), _stored_timestamp(row["created_at"],"stream",required=True), _stored_timestamp(row["updated_at"],"stream",required=True), _stored_revision(row["revision"],"stream"))
        except PersistenceError: raise
        except (sqlite3.Error, TypeError, ValueError) as error: raise PersistenceError("stream_load_failed", "stream") from error


class StreamSampleRepository(_Repository):
    def append(self, sample: StreamSample) -> StreamSample:
        if not isinstance(sample, StreamSample) or type(sample.stream_id) is not str or not sample.stream_id: raise PersistenceError("invalid_sample", "sample")
        vals = (sample.stream_id, _dt(sample.sampled_at, "sample", required=True), _number(sample.viewer_count,"sample"), _number(sample.chat_count,"sample"), _number(sample.messages_per_minute,"sample",integer=False,finite=True), _number(sample.bits,"sample"), _number(sample.gift_subscriptions,"sample"), _number(sample.follower_total,"sample"))
        try:
            with self._database.connection() as c: c.execute("INSERT INTO stream_samples VALUES (?,?,?,?,?,?,?,?)", vals); c.commit()
        except sqlite3.IntegrityError as error: raise PersistenceError("duplicate_or_foreign_sample", "sample") from error
        except sqlite3.Error as error: raise PersistenceError("sample_append_failed", "sample") from error
        return sample
    def list(self, stream_id: str) -> list[StreamSample]:
        stream_id = _identity(stream_id, "sample")
        try:
            with self._database.connection() as c: rows = c.execute("SELECT * FROM stream_samples WHERE stream_id=? ORDER BY sampled_at", (stream_id,)).fetchall()
            result=[]
            for row in rows:
                if type(row["stream_id"]) is not str or not row["stream_id"]: raise PersistenceError("invalid_stored_value", "sample")
                result.append(StreamSample(row["stream_id"], _stored_timestamp(row["sampled_at"],"sample",required=True), _stored_number(row["viewer_count"],"sample"), _stored_number(row["chat_count"],"sample"), _stored_number(row["messages_per_minute"],"sample",integer=False), _stored_number(row["bits"],"sample"), _stored_number(row["gift_subscriptions"],"sample"), _stored_number(row["follower_total"],"sample")))
            return result
        except (PersistenceError, sqlite3.Error) as error:
            if isinstance(error, PersistenceError): raise
            raise PersistenceError("sample_load_failed", "sample") from error


class ViewerRepository(_Repository):
    def put(self, record: ViewerRecord, expected_revision: int) -> ViewerRecord:
        self._expected(expected_revision)
        if not isinstance(record, ViewerRecord) or type(record.user_id) is not str or not record.user_id: raise PersistenceError("invalid_viewer", "viewer")
        metadata, encoded = _domain_object(record.legacy_metadata, "viewer")
        ints = [_number(getattr(record, n), "viewer") for n in ("visit_count","watch_seconds","comment_count","bits_total","sub_months","gifts_given","gifts_received","streak")]
        if record.is_subscriber is not None and type(record.is_subscriber) is not bool: raise PersistenceError("invalid_viewer", "viewer")
        vals = (record.user_id, _text(record.login,"viewer"), _text(record.display_name,"viewer"), _dt(record.followed_at,"viewer"), _dt(record.unfollowed_at,"viewer"), ints[0], ints[1], ints[2], ints[3], None if record.is_subscriber is None else int(record.is_subscriber), ints[4], ints[5], ints[6], ints[7], _dt(record.last_sub_at,"viewer"), _text(record.last_sub_plan,"viewer"), _dt(record.last_seen_at,"viewer"), _text(record.last_stream_id,"viewer"), _text(record.note,"viewer"), encoded)
        now = to_rfc3339(self._clock())
        try:
            with self._database.connection() as c:
                c.execute("BEGIN IMMEDIATE"); current = c.execute("SELECT revision,created_at FROM viewers WHERE user_id=?",(record.user_id,)).fetchone()
                if current is None:
                    if expected_revision != 0: self._rollback(c); raise RevisionConflictError("viewer")
                    revision, created = 1, now; c.execute("INSERT INTO viewers(user_id,login,display_name,followed_at,unfollowed_at,visit_count,watch_seconds,comment_count,bits_total,is_subscriber,sub_months,gifts_given,gifts_received,streak,last_sub_at,last_sub_plan,last_seen_at,last_stream_id,note,legacy_metadata_json,created_at,updated_at,revision) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*vals, created, now, revision))
                else:
                    if current["revision"] != expected_revision: self._rollback(c); raise RevisionConflictError("viewer")
                    revision, created = expected_revision+1, current["created_at"]
                    c.execute("UPDATE viewers SET login=?,display_name=?,followed_at=?,unfollowed_at=?,visit_count=?,watch_seconds=?,comment_count=?,bits_total=?,is_subscriber=?,sub_months=?,gifts_given=?,gifts_received=?,streak=?,last_sub_at=?,last_sub_plan=?,last_seen_at=?,last_stream_id=?,note=?,legacy_metadata_json=?,updated_at=?,revision=? WHERE user_id=?", (*vals[1:], now, revision, record.user_id))
                c.commit()
        except PersistenceError: raise
        except sqlite3.IntegrityError as error: raise PersistenceError("viewer_save_failed", "viewer") from error
        except sqlite3.Error as error: raise PersistenceError("viewer_save_failed", "viewer") from error
        return ViewerRecord(record.user_id, record.login, record.display_name, record.followed_at, record.unfollowed_at, record.visit_count, record.watch_seconds, record.comment_count, record.bits_total, record.is_subscriber, record.sub_months, record.last_sub_at, record.last_sub_plan, record.gifts_given, record.gifts_received, record.streak, record.last_seen_at, record.last_stream_id, record.note, metadata, from_rfc3339(created), from_rfc3339(now), revision)
    create = put; update = put
    def get(self, user_id: str) -> ViewerRecord | None:
        user_id = _identity(user_id, "viewer")
        try:
            with self._database.connection() as c: row = c.execute("SELECT * FROM viewers WHERE user_id=?",(user_id,)).fetchone()
            if row is None: return None
            if type(row["user_id"]) is not str or not row["user_id"]: raise PersistenceError("invalid_stored_value", "viewer")
            if row["is_subscriber"] is not None and type(row["is_subscriber"]) is not int or row["is_subscriber"] not in (None,0,1): raise PersistenceError("invalid_stored_value", "viewer")
            return ViewerRecord(row["user_id"],_stored_text(row["login"],"viewer"),_stored_text(row["display_name"],"viewer"),_stored_timestamp(row["followed_at"],"viewer"),_stored_timestamp(row["unfollowed_at"],"viewer"),_stored_number(row["visit_count"],"viewer"),_stored_number(row["watch_seconds"],"viewer"),_stored_number(row["comment_count"],"viewer"),_stored_number(row["bits_total"],"viewer"),None if row["is_subscriber"] is None else bool(row["is_subscriber"]),_stored_number(row["sub_months"],"viewer"),_stored_timestamp(row["last_sub_at"],"viewer"),_stored_text(row["last_sub_plan"],"viewer"),_stored_number(row["gifts_given"],"viewer"),_stored_number(row["gifts_received"],"viewer"),_stored_number(row["streak"],"viewer"),_stored_timestamp(row["last_seen_at"],"viewer"),_stored_text(row["last_stream_id"],"viewer"),_stored_text(row["note"],"viewer"),_load_safe_object(row["legacy_metadata_json"],"viewer",reject_absolute_paths=True),_stored_timestamp(row["created_at"],"viewer",required=True),_stored_timestamp(row["updated_at"],"viewer",required=True),_stored_revision(row["revision"],"viewer"))
        except PersistenceError: raise
        except (sqlite3.Error,TypeError,ValueError) as error: raise PersistenceError("viewer_load_failed","viewer") from error


class VodAssetRepository(_Repository):
    def put(self, asset: VodAsset, expected_revision: int) -> VodAsset:
        self._expected(expected_revision)
        if not isinstance(asset,VodAsset) or type(asset.id) is not str or not asset.id or type(asset.stream_id) is not str or not asset.stream_id or type(asset.remote_state) is not str or not asset.remote_state or type(asset.local_state) is not str or not asset.local_state: raise PersistenceError("invalid_vod","vod")
        path = _path(asset.relative_path); size = _number(asset.size_bytes,"vod")
        vals=(asset.id,asset.stream_id,_text(asset.twitch_vod_id,"vod"),path,size,_dt(asset.discovered_at,"vod"),_dt(asset.verified_at,"vod"),asset.remote_state,asset.local_state)
        try:
            with self._database.connection() as c:
                c.execute("BEGIN IMMEDIATE"); current=c.execute("SELECT revision FROM vod_assets WHERE id=?",(asset.id,)).fetchone()
                if current is None:
                    if expected_revision != 0: self._rollback(c); raise RevisionConflictError("vod")
                    revision=1; c.execute("INSERT INTO vod_assets VALUES (?,?,?,?,?,?,?,?,?,?)",(*vals,revision))
                else:
                    if current["revision"] != expected_revision: self._rollback(c); raise RevisionConflictError("vod")
                    revision=expected_revision+1; c.execute("UPDATE vod_assets SET stream_id=?,twitch_vod_id=?,relative_path=?,size_bytes=?,discovered_at=?,verified_at=?,remote_state=?,local_state=?,revision=? WHERE id=?",(*vals[1:],revision,asset.id))
                c.commit()
        except PersistenceError: raise
        except sqlite3.IntegrityError as error: raise PersistenceError("vod_save_failed","vod") from error
        except sqlite3.Error as error: raise PersistenceError("vod_save_failed","vod") from error
        return VodAsset(asset.id,asset.stream_id,asset.twitch_vod_id,path,size,asset.discovered_at,asset.verified_at,asset.remote_state,asset.local_state,revision)
    create=put; update=put
    def get(self, asset_id: str) -> VodAsset | None:
        asset_id = _identity(asset_id, "vod")
        return self._get("id",asset_id)
    def get_by_stream(self, stream_id: str) -> VodAsset | None:
        stream_id = _identity(stream_id, "vod")
        return self._get("stream_id",stream_id)
    def _get(self, key: str, value: str) -> VodAsset | None:
        try:
            with self._database.connection() as c: row=c.execute(f"SELECT * FROM vod_assets WHERE {key}=?",(value,)).fetchone()
            if row is None:return None
            if type(row["id"]) is not str or not row["id"] or type(row["stream_id"]) is not str or not row["stream_id"] or type(row["remote_state"]) is not str or not row["remote_state"] or type(row["local_state"]) is not str or not row["local_state"]: raise PersistenceError("invalid_stored_value", "vod")
            return VodAsset(row["id"],row["stream_id"],_stored_text(row["twitch_vod_id"],"vod"),_stored_path(row["relative_path"],"vod"),_stored_number(row["size_bytes"],"vod"),_stored_timestamp(row["discovered_at"],"vod"),_stored_timestamp(row["verified_at"],"vod"),row["remote_state"],row["local_state"],_stored_revision(row["revision"],"vod"))
        except PersistenceError: raise
        except (sqlite3.Error,TypeError,ValueError) as error: raise PersistenceError("vod_load_failed","vod") from error
