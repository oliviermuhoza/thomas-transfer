"""Database connections: stdlib sqlite3 locally, libSQL (Turso) when configured.

The rest of the app expects sqlite3 behaviour: rows addressable by column name,
``dict(row)`` working, and ``sqlite3.IntegrityError`` on constraint violations.
The libSQL driver returns plain tuples, has no ``row_factory`` and raises
``ValueError``, so it is wrapped here instead of across every route.
"""

import os
import sqlite3
from pathlib import Path

URL_PREFIXES = ("libsql://", "https://", "http://", "file:")


def resolve_driver(database, driver=None):
    """Pick the driver: an explicit name wins, then the shape of the target."""
    if driver:
        return driver
    value = str(database or "")
    return "libsql" if value.startswith(URL_PREFIXES) else "sqlite"


def connect(database, driver=None, auth_token=None):
    kind = resolve_driver(database, driver)
    if kind == "libsql":
        return _connect_libsql(database, auth_token)
    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    return connection


def _connect_libsql(database, auth_token):
    try:
        import libsql
    except ImportError as exc:  # pragma: no cover - requirements include it
        raise RuntimeError(
            "The libsql package is required for TURSO_DATABASE_URL. "
            "Install backend/requirements.txt."
        ) from exc

    target = str(database)
    if not target.startswith(URL_PREFIXES) and target != ":memory:":
        target = "file:" + str(Path(target).resolve())
    return LibsqlConnection(libsql.connect(target, auth_token=auth_token or ""))


class Row:
    """A row that behaves like sqlite3.Row for both index and name access."""

    __slots__ = ("_values", "_index")

    def __init__(self, values, index):
        self._values = tuple(values)
        self._index = index

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        return self._values[self._index[key]]

    def keys(self):
        return list(self._index)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    def __repr__(self):
        return f"Row({dict(zip(self._index, self._values))!r})"


class LibsqlCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._index = None

    def _columns(self):
        if self._index is None:
            description = self._cursor.description or ()
            self._index = {column[0]: position for position, column in enumerate(description)}
        return self._index

    def fetchone(self):
        row = self._cursor.fetchone()
        return None if row is None else Row(row, self._columns())

    def fetchall(self):
        rows = self._cursor.fetchall()
        index = self._columns()
        return [Row(row, index) for row in rows]

    def __iter__(self):
        index = self._columns()
        for row in self._cursor.fetchall():
            yield Row(row, index)

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def close(self):
        self._cursor.close()


class LibsqlConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, parameters=()):
        try:
            return LibsqlCursor(self._connection.execute(sql, parameters))
        except Exception as exc:
            _translate_error(exc)

    def executemany(self, sql, parameters):
        try:
            return LibsqlCursor(self._connection.executemany(sql, parameters))
        except Exception as exc:
            _translate_error(exc)

    def executescript(self, script):
        return self._connection.executescript(script)

    def cursor(self):
        return LibsqlCursor(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    @property
    def in_transaction(self):
        return getattr(self._connection, "in_transaction", False)


def _translate_error(exc):
    """Re-raise libSQL errors as the sqlite3 types the app already handles."""
    message = str(exc)
    lowered = message.lower()
    if "constraint failed" in lowered or "unique constraint" in lowered:
        raise sqlite3.IntegrityError(message) from exc
    raise exc
