"""SQLite ma'lumotlar bazasi: foydalanuvchilar, shifrlangan shablonlar, audit jurnali.

Rasmlar hech qachon saqlanmaydi — faqat shifrlangan 512 o'lchamli vektorlar.
Audit jurnali xesh-zanjir ko'rinishida: har yozuv oldingisining SHA-256
xeshini o'z ichiga oladi, shuning uchun yozuvlarni sezdirmasdan o'zgartirish
yoki o'chirish mumkin emas (``verify_audit``).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .crypto import TemplateCipher

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA secure_delete=ON;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'user',
    created_at REAL NOT NULL,
    consent_at REAL NOT NULL,
    last_login REAL,
    failed INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0,
    lockouts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blob BLOB NOT NULL,
    quality REAL NOT NULL,
    model TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    event TEXT NOT NULL,
    user_id INTEGER,
    data TEXT NOT NULL,
    prev TEXT NOT NULL,
    hash TEXT NOT NULL
);
"""

MODEL_ID = "arcface-r50-w600k"
GENESIS = "0" * 64


@dataclass
class User:
    id: int
    name: str
    role: str
    created_at: float
    last_login: float | None
    failed: int
    locked_until: float
    lockouts: int
    templates: int = 0


class Database:
    def __init__(self, path: Path, cipher: TemplateCipher, audit_key: bytes) -> None:
        self.path = path
        self.cipher = cipher
        self._audit_key = audit_key
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._cache: dict[int, np.ndarray] | None = None

    # ----------------------------------------------------------------- meta
    def get_meta(self, k: str) -> str | None:
        r = self.conn.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r["v"] if r else None

    def set_meta(self, k: str, v: str) -> None:
        with self._lock:
            self.conn.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ---------------------------------------------------------------- users
    def add_user(self, name: str, embeddings: list[np.ndarray], qualities: list[float], role: str = "user") -> int:
        name = name.strip()
        if not name or len(name) > 64:
            raise ValueError("Ism 1–64 belgidan iborat bo'lishi kerak")
        now = time.time()
        with self._lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                cur = self.conn.execute("INSERT INTO users(name, role, created_at, consent_at) VALUES(?,?,?,?)",
                                        (name, role, now, now))
                uid = int(cur.lastrowid)
                for emb, q in zip(embeddings, qualities, strict=True):
                    self._insert_template(uid, emb, q, now)
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            self._cache = None
        return uid

    def _insert_template(self, uid: int, emb: np.ndarray, q: float, now: float) -> None:
        cur = self.conn.execute("INSERT INTO templates(user_id, blob, quality, model, created_at) VALUES(?,?,?,?,?)",
                                (uid, b"", float(q), MODEL_ID, now))
        tid = int(cur.lastrowid)
        data = np.asarray(emb, dtype=np.float32).tobytes()
        blob = self.cipher.encrypt(data, self._aad(uid, tid))
        self.conn.execute("UPDATE templates SET blob=? WHERE id=?", (blob, tid))

    @staticmethod
    def _aad(uid: int, tid: int) -> bytes:
        return f"faceid:{MODEL_ID}:{uid}:{tid}".encode()

    def users(self) -> list[User]:
        rows = self.conn.execute(
            "SELECT u.*, (SELECT COUNT(*) FROM templates t WHERE t.user_id=u.id) AS n FROM users u ORDER BY u.id"
        ).fetchall()
        return [User(r["id"], r["name"], r["role"], r["created_at"], r["last_login"], r["failed"],
                     r["locked_until"], r["lockouts"], r["n"]) for r in rows]

    def user(self, uid: int) -> User | None:
        return next((u for u in self.users() if u.id == uid), None)

    def user_by_name(self, name: str) -> User | None:
        return next((u for u in self.users() if u.name.lower() == name.strip().lower()), None)

    def delete_user(self, uid: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM users WHERE id=?", (uid,))
            self._cache = None
        # secure_delete=ON — o'chirilgan sahifalar nol bilan qayta yoziladi
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def gallery(self) -> dict[int, np.ndarray]:
        """Barcha foydalanuvchilarning deshifrlangan shablonlari (faqat xotirada)."""
        with self._lock:
            if self._cache is None:
                out: dict[int, list[np.ndarray]] = {}
                for r in self.conn.execute("SELECT id, user_id, blob FROM templates WHERE model=?", (MODEL_ID,)):
                    raw = self.cipher.decrypt(r["blob"], self._aad(r["user_id"], r["id"]))
                    out.setdefault(r["user_id"], []).append(np.frombuffer(raw, dtype=np.float32))
                self._cache = {k: np.stack(v) for k, v in out.items()}
            return dict(self._cache)

    # ------------------------------------------------- lockout (brute force)
    def record_attempt(self, uid: int | None, success: bool, base_s: int, max_failed: int) -> None:
        if uid is None:
            return
        with self._lock:
            if success:
                self.conn.execute("UPDATE users SET failed=0, last_login=? WHERE id=?", (time.time(), uid))
                return
            u = self.user(uid)
            if u is None:
                return
            failed = u.failed + 1
            if failed >= max_failed:
                lock_s = base_s * (2 ** min(u.lockouts, 8))
                self.conn.execute("UPDATE users SET failed=0, locked_until=?, lockouts=lockouts+1 WHERE id=?",
                                  (time.time() + lock_s, uid))
            else:
                self.conn.execute("UPDATE users SET failed=? WHERE id=?", (failed, uid))

    # ------------------------------------------------------------- audit
    def _audit_hash(self, prev: str, ts: float, event: str, uid: int | None, data: str) -> str:
        msg = json.dumps([prev, round(ts, 6), event, uid, data], ensure_ascii=False).encode()
        return hmac.new(self._audit_key, msg, hashlib.sha256).hexdigest()

    def audit(self, event: str, user_id: int | None = None, **data) -> None:
        with self._lock:
            row = self.conn.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            prev = row["hash"] if row else GENESIS
            ts = time.time()
            payload = json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
            h = self._audit_hash(prev, ts, event, user_id, payload)
            self.conn.execute("INSERT INTO audit(ts, event, user_id, data, prev, hash) VALUES(?,?,?,?,?,?)",
                              (ts, event, user_id, payload, prev, h))

    def audit_log(self, limit: int = 500) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def verify_audit(self) -> tuple[bool, int | None]:
        """Zanjirni tekshiradi. (to'g'ri, buzilgan_birinchi_id) qaytaradi."""
        prev = None
        for r in self.conn.execute("SELECT * FROM audit ORDER BY id"):
            if prev is not None and r["prev"] != prev:
                return False, r["id"]
            if self._audit_hash(r["prev"], r["ts"], r["event"], r["user_id"], r["data"]) != r["hash"]:
                return False, r["id"]
            prev = r["hash"]
        return True, None

    def prune_audit(self, retention_days: int) -> int:
        """Eski yozuvlarni o'chiradi; zanjir boshiga "checkpoint" yozuvi qo'shiladi."""
        cutoff = time.time() - retention_days * 86400
        with self._lock:
            n = self.conn.execute("SELECT COUNT(*) FROM audit WHERE ts < ?", (cutoff,)).fetchone()[0]
            if n:
                last = self.conn.execute("SELECT hash FROM audit WHERE ts < ? ORDER BY id DESC LIMIT 1",
                                         (cutoff,)).fetchone()["hash"]
                # Qolgan birinchi yozuvning prev'i o'chirilgan oxirgi yozuv xeshiga teng —
                # zanjirning qolgan qismi tekshiriladigan bo'lib qoladi.
                self.conn.execute("DELETE FROM audit WHERE ts < ?", (cutoff,))
                self.audit("audit_pruned", removed=n, anchor=last)
            return n

    def close(self) -> None:
        self.conn.close()
