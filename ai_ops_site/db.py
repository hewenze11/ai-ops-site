"""Database schema and access helpers for the AI Ops website.

Kept intentionally plain (sqlite3, explicit DDL) so the whole state is one file
you can back up or delete. No ORM: this is a small, auditable surface.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    created_at    REAL NOT NULL
);

-- A course is a sellable bundle of videos. price_cents = 0 means free.
CREATE TABLE IF NOT EXISTS courses(
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    cover_url   TEXT NOT NULL DEFAULT '',
    sort        INTEGER NOT NULL DEFAULT 100,
    published   INTEGER NOT NULL DEFAULT 1,
    created_at  REAL NOT NULL
);

-- A video belongs to a course. A course is "unlocked" only when purchased.
CREATE TABLE IF NOT EXISTS videos(
    id          TEXT PRIMARY KEY,
    course_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    duration_s  INTEGER NOT NULL DEFAULT 0,
    sort        INTEGER NOT NULL DEFAULT 100
);

-- What a user owns. kind='course' -> course_id; kind='subscription' -> plan.
CREATE TABLE IF NOT EXISTS entitlements(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    ref        TEXT NOT NULL,
    granted_at REAL NOT NULL,
    expires_at REAL,
    UNIQUE(user_id, kind, ref)
);

-- Orders. state: 'created' -> 'paid' | 'cancelled'. Provider is recorded so a
-- simulated order is never mistaken for a real one.
CREATE TABLE IF NOT EXISTS orders(
    id            TEXT PRIMARY KEY,
    user_id       INTEGER NOT NULL,
    kind          TEXT NOT NULL,
    ref           TEXT NOT NULL,
    amount_cents  INTEGER NOT NULL,
    state         TEXT NOT NULL,
    provider      TEXT NOT NULL,
    provider_ref  TEXT,
    created_at    REAL NOT NULL,
    paid_at       REAL
);

-- Skills hub. A skill here is a distributable bundle. The control service
-- imports skills shaped like {id,name,content,role_ids,enabled}.
CREATE TABLE IF NOT EXISTS skills(
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    content     TEXT NOT NULL,
    role_ids    TEXT NOT NULL DEFAULT '[]',
    tier        TEXT NOT NULL DEFAULT 'standard',   -- standard | premium
    published   INTEGER NOT NULL DEFAULT 1,
    revision    INTEGER NOT NULL DEFAULT 1,
    updated_at  REAL NOT NULL
);

-- Pull keys: minted for subscribers. One user may hold several (e.g. per host).
CREATE TABLE IF NOT EXISTS pull_keys(
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    label       TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    revoked_at  REAL,
    last_used_at REAL
);

CREATE TABLE IF NOT EXISTS audit(
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    at         REAL NOT NULL,
    actor      TEXT NOT NULL,
    action     TEXT NOT NULL,
    subject    TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '{}'
);

-- Login sessions. The cookie carries a random token; only its hash is stored.
CREATE TABLE IF NOT EXISTS sessions(
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One transaction. Commits on success, rolls back on any exception."""
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, db: sqlite3.Connection, actor: str, action: str, subject: str,
              detail: dict | None = None) -> None:
        db.execute("INSERT INTO audit(at,actor,action,subject,detail) VALUES(?,?,?,?,?)",
                   (time.time(), actor, action, subject, json.dumps(detail or {}, ensure_ascii=False)))
