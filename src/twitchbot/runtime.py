"""Explicit, idempotent runtime lifecycle boundary for v2."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Literal

RuntimeState = Literal["stopped", "running"]


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    state: RuntimeState
    ready: bool

    def as_dict(self) -> dict[str, object]:
        return {"state": self.state, "ready": self.ready}


class RuntimeSupervisor:
    """Own lifecycle state without starting threads during construction/import."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state: RuntimeState = "stopped"

    def start(self) -> RuntimeSnapshot:
        with self._lock:
            self._state = "running"
            return self.snapshot()

    def stop(self) -> RuntimeSnapshot:
        with self._lock:
            self._state = "stopped"
            return self.snapshot()

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            running = self._state == "running"
            return RuntimeSnapshot(state=self._state, ready=running)
