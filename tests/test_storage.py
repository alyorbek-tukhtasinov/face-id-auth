import sqlite3
import time

import numpy as np
import pytest
from cryptography.exceptions import InvalidTag

from faceid.storage.crypto import KeyStore, TemplateCipher
from faceid.storage.db import Database


@pytest.fixture
def db(tmp_path):
    key = KeyStore(tmp_path, use_keyring=False).load_or_create()
    d = Database(tmp_path / "t.db", TemplateCipher(key), b"a" * 32)
    yield d
    d.close()


def _embs(n, seed=0):
    rng = np.random.default_rng(seed)
    e = rng.normal(size=(n, 512)).astype(np.float32)
    return list(e / np.linalg.norm(e, axis=1, keepdims=True))


def test_keystore_persistent(tmp_path):
    k1 = KeyStore(tmp_path, use_keyring=False).load_or_create()
    k2 = KeyStore(tmp_path, use_keyring=False).load_or_create()
    assert k1 == k2 and len(k1) == 32


def test_cipher_roundtrip_and_aad():
    c = TemplateCipher(b"k" * 32)
    blob = c.encrypt(b"secret", b"aad1")
    assert c.decrypt(blob, b"aad1") == b"secret"
    assert b"secret" not in blob
    with pytest.raises(InvalidTag):
        c.decrypt(blob, b"aad2")


def test_templates_encrypted_at_rest(db, tmp_path):
    embs = _embs(3)
    uid = db.add_user("Ali", embs, [80, 81, 82])
    raw = (tmp_path / "t.db").read_bytes()
    assert embs[0].tobytes()[:64] not in raw
    g = db.gallery()
    np.testing.assert_allclose(g[uid], np.stack(embs))


def test_template_swap_detected(db):
    u1 = db.add_user("A", _embs(1, 1), [80])
    db.add_user("B", _embs(1, 2), [80])
    # Hujumchi B ning shablonini A ning yozuviga ko'chiradi
    b_blob = db.conn.execute("SELECT blob FROM templates WHERE user_id != ?", (u1,)).fetchone()[0]
    db.conn.execute("UPDATE templates SET blob=? WHERE user_id=?", (b_blob, u1))
    db._cache = None
    with pytest.raises(InvalidTag):
        db.gallery()


def test_delete_user_cascades(db):
    uid = db.add_user("A", _embs(2), [80, 80])
    db.delete_user(uid)
    assert db.users() == []
    assert db.conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0] == 0
    assert db.gallery() == {}


def test_unique_names(db):
    db.add_user("Ali", _embs(1), [80])
    with pytest.raises(sqlite3.IntegrityError):
        db.add_user("Ali", _embs(1), [80])


def test_audit_chain_detects_tampering(db):
    for i in range(5):
        db.audit("auth", None, ok=i % 2 == 0)
    assert db.verify_audit() == (True, None)
    db.conn.execute("UPDATE audit SET data=? WHERE id=3", ('{"ok": false}',))  # asl qiymat: true
    ok, bad = db.verify_audit()
    assert not ok and bad == 3


def test_audit_chain_detects_deletion(db):
    for i in range(5):
        db.audit("auth", None, n=i)
    db.conn.execute("DELETE FROM audit WHERE id=3")
    ok, bad = db.verify_audit()
    assert not ok and bad == 4


def test_lockout_exponential(db):
    uid = db.add_user("A", _embs(1), [80])
    for _ in range(3):
        db.record_attempt(uid, False, base_s=10, max_failed=3)
    u = db.user(uid)
    assert u.lockouts == 1 and u.locked_until > time.time() + 8
    for _ in range(3):
        db.record_attempt(uid, False, base_s=10, max_failed=3)
    assert db.user(uid).locked_until > time.time() + 18  # 2x
    db.record_attempt(uid, True, 10, 3)
    assert db.user(uid).failed == 0


def test_prune_audit_keeps_chain_valid(db):
    for i in range(4):
        db.audit("x", None, i=i)
    db.conn.execute("UPDATE audit SET ts = ts - 400*86400 WHERE id <= 2")
    # ts o'zgardi — xesh mos kelmaydi, shuning uchun to'g'ri yozuvlarni qayta yaratamiz
    db.conn.execute("DELETE FROM audit")
    old = time.time() - 400 * 86400
    prev = "0" * 64
    for i in range(4):
        ts = old if i < 2 else time.time()
        h = db._audit_hash(prev, ts, "x", None, "{}")
        db.conn.execute("INSERT INTO audit(ts,event,user_id,data,prev,hash) VALUES(?,?,?,?,?,?)",
                        (ts, "x", None, "{}", prev, h))
        prev = h
    assert db.prune_audit(365) == 2
    assert db.verify_audit()[0]


def test_global_lockout_for_unknown_faces(monkeypatch, tmp_path):
    monkeypatch.setenv("FACEID_HOME", str(tmp_path))
    from faceid.config import Settings
    from faceid.services.app import FaceIDService
    from faceid.session import SessionResult

    s = Settings()
    s.max_failed_attempts = 3
    svc = FaceIDService(s)
    for _ in range(3):
        out = svc.record_auth(SessionResult(False, "no_match"))
    assert svc.global_locked_for() > 0 and out.locked_for_s > 0
    ok, _ = svc.db.verify_audit()
    assert ok
