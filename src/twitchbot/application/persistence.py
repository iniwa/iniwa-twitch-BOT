"""Immutable persistence records and safe errors, independent of SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias

from ..settings import AppSettings


class PersistenceError(RuntimeError):
    """A safe failure whose message never includes stored values or paths."""

    def __init__(self, code: str, context: str = "persistence") -> None:
        self.code = code
        self.context = context
        super().__init__(f"persistence error ({code}) in {context}")


class RevisionConflictError(PersistenceError):
    def __init__(self, context: str) -> None:
        super().__init__("revision_conflict", context)


@dataclass(frozen=True, slots=True)
class FrozenObject:
    items: tuple[tuple[str, "FrozenJson"], ...]


@dataclass(frozen=True, slots=True)
class FrozenArray:
    items: tuple["FrozenJson", ...]


FrozenJson: TypeAlias = None | bool | int | float | str | FrozenArray | FrozenObject


def freeze_json_object(value: Mapping[str, Any]) -> FrozenObject:
    """Detach a JSON object into an immutable, JSON-compatible value tree."""
    if not isinstance(value, Mapping):
        raise PersistenceError("invalid_json_object", "persistence")

    def freeze(item: Any) -> FrozenJson:
        if item is None or type(item) in (bool, int, float, str):
            return item
        if isinstance(item, Mapping):
            if any(type(key) is not str for key in item):
                raise PersistenceError("invalid_json", "persistence")
            return FrozenObject(tuple(sorted((key, freeze(child)) for key, child in item.items())))
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            return FrozenArray(tuple(freeze(child) for child in item))
        raise PersistenceError("invalid_json", "persistence")

    return freeze(value)  # type: ignore[return-value]


def thaw_json(value: FrozenJson) -> Any:
    """Create a fresh JSON-compatible copy from a frozen value tree."""
    if isinstance(value, FrozenObject):
        return {key: thaw_json(child) for key, child in value.items}
    if isinstance(value, FrozenArray):
        return [thaw_json(item) for item in value.items]
    return value


@dataclass(frozen=True, slots=True)
class SettingsSnapshot:
    settings: AppSettings
    revision: int
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class ChannelReadModel:
    channel_id: str
    title: str
    game_id: str | None
    game_name: str | None
    tags: tuple[str, ...]
    active_preset_id: str | None
    observed_at: datetime
    source: str
    revision: int = 0


@dataclass(frozen=True, slots=True)
class OperationRecord:
    id: str
    operation_type: str
    target_type: str
    target_id: str
    state: str
    message_code: str
    request_id: str | None
    started_at: datetime
    finished_at: datetime | None
    safe_details: FrozenObject

    def __post_init__(self) -> None:
        source = thaw_json(self.safe_details) if isinstance(self.safe_details, FrozenObject) else self.safe_details
        object.__setattr__(self, "safe_details", freeze_json_object(source))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class ImportBatch:
    id: str
    importer_version: str
    imported_at: datetime
    cutoff_at: datetime
    source_manifest: FrozenObject
    source_base_reference: str
    result: str
    report_reference: str | None

    def __post_init__(self) -> None:
        source = thaw_json(self.source_manifest) if isinstance(self.source_manifest, FrozenObject) else self.source_manifest
        object.__setattr__(self, "source_manifest", freeze_json_object(source))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class StreamRecord:
    id: str
    channel_id: str
    title: str
    game_id: str | None
    game_name: str | None
    thumbnail_url: str | None
    tags: tuple[str, ...]
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    source: str
    completeness: str
    max_viewers: int | None
    average_viewers: float | None
    follower_count: int | None
    total_comments: int | None
    legacy_metadata: FrozenObject
    import_batch_id: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        source = thaw_json(self.legacy_metadata) if isinstance(self.legacy_metadata, FrozenObject) else self.legacy_metadata
        object.__setattr__(self, "legacy_metadata", freeze_json_object(source))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class StreamSample:
    stream_id: str
    sampled_at: datetime
    viewer_count: int | None = None
    chat_count: int | None = None
    messages_per_minute: float | None = None
    bits: int | None = None
    gift_subscriptions: int | None = None
    follower_total: int | None = None


@dataclass(frozen=True, slots=True)
class ViewerRecord:
    user_id: str
    login: str | None
    display_name: str | None
    followed_at: datetime | None
    unfollowed_at: datetime | None
    visit_count: int | None
    watch_seconds: int | None
    comment_count: int | None
    bits_total: int | None
    is_subscriber: bool | None
    sub_months: int | None
    last_sub_at: datetime | None
    last_sub_plan: str | None
    gifts_given: int | None
    gifts_received: int | None
    streak: int | None
    last_seen_at: datetime | None
    last_stream_id: str | None
    note: str | None
    legacy_metadata: FrozenObject
    created_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 0

    def __post_init__(self) -> None:
        source = thaw_json(self.legacy_metadata) if isinstance(self.legacy_metadata, FrozenObject) else self.legacy_metadata
        object.__setattr__(self, "legacy_metadata", freeze_json_object(source))  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class VodAsset:
    id: str
    stream_id: str
    twitch_vod_id: str | None
    relative_path: str | None
    size_bytes: int | None
    discovered_at: datetime | None
    verified_at: datetime | None
    remote_state: str
    local_state: str
    revision: int = 0
