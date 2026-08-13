"""Read-only publication bridge for the isolated v2 live pilot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Mapping

import config
from src.twitchbot.application.live import LiveSnapshot, StreamSnapshot


Observation = tuple[dict | None, object | None]


class LegacyCurrentStreamLiveProvider:
    """Translate the legacy worker's copied stream observation into v2 data.

    The injected reader is the complete request-time dependency boundary.  It
    must return the legacy lock-protected detached snapshot and observation
    timestamp; this class deliberately does no configuration or service I/O.
    """

    def __init__(
        self,
        observation_reader: Callable[[], Observation] = config.get_current_stream_observation,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not callable(observation_reader) or not callable(clock):
            raise TypeError("bridge dependencies must be callable")
        self._observation_reader = observation_reader
        self._clock = clock

    def snapshot(self) -> LiveSnapshot:
        generated_at = self._generated_at()
        try:
            stream, observed_at = self._observation_reader()
        except Exception:
            return self._unknown("degraded", True, generated_at=generated_at)

        if observed_at is None:
            return self._unknown("unavailable", False, generated_at=generated_at)
        try:
            observed = self._timestamp(observed_at)
        except (TypeError, ValueError):
            return self._unknown("degraded", True, generated_at=generated_at)
        if stream is None:
            return LiveSnapshot(
                stream=StreamSnapshot(state="offline", stale=False, observed_at=observed),
                generated_at=generated_at,
                bot_enabled=None,
                bot_state="unavailable",
            )
        try:
            return LiveSnapshot(
                stream=StreamSnapshot(
                    state="live",
                    stale=False,
                    observed_at=observed,
                    id=self._text(stream, "id", required=True),
                    title=self._text(stream, "title"),
                    game=self._text(stream, "game_name"),
                    started_at=self._optional_timestamp(stream.get("started_at")),
                ),
                generated_at=generated_at,
                bot_enabled=None,
                bot_state="unavailable",
            )
        except (AttributeError, TypeError, ValueError):
            return self._unknown("degraded", True, observed, generated_at)

    def _generated_at(self) -> str:
        try:
            return self._timestamp(self._clock())
        except (TypeError, ValueError):
            return "1970-01-01T00:00:00Z"

    @staticmethod
    def _timestamp(value: object) -> str:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("naive timestamp")
            return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        if isinstance(value, str):
            return StreamSnapshot(observed_at=value).observed_at
        raise TypeError("invalid timestamp")

    @staticmethod
    def _optional_timestamp(value: object) -> str | None:
        return None if value is None else LegacyCurrentStreamLiveProvider._timestamp(value)

    @staticmethod
    def _text(stream: Mapping[str, object], key: str, *, required: bool = False) -> str | None:
        value = stream.get(key)
        if value is None and not required:
            return None
        if type(value) is not str or not value.strip() or len(value) > 200:
            raise ValueError("invalid stream metadata")
        return value

    @staticmethod
    def _unknown(
        state: str,
        stale: bool,
        observed_at: str = "1970-01-01T00:00:00Z",
        generated_at: str = "1970-01-01T00:00:00Z",
    ) -> LiveSnapshot:
        return LiveSnapshot(
            stream=StreamSnapshot(state=state, stale=stale, observed_at=observed_at),
            generated_at=generated_at,
            bot_enabled=None,
            bot_state="unavailable",
        )
