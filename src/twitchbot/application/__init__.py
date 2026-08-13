"""Application-level contracts with no framework or SQLite dependency."""

from .persistence import (
    ChannelReadModel,
    ImportBatch,
    OperationRecord,
    PersistenceError,
    RevisionConflictError,
    SettingsSnapshot,
    StreamRecord, StreamSample, ViewerRecord, VodAsset,
)

__all__ = ["ChannelReadModel", "ImportBatch", "OperationRecord", "PersistenceError", "RevisionConflictError", "SettingsSnapshot", "StreamRecord", "StreamSample", "ViewerRecord", "VodAsset"]

from .live import LiveSnapshot, LiveSnapshotProvider, StaticLiveProvider, StreamSnapshot, UnavailableLiveProvider

__all__ += ["LiveSnapshot", "LiveSnapshotProvider", "StaticLiveProvider", "StreamSnapshot", "UnavailableLiveProvider"]
