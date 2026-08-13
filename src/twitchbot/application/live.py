"""Immutable, side-effect-free live snapshot boundary for the v2 pilot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal, Protocol, Mapping
from types import MappingProxyType

StreamState = Literal["unavailable", "offline", "live", "degraded"]
_CONNECTION_KEYS = frozenset({"twitch", "eventsub", "helix", "bot", "broadcaster"})
_STATE_CODES = frozenset({"healthy", "stopped", "degraded", "unavailable", "action_required"})
_BOT_STATES = frozenset({"running", "stopped", "unavailable", "action_required"})
_SESSION_KEYS = frozenset({"messages", "viewers", "events"})


def _utc(value: datetime | str, *, field_name: str) -> str:
    if isinstance(value, str):
        text = value
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"invalid {field_name}") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"invalid {field_name}")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class StreamSnapshot:
    state: StreamState = "unavailable"
    stale: bool = False
    observed_at: str = "1970-01-01T00:00:00Z"
    id: str | None = None
    title: str | None = None
    game: str | None = None
    started_at: str | None = None
    viewer_count: int | None = None

    def __post_init__(self) -> None:
        if self.state not in {"unavailable", "offline", "live", "degraded"}:
            raise ValueError("invalid stream state")
        if type(self.stale) is not bool:
            raise ValueError("invalid stale")
        object.__setattr__(self, "observed_at", _utc(self.observed_at, field_name="observed_at"))
        if self.started_at is not None:
            object.__setattr__(self, "started_at", _utc(self.started_at, field_name="started_at"))
        if self.viewer_count is not None and (type(self.viewer_count) is not int or self.viewer_count < 0):
            raise ValueError("invalid viewer_count")
        for name in ("id", "title", "game"):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value.strip() or len(value) > 200):
                raise ValueError(f"invalid {name}")

    def as_dict(self) -> dict[str, object]:
        return {"state": self.state, "stale": self.stale, "observed_at": self.observed_at,
                "id": self.id, "title": self.title, "game": self.game,
                "started_at": self.started_at, "viewer_count": self.viewer_count}


@dataclass(frozen=True, slots=True)
class LiveSnapshot:
    stream: StreamSnapshot = field(default_factory=StreamSnapshot)
    generated_at: str = "1970-01-01T00:00:00Z"
    revision: int = 0
    bot_enabled: bool | None = None
    bot_state: str = "unavailable"
    connections: Mapping[str, str] = field(default_factory=dict)
    session: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.stream, StreamSnapshot):
            raise ValueError("invalid stream")
        object.__setattr__(self, "generated_at", _utc(self.generated_at, field_name="generated_at"))
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("invalid revision")
        if self.bot_enabled is not None and type(self.bot_enabled) is not bool:
            raise ValueError("invalid bot_enabled")
        if self.bot_enabled is False and self.bot_state == "running":
            raise ValueError("invalid bot state")
        if not isinstance(self.connections, Mapping) or set(self.connections) - _CONNECTION_KEYS or not all(type(k) is str and k.strip() and type(v) is str and v in _STATE_CODES for k, v in self.connections.items()):
            raise ValueError("invalid connections")
        if not isinstance(self.session, Mapping) or set(self.session) - _SESSION_KEYS or not all(type(k) is str and type(v) is int and v >= 0 for k, v in self.session.items()):
            raise ValueError("invalid session")
        if type(self.bot_state) is not str or self.bot_state not in _BOT_STATES:
            raise ValueError("invalid bot_state")
        object.__setattr__(self, "bot_state", self.bot_state)
        object.__setattr__(self, "connections", MappingProxyType(dict(self.connections)))
        object.__setattr__(self, "session", MappingProxyType(dict(self.session)))

    def as_dict(self) -> dict[str, object]:
        return {"revision": self.revision, "generated_at": self.generated_at,
                "stream": self.stream.as_dict(), "bot": {"enabled": self.bot_enabled, "state": self.bot_state},
                "connections": dict(self.connections), "session": dict(self.session)}

    def etag(self) -> str:
        # The ETag represents the complete JSON representation.  In
        # particular, a bridge-generated ``generated_at`` changes the
        # response, so it must not produce a false 304 for a different body.
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        return '"' + sha256(payload).hexdigest() + '"'


class LiveSnapshotProvider(Protocol):
    def snapshot(self) -> LiveSnapshot: ...


class UnavailableLiveProvider:
    def snapshot(self) -> LiveSnapshot:
        return LiveSnapshot()


@dataclass(frozen=True, slots=True)
class StaticLiveProvider:
    value: LiveSnapshot

    def __post_init__(self) -> None:
        if not isinstance(self.value, LiveSnapshot):
            raise TypeError("value must be LiveSnapshot")

    def snapshot(self) -> LiveSnapshot:
        return self.value
