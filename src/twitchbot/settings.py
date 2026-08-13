"""Credential-free, strictly validated v2 operational settings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any


class SettingsValidationError(ValueError):
    """Safe validation failure with a stable code and non-secret field name."""

    def __init__(self, code: str, field: str = "mapping") -> None:
        self.code = code
        self.field = field if field in _KNOWN_KEYS else "mapping"
        super().__init__(f"invalid settings ({code}) at {self.field}")


_KNOWN_KEYS = frozenset(
    {
        "bot_enabled",
        "welcome_enabled",
        "ignore_stream_status",
        "enable_vod_download",
        "stream_poll_interval_seconds",
        "metrics_flush_interval_seconds",
        "hide_self_bot",
        "ignored_users",
    }
)
_CREDENTIAL_WORDS = ("token", "secret", "password", "authorization", "credential")
_LOGIN_RE = re.compile(r"^[a-z0-9_]{1,25}$")


def _bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise SettingsValidationError("invalid_type", field)
    return value


def _int(value: Any, field: str, low: int, high: int) -> int:
    if type(value) is not int:
        raise SettingsValidationError("invalid_type", field)
    if not low <= value <= high:
        raise SettingsValidationError("out_of_range", field)
    return value


def _users(value: Any) -> tuple[str, ...]:
    field = "ignored_users"
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SettingsValidationError("invalid_type", field)
    if len(value) > 100:
        raise SettingsValidationError("too_many_filters", field)
    result: list[str] = []
    seen: set[str] = set()
    for user in value:
        if type(user) is not str or not _LOGIN_RE.fullmatch(user):
            raise SettingsValidationError("invalid_filter", field)
        if user in seen:
            raise SettingsValidationError("duplicate_filter", field)
        seen.add(user)
        result.append(user)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class AppSettings:
    bot_enabled: bool = False
    welcome_enabled: bool = False
    ignore_stream_status: bool = False
    enable_vod_download: bool = False
    stream_poll_interval_seconds: int = 20
    metrics_flush_interval_seconds: int = 60
    hide_self_bot: bool = False
    ignored_users: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in (
            "bot_enabled",
            "welcome_enabled",
            "ignore_stream_status",
            "enable_vod_download",
            "hide_self_bot",
        ):
            _bool(getattr(self, field), field)
        _int(self.stream_poll_interval_seconds, "stream_poll_interval_seconds", 1, 300)
        _int(self.metrics_flush_interval_seconds, "metrics_flush_interval_seconds", 1, 3600)
        users = _users(self.ignored_users)
        object.__setattr__(self, "ignored_users", users)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "AppSettings":
        if not isinstance(values, Mapping):
            raise SettingsValidationError("invalid_type")
        for key in values:
            if not isinstance(key, str):
                raise SettingsValidationError("unknown_key")
            if key not in _KNOWN_KEYS:
                code = "credential_key" if any(word in key.lower() for word in _CREDENTIAL_WORDS) else "unknown_key"
                raise SettingsValidationError(code)
        data = {
            "bot_enabled": _bool(values.get("bot_enabled", False), "bot_enabled"),
            "welcome_enabled": _bool(values.get("welcome_enabled", False), "welcome_enabled"),
            "ignore_stream_status": _bool(values.get("ignore_stream_status", False), "ignore_stream_status"),
            "enable_vod_download": _bool(values.get("enable_vod_download", False), "enable_vod_download"),
            "stream_poll_interval_seconds": _int(values.get("stream_poll_interval_seconds", 20), "stream_poll_interval_seconds", 1, 300),
            "metrics_flush_interval_seconds": _int(values.get("metrics_flush_interval_seconds", 60), "metrics_flush_interval_seconds", 1, 3600),
            "hide_self_bot": _bool(values.get("hide_self_bot", False), "hide_self_bot"),
            "ignored_users": _users(values.get("ignored_users", ())),
        }
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "bot_enabled": self.bot_enabled,
            "welcome_enabled": self.welcome_enabled,
            "ignore_stream_status": self.ignore_stream_status,
            "enable_vod_download": self.enable_vod_download,
            "stream_poll_interval_seconds": self.stream_poll_interval_seconds,
            "metrics_flush_interval_seconds": self.metrics_flush_interval_seconds,
            "hide_self_bot": self.hide_self_bot,
            "ignored_users": list(self.ignored_users),
        }
