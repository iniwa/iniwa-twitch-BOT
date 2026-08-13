"""Deterministic unavailable adapters used until real integrations are approved."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal


@dataclass(frozen=True, slots=True)
class AdapterAvailability:
    available: bool = False
    code: str = "not_configured"


@dataclass(frozen=True, slots=True)
class CredentialStatus:
    role: str
    code: str = "not_configured"


class AdapterUnavailableError(RuntimeError):
    code: Final[str] = "not_configured"

    def __init__(self, adapter: str) -> None:
        self.adapter = adapter
        super().__init__(f"{adapter} adapter is not configured")


class NullTwitchAdapter:
    def status(self) -> AdapterAvailability:
        return AdapterAvailability()

    def require(self) -> None:
        raise AdapterUnavailableError("twitch")


class NullMediaAdapter:
    def status(self) -> AdapterAvailability:
        return AdapterAvailability()

    def require(self) -> None:
        raise AdapterUnavailableError("media")


class NullCredentialRegistry:
    _ROLES = ("bot", "broadcaster")

    def status(self, role: Literal["bot", "broadcaster"]) -> CredentialStatus:
        if role not in self._ROLES:
            raise ValueError("unknown credential role")
        return CredentialStatus(role=role)

    def resolve(self, role: Literal["bot", "broadcaster"]) -> None:
        if role not in self._ROLES:
            raise ValueError("unknown credential role")
        raise AdapterUnavailableError(f"credential:{role}")


@dataclass(frozen=True, slots=True)
class AdapterSet:
    twitch: NullTwitchAdapter
    media: NullMediaAdapter
    credentials: NullCredentialRegistry

    @classmethod
    def unavailable(cls) -> "AdapterSet":
        return cls(NullTwitchAdapter(), NullMediaAdapter(), NullCredentialRegistry())
