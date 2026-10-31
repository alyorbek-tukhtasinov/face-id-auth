"""FaceID Next — buyruq qatori.

    python -m faceid                 grafik ilova
    python -m faceid models          modellarni yuklab olish
    python -m faceid doctor          tizim diagnostikasi
    python -m faceid verify          GUIsiz tekshiruv (chiqish kodi 0 = muvaffaqiyat)
    python -m faceid users           foydalanuvchilar ro'yxati
    python -m faceid audit           audit jurnali va uning yaxlitligi
    python -m faceid evaluate ...    FMR/FNMR va APCER/BPCER o'lchash
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def _progress(name: str, done: int, total: int) -> None:
    pct = f"{done * 100 / total:5.1f}%" if total else f"{done / 1e6:.0f} MB"
    print(f"\r  {name}: {pct}", end="", flush=True)


def cmd_models(_a) -> int:
    from . import models

    print("Modellar papkasi:", models.models_dir())
    models.ensure_models(_progress)
    print("\nBarcha modellar joyida va SHA-256 tekshiruvidan o'tdi ✓")
    return 0


def cmd_doctor(_a) -> int:
    import numpy as np
    import onnxruntime as ort

    from . import __version__, models
    from .camera import list_cameras
    from .config import data_dir
    from .liveness.injection import is_virtual_camera
    from .services.app import FaceIDService

    print(f"FaceID Next {__version__} · Python {sys.version.split()[0]} · {sys.platform}")
    print("Ma'lumotlar:", data_dir())
    print("ONNX Runtime", ort.__version__, ort.get_available_providers())
    miss = models.missing_models(verify_hash=True)
    print("Modellar:", "OK ✓" if not miss else "YETISHMAYDI: " + ", ".join(miss))
    svc = FaceIDService()
    print("Kalit ombori:", svc.keystore.backend, "· foydalanuvchilar:", len(svc.db.users()))
    ok, bad = svc.db.verify_audit()
    print("Audit zanjiri:", "butun ✓" if ok else f"BUZILGAN (#{bad})")
    cams = list_cameras()
    print("Kameralar:")
    for c in cams:
        print("  ", c.label(), "  ⚠ VIRTUAL" if is_virtual_camera(c.name) else "")
    if not cams:
        print("   (topilmadi)")
    if not miss:
        from .engine import Engine

        eng = Engine()
        img = np.random.default_rng(0).integers(0, 255, (720, 1280, 3), dtype=np.uint8)
        eng.detector.detect(img)
        t = time.perf_counter()
        for _ in range(5):
            eng.detector.detect(img)
        det = (time.perf_counter() - t) / 5 * 1000
        al = np.zeros((112, 112, 3), np.uint8)
        eng.embedder.embed(al)
        t = time.perf_counter()
        for _ in range(3):
            eng.embedder.embed(al)
        emb = (time.perf_counter() - t) / 3 * 1000
        roi = np.array([500, 180, 780, 540], np.float32)
        eng.landmarker.process_roi(img, roi)
        t = time.perf_counter()
        for _ in range(5):
            eng.landmarker.process_roi(img, roi)
        lm = (time.perf_counter() - t) / 5 * 1000
        print(f"Tezlik: detektor {det:.0f} ms · landmarklar {lm:.0f} ms · embedding {emb:.0f} ms")
        print(f"Taxminiy kadr tezligi: ~{1000 / (det + lm + 10):.0f} FPS")
        eng.close()
    return 0 if not miss else 1


def cmd_users(a) -> int:
    from .services.app import FaceIDService

    svc = FaceIDService()
    if a.delete is not None:
        u = svc.db.user(a.delete)
        if not u:
            print("Topilmadi")
            return 1
        if input(f"{u.name} o'chirilsinmi? [y/N] ").strip().lower() not in ("y", "ha", "yes"):
            return 1
        svc.delete_user(u.id)
        print("O'chirildi")
        return 0
    for u in svc.db.users():
        print(f"{u.id:>3}  {u.name:<24} {u.role:<6} shablon={u.templates}  oxirgi kirish={u.last_login or '—'}")
    return 0


def cmd_audit(a) -> int:
    import datetime as dt

    from .services.app import FaceIDService

    svc = FaceIDService()
    for r in reversed(svc.db.audit_log(a.n)):
        ts = dt.datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{r['id']:>5} {ts} {r['event']:<18} user={r['user_id']} {r['data']}")
    ok, bad = svc.db.verify_audit()
    print("\nZanjir:", "butun ✓" if ok else f"BUZILGAN — #{bad} yozuv o'zgartirilgan!")
    return 0 if ok else 2


def cmd_verify(a) -> int:
    """GUIsiz kirish. Boshqa dasturlar bilan integratsiya uchun: natija JSON va chiqish kodi."""
    import cv2

    from .camera import LiveCamera, VideoFileSource, list_cameras
    from .config import Settings
    from .engine import Engine
    from .i18n import set_language, t
    from .liveness.injection import is_virtual_camera
    from .services.app import FaceIDService
    from .session import BiometricSession, Mode

    s = Settings.load()
    set_language(s.language)
    svc = FaceIDService(s)
    claimed = None
    if a.user:
        u = svc.db.user_by_name(a.user)
        if not u:
            print(json.dumps({"success": False, "reason": "unknown_user"}))
            return 1
        claimed = u.id
    if svc.global_locked_for():
        print(json.dumps({"success": False, "reason": "locked", "retry_after_s": svc.global_locked_for()}))
        return 1
    eng = Engine(s)
    if a.source:
        src = VideoFileSource(a.source)
    else:
        cams = list_cameras()
        dev = next((c for c in cams if c.index == s.camera_index), cams[0] if cams else None)
        if dev is None:
            print(json.dumps({"success": False, "reason": "no_camera"}))
            return 1
        if s.block_virtual_cameras and is_virtual_camera(dev.name, s.allowed_camera_names):
            print(json.dumps({"success": False, "reason": "inj_virtual_camera"}))
            return 1
        src = LiveCamera(dev, s.camera_width, s.camera_height)
    sess = BiometricSession(eng, Mode.AUTH, svc.gallery, s, claimed_user=claimed, camera_mirrored=s.camera_hw_mirrored)
    last = ""
    try:
        while sess.result is None:
            frame, ts = src.read()
            if frame is None:
                if a.source:
                    break
                continue
            rep = sess.process(frame, ts if a.source else None)
            if rep.instruction != last and not a.quiet:
                print("→", t(rep.instruction, name=""), file=sys.stderr)
                last = rep.instruction
            if a.preview:
                view = cv2.flip(frame, 1) if s.mirror_preview else frame
                cv2.putText(view, t(rep.instruction, name=""), (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.imshow("FaceID Next", view)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
    finally:
        src.release()
        if a.preview:
            cv2.destroyAllWindows()
        eng.close()
    res = sess.result
    if res is None:
        print(json.dumps({"success": False, "reason": "aborted"}))
        return 1
    out = svc.record_auth(res, claimed=claimed)
    print(json.dumps({"success": out.success, "reason": out.reason, "user": out.user.name if out.user and out.success else None,
                      "score": round(out.score, 4), "liveness": round(res.pad_score, 3)}, ensure_ascii=False))
    return 0 if out.success else 1


def cmd_evaluate(a) -> int:
    from pathlib import Path

    from .config import Settings
    from .engine import Engine
    from .evaluation import evaluate_pad_dirs, evaluate_pairs, folder_pairs, load_lfw_pairs

    s = Settings.load()
    eng = Engine(s)
    if a.pad_real and a.pad_attack:
        m = evaluate_pad_dirs(eng, Path(a.pad_real), Path(a.pad_attack), a.pad_threshold or s.passive_threshold)
        print(f"PAD (ISO/IEC 30107-3): APCER {m['APCER'] * 100:.2f}% · BPCER {m['BPCER'] * 100:.2f}% "
              f"· chegara {m['threshold']:.2f} · real={m['n_real']} hujum={m['n_attack']}")
    if a.root:
        root = Path(a.root)
        pairs = load_lfw_pairs(Path(a.pairs), root) if a.pairs else folder_pairs(root)
        print(f"{len(pairs)} juftlik baholanmoqda...")
        rep = evaluate_pairs(eng, pairs, s.match_threshold, lambda k, n: print(f"\r  {k}/{n}", end="", flush=True))
        print("\n" + rep.text())
    eng.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="faceid", description="FaceID Next — lokal yuz orqali autentifikatsiya")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("gui", help="grafik ilova (standart)")
    g.add_argument("--source", help="kamera o'rniga video fayl (test uchun)")
    sub.add_parser("models", help="modellarni yuklab olish va tekshirish")
    sub.add_parser("doctor", help="tizim diagnostikasi va tezlik o'lchovi")
    u = sub.add_parser("users", help="foydalanuvchilar")
    u.add_argument("--delete", type=int, metavar="ID")
    au = sub.add_parser("audit", help="audit jurnali")
    au.add_argument("-n", type=int, default=50)
    v = sub.add_parser("verify", help="GUIsiz tekshiruv; JSON chiqaradi, kod 0 = muvaffaqiyat")
    v.add_argument("--user", help="1:1 rejimi — faqat shu foydalanuvchini tekshirish")
    v.add_argument("--source", help="video fayl (test uchun)")
    v.add_argument("--preview", action="store_true", help="OpenCV oynasida ko'rsatish")
    v.add_argument("--quiet", action="store_true")
    e = sub.add_parser("evaluate", help="FMR/FNMR va APCER/BPCER o'lchash")
    e.add_argument("--root", help="rasmlar papkasi (har shaxs — alohida papka yoki LFW)")
    e.add_argument("--pairs", help="LFW pairs.txt (ixtiyoriy)")
    e.add_argument("--pad-real", help="haqiqiy yuz rasmlari papkasi")
    e.add_argument("--pad-attack", help="hujum (rasm/ekran) rasmlari papkasi")
    e.add_argument("--pad-threshold", type=float)
    a = ap.parse_args(argv)

    if a.cmd in (None, "gui"):
        from .gui.app import run

        return run(getattr(a, "source", None))
    return {"models": cmd_models, "doctor": cmd_doctor, "users": cmd_users, "audit": cmd_audit,
            "verify": cmd_verify, "evaluate": cmd_evaluate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
