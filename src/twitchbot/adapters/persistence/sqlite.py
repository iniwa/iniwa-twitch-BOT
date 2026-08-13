"""Explicit SQLite connection and migration boundaries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Iterator

from ...application.persistence import PersistenceError
from .migrations import MIGRATIONS, Migration

DEFAULT_DATABASE_PATH = "/app/data/twitchbot-v2.sqlite3"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_rfc3339(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise PersistenceError("invalid_timestamp", "clock")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def from_rfc3339(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise PersistenceError("invalid_timestamp", "database") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PersistenceError("invalid_timestamp", "database")
    return parsed.astimezone(timezone.utc)


def validate_database_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.name.casefold() == "data.db":
        raise PersistenceError("forbidden_database_name", "database_path")
    if not candidate.is_absolute() or candidate.suffix.casefold() != ".sqlite3":
        raise PersistenceError("invalid_database_path", "database_path")
    return candidate


def validate_migrations(migrations: Sequence[Migration]) -> tuple[Migration, ...]:
    try:
        checked = tuple(migrations)
    except TypeError as error:
        raise PersistenceError("invalid_migrations", "migrations") from error
    if not checked:
        raise PersistenceError("invalid_migrations", "migrations")
    for expected, migration in enumerate(checked, start=1):
        if not isinstance(migration, Migration) or type(migration.version) is not int or migration.version != expected:
            raise PersistenceError("invalid_migrations", "migrations")
        if not isinstance(migration.name, str) or not migration.name.strip():
            raise PersistenceError("invalid_migrations", "migrations")
        if not isinstance(migration.statements, tuple) or not migration.statements:
            raise PersistenceError("invalid_migrations", "migrations")
        if any(type(statement) is not str or not statement.strip() for statement in migration.statements):
            raise PersistenceError("invalid_migrations", "migrations")
    if len({migration.name for migration in checked}) != len(checked):
        raise PersistenceError("invalid_migrations", "migrations")
    return checked


class SQLiteDatabase:
    """A path policy plus fresh same-thread SQLite connections; construction is inert."""

    def __init__(self, path: str | Path = DEFAULT_DATABASE_PATH, *, clock: Callable[[], datetime] = utc_now,
                 migrations: Sequence[Migration] = MIGRATIONS) -> None:
        self.path = validate_database_path(path)
        self._clock = clock
        self._migrations = validate_migrations(migrations)

    def connect(self) -> sqlite3.Connection:
        if not self.path.parent.is_dir():
            raise PersistenceError("database_parent_missing", "database_path")
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self.path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise PersistenceError("journal_mode_unavailable", "connection")
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise PersistenceError("foreign_keys_unavailable", "connection")
            if connection.execute("PRAGMA busy_timeout").fetchone()[0] != 5000:
                raise PersistenceError("busy_timeout_unavailable", "connection")
            return connection
        except PersistenceError:
            if connection is not None:
                connection.close()
            raise
        except sqlite3.Error as error:
            if connection is not None:
                connection.close()
            raise PersistenceError("connection_failed", "connection") from error

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def quick_check(self) -> None:
        try:
            with self.connection() as connection:
                rows = connection.execute("PRAGMA quick_check").fetchall()
            if len(rows) != 1 or rows[0][0] != "ok":
                raise PersistenceError("integrity_check_failed", "quick_check")
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("integrity_check_failed", "quick_check") from error

    def migrate(self) -> None:
        try:
            with self.connection() as connection:
                existing = self._read_existing(connection)
                for migration in self._migrations[len(existing):]:
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        for statement in migration.statements:
                            connection.execute(statement)
                        connection.execute("INSERT INTO schema_migrations(version, name, applied_at, checksum) VALUES (?, ?, ?, ?)",
                                           (migration.version, migration.name, to_rfc3339(self._clock()), migration.checksum))
                        connection.commit()
                    except (sqlite3.Error, PersistenceError):
                        connection.rollback()
                        raise
        except PersistenceError:
            raise
        except sqlite3.Error as error:
            raise PersistenceError("migration_failed", "migrations") from error

    def _read_existing(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        table = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
        if table is None:
            return []
        rows = connection.execute("SELECT version, name, checksum FROM schema_migrations ORDER BY version").fetchall()
        if any(row["version"] > len(self._migrations) for row in rows):
            raise PersistenceError("schema_newer_than_code", "migrations")
        for expected, row in enumerate(rows, start=1):
            migration = self._migrations[expected - 1]
            if row["version"] != expected:
                raise PersistenceError("invalid_migration_history", "migrations")
            if row["name"] != migration.name or row["checksum"] != migration.checksum:
                raise PersistenceError("migration_drift", "migrations")
        return rows
