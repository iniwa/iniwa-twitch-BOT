"""Small dependency container for the v2 application boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from .adapters import AdapterSet
from .runtime import RuntimeSupervisor
from .settings import AppSettings
from .application.live import LiveSnapshotProvider, UnavailableLiveProvider


@dataclass(slots=True)
class Container:
    """Dependencies owned by one v2 app instance.

    The default supervisor is inert until explicitly started by the caller.
    ``adapters`` is intentionally an opaque mapping for later migration slices.
    """

    runtime: RuntimeSupervisor = field(default_factory=RuntimeSupervisor)
    settings: AppSettings = field(default_factory=AppSettings)
    adapters: AdapterSet = field(default_factory=AdapterSet.unavailable)
    live_provider: LiveSnapshotProvider = field(default_factory=UnavailableLiveProvider)
