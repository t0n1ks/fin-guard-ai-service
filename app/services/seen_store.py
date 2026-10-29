"""
Compact per-user memory of which pool items a user has already seen.

One small binary row per user (~0.2–0.3 KB), never one row per item:

  * a BITSET per bucket (bit i = item i of that bucket has been shown),
    shared across languages, so switching language never repeats an item;
  * the day the bucket's current pass began (for the 2-month reset rule);
  * the last few items shown (so repeats, once allowed, avoid them);
  * per message type, the last few variants used.

Buckets and message types are FIXED, APPEND-ONLY orders: the binary layout
depends on them. Items inside a bucket are append-only too (model.py), so a
bit always means the same item.

Storage: the AI service's own PostgreSQL (table ``companion_seen``) when
DATABASE_URL is set, else a JSON file (development). Reads and writes touch
exactly one user's row.

Binary layout, version 1:
    B   version
    per bucket (BUCKETS order):  H cycle_day · H nbytes · bits · B nrecent · H×nrecent
    B   count of message entries
    per entry:                   B type index · B nrecent · B×nrecent
A shorter blob (an older layout with fewer buckets) decodes with defaults.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import struct
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

logger = logging.getLogger(__name__)

VERSION = 1
BUCKETS: tuple[str, ...] = ("jokes", "facts", "tips", "exits", "quota", "encouragements")
MESSAGE_TYPES: tuple[str, ...] = (
    "overspent", "big_expense", "savings_deposit", "income", "pace_warn", "pace_over",
    "pace_recovered", "payday_tomorrow", "last_days", "week_checkin", "weekday_heads_up", "quest_ask",
)
RECENT = 3

_DB_URL = os.getenv("DATABASE_URL")
_USE_DB = bool(_DB_URL)
STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "state", "companion_seen.json")
_lock = threading.Lock()


@dataclass
class Bucket:
    bits: bytearray = field(default_factory=bytearray)
    cycle_day: int = 0  # day number the current pass began; 0 = never used
    recent: list[int] = field(default_factory=list)

    def seen(self, i: int) -> bool:
        byte = i // 8
        return byte < len(self.bits) and bool(self.bits[byte] & (1 << (i % 8)))

    def mark(self, i: int) -> None:
        byte = i // 8
        if byte >= len(self.bits):
            self.bits.extend(b"\x00" * (byte + 1 - len(self.bits)))
        self.bits[byte] |= 1 << (i % 8)

    def remember(self, i: int) -> None:
        remember(self.recent, i)


def remember(recent: list[int], i: int) -> None:
    """Keep the last RECENT indices, newest last."""
    if i in recent:
        recent.remove(i)
    recent.append(i)
    del recent[:-RECENT]


@dataclass
class SeenState:
    buckets: dict[str, Bucket] = field(default_factory=dict)
    messages: dict[str, list[int]] = field(default_factory=dict)

    def bucket(self, name: str) -> Bucket:
        assert name in BUCKETS, name
        return self.buckets.setdefault(name, Bucket())

    def message_recent(self, type_: str) -> list[int]:
        return self.messages.setdefault(type_, [])

    # ── binary codec ────────────────────────────────────────────────────────

    def encode(self) -> bytes:
        out = bytearray(struct.pack("<B", VERSION))
        for name in BUCKETS:
            b = self.buckets.get(name, Bucket())
            out += struct.pack("<HH", b.cycle_day, len(b.bits)) + bytes(b.bits)
            out += struct.pack("<B", len(b.recent)) + b"".join(struct.pack("<H", i) for i in b.recent)
        entries = [(MESSAGE_TYPES.index(t), r) for t, r in self.messages.items() if t in MESSAGE_TYPES and r]
        out += struct.pack("<B", len(entries))
        for idx, recent in entries:
            out += struct.pack("<BB", idx, len(recent)) + bytes(i & 0xFF for i in recent)
        return bytes(out)

    @classmethod
    def decode(cls, data: bytes | None) -> "SeenState":
        state = cls()
        if not data:
            return state
        try:
            pos = 1  # version byte (only v1 exists)
            for name in BUCKETS:
                if pos >= len(data):
                    break
                cycle_day, n = struct.unpack_from("<HH", data, pos)
                pos += 4
                bits = bytearray(data[pos:pos + n])
                pos += n
                (nrecent,) = struct.unpack_from("<B", data, pos)
                pos += 1
                recent = list(struct.unpack_from(f"<{nrecent}H", data, pos))
                pos += 2 * nrecent
                state.buckets[name] = Bucket(bits=bits, cycle_day=cycle_day, recent=recent)
            if pos < len(data):
                (count,) = struct.unpack_from("<B", data, pos)
                pos += 1
                for _ in range(count):
                    idx, nrecent = struct.unpack_from("<BB", data, pos)
                    pos += 2
                    state.messages[MESSAGE_TYPES[idx]] = list(data[pos:pos + nrecent])
                    pos += nrecent
        except (struct.error, IndexError):
            logger.warning("seen_store: unreadable blob — starting fresh")
            return cls()
        return state


# ── persistence (one user per read / write) ───────────────────────────────────

def _ensure_table() -> None:
    import psycopg2
    with psycopg2.connect(_DB_URL, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS companion_seen (
                    user_id    INTEGER     PRIMARY KEY,
                    data       BYTEA       NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
        conn.commit()


if _USE_DB:
    try:
        _ensure_table()
    except Exception as exc:  # pragma: no cover - depends on the deployment
        logger.warning("seen_store: DB table setup failed (%s) — falling back to file", exc)
        _USE_DB = False


def _db_load(user_id: int) -> bytes | None:
    import psycopg2
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM companion_seen WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
    return bytes(row[0]) if row else None


def _db_save(user_id: int, blob: bytes) -> None:
    import psycopg2
    with psycopg2.connect(_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO companion_seen (user_id, data, updated_at) VALUES (%s, %s, now())
                ON CONFLICT (user_id) DO UPDATE SET data = EXCLUDED.data, updated_at = now()
                """,
                (user_id, psycopg2.Binary(blob)),
            )
        conn.commit()


def _file_read() -> dict[str, str]:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _file_load(user_id: int) -> bytes | None:
    raw = _file_read().get(str(user_id))
    return base64.b64decode(raw) if raw else None


def _file_save(user_id: int, blob: bytes) -> None:
    data = _file_read()
    data[str(user_id)] = base64.b64encode(blob).decode("ascii")
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(STATE_FILE), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, STATE_FILE)


def exists(user_id: int) -> bool:
    return (_db_load(user_id) if _USE_DB else _file_load(user_id)) is not None


@contextmanager
def session(user_id: int) -> Iterator[SeenState]:
    """Load the user's state, let the caller change it, save it back."""
    with _lock:
        blob = _db_load(user_id) if _USE_DB else _file_load(user_id)
        state = SeenState.decode(blob)
        yield state
        new = state.encode()
        if new != blob:
            if _USE_DB:
                _db_save(user_id, new)
            else:
                _file_save(user_id, new)
