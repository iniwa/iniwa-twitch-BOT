"""Forward-only, checksummed v2 SQLite migrations."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        payload = "\n".join((str(self.version), self.name, *self.statements)).encode("utf-8")
        return sha256(payload).hexdigest()


MIGRATIONS: tuple[Migration, ...] = (
    Migration(1, "core_system", (
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY CHECK(version > 0), name TEXT NOT NULL, applied_at TEXT NOT NULL, checksum TEXT NOT NULL)",
        "CREATE TABLE settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL CHECK(json_valid(value_json)), revision INTEGER NOT NULL CHECK(revision >= 0), updated_at TEXT NOT NULL)",
        "CREATE TABLE channel_read_model (channel_id TEXT PRIMARY KEY, title TEXT NOT NULL, game_id TEXT, game_name TEXT, tags_json TEXT NOT NULL CHECK(json_valid(tags_json)), active_preset_id TEXT, observed_at TEXT NOT NULL, source TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 0))",
        "CREATE TABLE operation_log (id TEXT PRIMARY KEY, operation_type TEXT NOT NULL, target_type TEXT NOT NULL, target_id TEXT NOT NULL, state TEXT NOT NULL, message_code TEXT NOT NULL, request_id TEXT, started_at TEXT NOT NULL, finished_at TEXT, safe_details_json TEXT NOT NULL CHECK(json_valid(safe_details_json)))",
        "CREATE TABLE processed_event_ids (message_id TEXT PRIMARY KEY, message_type TEXT NOT NULL, received_at TEXT NOT NULL, expires_at TEXT NOT NULL)",
        "CREATE INDEX processed_event_ids_expires_at_idx ON processed_event_ids(expires_at)",
        "CREATE TABLE import_batches (id TEXT PRIMARY KEY, importer_version TEXT NOT NULL, imported_at TEXT NOT NULL, cutoff_at TEXT NOT NULL, source_manifest_json TEXT NOT NULL CHECK(json_valid(source_manifest_json)), source_base_reference TEXT NOT NULL, result TEXT NOT NULL, report_reference TEXT)",
    )),
    Migration(2, "domain_destination", (
        "CREATE TABLE streams (id TEXT PRIMARY KEY CHECK(length(id)>0), channel_id TEXT NOT NULL CHECK(length(channel_id)>0), title TEXT NOT NULL, game_id TEXT, game_name TEXT, thumbnail_url TEXT, tags_json TEXT NOT NULL CHECK(json_valid(tags_json) AND json_type(tags_json)='array'), started_at TEXT NOT NULL, ended_at TEXT, duration_seconds INTEGER CHECK(duration_seconds IS NULL OR (typeof(duration_seconds)='integer' AND duration_seconds>=0)), source TEXT NOT NULL CHECK(source IN ('bot','api','imported')), completeness TEXT NOT NULL CHECK(completeness IN ('full','samples_only','metadata_only','partial')), max_viewers INTEGER CHECK(max_viewers IS NULL OR (typeof(max_viewers)='integer' AND max_viewers>=0)), average_viewers REAL CHECK(average_viewers IS NULL OR (typeof(average_viewers) IN ('integer','real') AND average_viewers>=0)), follower_count INTEGER CHECK(follower_count IS NULL OR (typeof(follower_count)='integer' AND follower_count>=0)), total_comments INTEGER CHECK(total_comments IS NULL OR (typeof(total_comments)='integer' AND total_comments>=0)), legacy_metadata_json TEXT NOT NULL CHECK(json_valid(legacy_metadata_json) AND json_type(legacy_metadata_json)='object'), import_batch_id TEXT REFERENCES import_batches(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=0))",
        "CREATE INDEX streams_started_at_id_idx ON streams(started_at, id)",
        "CREATE TABLE stream_samples (stream_id TEXT NOT NULL REFERENCES streams(id) ON DELETE CASCADE, sampled_at TEXT NOT NULL, viewer_count INTEGER CHECK(viewer_count IS NULL OR (typeof(viewer_count)='integer' AND viewer_count>=0)), chat_count INTEGER CHECK(chat_count IS NULL OR (typeof(chat_count)='integer' AND chat_count>=0)), messages_per_minute REAL CHECK(messages_per_minute IS NULL OR ((typeof(messages_per_minute) IN ('integer','real')) AND messages_per_minute>=0)), bits INTEGER CHECK(bits IS NULL OR (typeof(bits)='integer' AND bits>=0)), gift_subscriptions INTEGER CHECK(gift_subscriptions IS NULL OR (typeof(gift_subscriptions)='integer' AND gift_subscriptions>=0)), follower_total INTEGER CHECK(follower_total IS NULL OR (typeof(follower_total)='integer' AND follower_total>=0)), PRIMARY KEY(stream_id,sampled_at))",
        "CREATE TABLE viewers (user_id TEXT PRIMARY KEY CHECK(length(user_id)>0), login TEXT, display_name TEXT, followed_at TEXT, unfollowed_at TEXT, visit_count INTEGER CHECK(visit_count IS NULL OR (typeof(visit_count)='integer' AND visit_count>=0)), watch_seconds INTEGER CHECK(watch_seconds IS NULL OR (typeof(watch_seconds)='integer' AND watch_seconds>=0)), comment_count INTEGER CHECK(comment_count IS NULL OR (typeof(comment_count)='integer' AND comment_count>=0)), bits_total INTEGER CHECK(bits_total IS NULL OR (typeof(bits_total)='integer' AND bits_total>=0)), is_subscriber INTEGER CHECK(is_subscriber IS NULL OR is_subscriber IN (0,1)), sub_months INTEGER CHECK(sub_months IS NULL OR (typeof(sub_months)='integer' AND sub_months>=0)), last_sub_at TEXT, last_sub_plan TEXT, gifts_given INTEGER CHECK(gifts_given IS NULL OR (typeof(gifts_given)='integer' AND gifts_given>=0)), gifts_received INTEGER CHECK(gifts_received IS NULL OR (typeof(gifts_received)='integer' AND gifts_received>=0)), streak INTEGER CHECK(streak IS NULL OR (typeof(streak)='integer' AND streak>=0)), last_seen_at TEXT, last_stream_id TEXT, note TEXT, legacy_metadata_json TEXT NOT NULL CHECK(json_valid(legacy_metadata_json) AND json_type(legacy_metadata_json)='object'), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=0))",
        "CREATE INDEX viewers_login_idx ON viewers(login)",
        "CREATE INDEX viewers_last_seen_idx ON viewers(last_seen_at)",
        "CREATE TABLE vod_assets (id TEXT PRIMARY KEY CHECK(length(id)>0), stream_id TEXT NOT NULL UNIQUE REFERENCES streams(id) ON DELETE CASCADE, twitch_vod_id TEXT, relative_path TEXT CHECK(relative_path IS NULL OR (length(relative_path)>0 AND relative_path NOT LIKE '/%' AND relative_path NOT LIKE '%\\%' AND relative_path NOT LIKE '%//%' AND relative_path NOT IN ('.','..') AND relative_path NOT LIKE './%' AND relative_path NOT LIKE '../%' AND relative_path NOT LIKE '%/./%' AND relative_path NOT LIKE '%/../%' AND relative_path NOT LIKE '%/.' AND relative_path NOT LIKE '%/..')), size_bytes INTEGER CHECK(size_bytes IS NULL OR (typeof(size_bytes)='integer' AND size_bytes>=0)), discovered_at TEXT, verified_at TEXT, remote_state TEXT NOT NULL CHECK(length(remote_state)>0), local_state TEXT NOT NULL CHECK(length(local_state)>0), revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision>=0))",
    )),
)
