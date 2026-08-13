"""Side-effect-free adapter contracts and unavailable implementations."""

from .null import (
    AdapterAvailability,
    AdapterUnavailableError,
    CredentialStatus,
    NullCredentialRegistry,
    NullMediaAdapter,
    NullTwitchAdapter,
    AdapterSet,
)

__all__ = [
    "AdapterAvailability",
    "AdapterSet",
    "AdapterUnavailableError",
    "CredentialStatus",
    "NullCredentialRegistry",
    "NullMediaAdapter",
    "NullTwitchAdapter",
]
