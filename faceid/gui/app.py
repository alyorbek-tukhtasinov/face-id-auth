"""FaceID Next — asosiy oyna."""

from __future__ import annotations

import datetime as dt
import json
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QImage
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..camera import list_cameras
from ..config import Settings, data_dir, models_dir
from ..i18n import set_language, t
from ..services.app import FaceIDService
from ..session import FrameReport, Mode, SessionResult
from .voice import Voice
from .widgets import StepDots, VideoView
from .worker import LoaderThread, SessionWorker

STYLE = """
* { font-family: 'Segoe UI', 'Inter', 'Noto Sans', sans-serif; color: #E8ECF4; }
QMainWindow, QWidget#page { background: #0F1420; }
QLabel#title { font-size: 30px; font-weight: 700; }
QLabel#subtitle { font-size: 15px; color: #9AA5B8; }
QLabel#instruction { font-size: 24px; font-weight: 600; }
QLabel#muted { color: #8D97AA; font-size: 12px; }
QLabel#big { font-size: 64px; }
QPushButton { background: #1C2433; border: 1px solid #2C3648; border-radius: 10px; padding: 12px 22px; font-size: 15px; }
QPushButton:hover { background: #253046; }
QPushButton:disabled { color: #5B657A; }
QPushButton#primary { background: #4F8CFF; border: none; font-weight: 600; }
QPushButton#primary:hover { background: #6A9DFF; }
QPushButton#danger { background: #3A1E24; border-color: #6B2B35; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #161D2A; border: 1px solid #2C3648; border-radius: 8px; padding: 8px; font-size: 14px; }
QCheckBox { font-size: 13px; }
QTabWidget::pane { border: 1px solid #2C3648; border-radius: 8px; }
QTabBar::tab { background: #161D2A; padding: 8px 16px; border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: #253046; }
QTableWidget { background: #121826; gridline-color: #232B3B; border: none; }
QHeaderView::section { background: #1A2232; padding: 6px; border: none; }
"""


def _fmt_ts(ts: float | None) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "—"


class MainWindow(QMainWindow):
    def __init__(self, source_path: str | None = None) -> None:
        super().__init__()
        self.settings = Settings.load()
        set_language(self.settings.language)
        self.service = FaceIDService(self.settings)
        self.engine = None
        self.worker: SessionWorker | None = None
        self.source_path = source_path
        self.voice = Voice(self.settings.language, self.settings.voice_enabled)
        self.pending_name = ""
        self.mode = Mode.AUTH
        self._last_instr = ""

        self.setWindowTitle(f"FaceID Next {__version__}")
        self.resize(1100, 760)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._build_home()
        self._build_enroll_form()
        self._build_camera()
        self._build_result()
        self._build_admin()
        self.stack.setCurrentWidget(self.home)

        self.loader = LoaderThread(self.settings)
        self.loader.progress.connect(self._on_load_progress)
        self.loader.loaded.connect(self._on_loaded)
        self.loader.failed.connect(self._on_load_failed)
        self.loader.start()

    # ================================================================ pages
    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        w.setObjectName("page")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(36, 28, 36, 28)
        lay.setSpacing(14)
        self.stack.addWidget(w)
        return w, lay

    def _build_home(self) -> None:
        self.home, lay = self._page()
        top = QHBoxLayout()
        top.addStretch()
        self.lang_box = QComboBox()
        for code, label in (("uz", "O'zbekcha"), ("ru", "Русский"), ("en", "English")):
            self.lang_box.addItem(label, code)
        self.lang_box.setCurrentIndex(["uz", "ru", "en"].index(self.settings.language))
        self.lang_box.currentIndexChanged.connect(self._change_language)
        top.addWidget(self.lang_box)
        lay.addLayout(top)
        lay.addStretch(2)
        logo = QLabel("◉")
        logo.setObjectName("big")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("color:#4F8CFF")
        lay.addWidget(logo)
        self.h_title = QLabel()
        self.h_title.setObjectName("title")
        self.h_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.h_sub = QLabel()
        self.h_sub.setObjectName("subtitle")
        self.h_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.h_title)
        lay.addWidget(self.h_sub)
        lay.addSpacing(24)
        self.btn_login = QPushButton()
        self.btn_login.setObjectName("primary")
        self.btn_enroll = QPushButton()
        self.btn_admin = QPushButton()
        for b in (self.btn_login, self.btn_enroll, self.btn_admin):
            b.setFixedWidth(320)
            b.setEnabled(False)
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(b)
            row.addStretch()
            lay.addLayout(row)
        self.btn_login.clicked.connect(self.start_login)
        self.btn_enroll.clicked.connect(self.open_enroll)
        self.btn_admin.clicked.connect(self.open_admin)
        lay.addStretch(3)
        self.h_status = QLabel()
        self.h_status.setObjectName("muted")
        self.h_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.h_status)

    def _build_enroll_form(self) -> None:
        self.enroll_form, lay = self._page()
        lay.addStretch()
        self.ef_title = QLabel()
        self.ef_title.setObjectName("title")
        lay.addWidget(self.ef_title)
        self.ef_name = QLineEdit()
        self.ef_name.setMaxLength(64)
        lay.addWidget(self.ef_name)
        self.ef_consent = QCheckBox()
        self.ef_consent.setStyleSheet("QCheckBox { font-size: 14px; }")
        lbl = QLabel()
        lbl.setWordWrap(True)
        self.ef_consent_text = lbl
        row = QHBoxLayout()
        row.addWidget(self.ef_consent, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(lbl, 1)
        lay.addLayout(row)
        self.ef_note = QLabel()
        self.ef_note.setObjectName("muted")
        lay.addWidget(self.ef_note)
        self.ef_err = QLabel()
        self.ef_err.setStyleSheet("color:#FF5C5C")
        lay.addWidget(self.ef_err)
        btns = QHBoxLayout()
        self.ef_back = QPushButton()
        self.ef_back.clicked.connect(self.go_home)
        self.ef_go = QPushButton()
        self.ef_go.setObjectName("primary")
        self.ef_go.clicked.connect(self._enroll_continue)
        btns.addWidget(self.ef_back)
        btns.addStretch()
        btns.addWidget(self.ef_go)
        lay.addLayout(btns)
        lay.addStretch()

    def _build_camera(self) -> None:
        self.cam_page, lay = self._page()
        self.instr = QLabel()
        self.instr.setObjectName("instruction")
        self.instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.instr)
        self.dots = StepDots()
        lay.addWidget(self.dots)
        self.view = VideoView()
        lay.addWidget(self.view, 1)
        bottom = QHBoxLayout()
        self.meters = QLabel()
        self.meters.setObjectName("muted")
        bottom.addWidget(self.meters)
        bottom.addStretch()
        self.cam_cancel = QPushButton()
        self.cam_cancel.clicked.connect(self.cancel_session)
        bottom.addWidget(self.cam_cancel)
        lay.addLayout(bottom)

    def _build_result(self) -> None:
        self.result_page, lay = self._page()
        lay.addStretch()
        self.r_icon = QLabel()
        self.r_icon.setObjectName("big")
        self.r_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.r_msg = QLabel()
        self.r_msg.setObjectName("title")
        self.r_msg.setWordWrap(True)
        self.r_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.r_det = QLabel()
        self.r_det.setObjectName("muted")
        self.r_det.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.r_det.setWordWrap(True)
        self.r_det.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.r_icon)
        lay.addWidget(self.r_msg)
        lay.addWidget(self.r_det)
        lay.addSpacing(20)
        row = QHBoxLayout()
        row.addStretch()
        self.r_retry = QPushButton()
        self.r_retry.setObjectName("primary")
        self.r_retry.clicked.connect(self._retry)
        self.r_home = QPushButton()
        self.r_home.clicked.connect(self.go_home)
        row.addWidget(self.r_home)
        row.addWidget(self.r_retry)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()

    def _build_admin(self) -> None:
        self.admin, lay = self._page()
        head = QHBoxLayout()
        self.a_title = QLabel()
        self.a_title.setObjectName("title")
        head.addWidget(self.a_title)
        head.addStretch()
        self.a_back = QPushButton()
        self.a_back.clicked.connect(self.go_home)
        head.addWidget(self.a_back)
        lay.addLayout(head)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # Foydalanuvchilar
        w = QWidget()
        v = QVBoxLayout(w)
        self.users_tbl = QTableWidget(0, 6)
        self.users_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.users_tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.users_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.users_tbl)
        row = QHBoxLayout()
        row.addStretch()
        self.u_del = QPushButton()
        self.u_del.setObjectName("danger")
        self.u_del.clicked.connect(self._delete_user)
        row.addWidget(self.u_del)
        v.addLayout(row)
        self.tabs.addTab(w, "")

        # Audit
        w = QWidget()
        v = QVBoxLayout(w)
        self.audit_status = QLabel()
        v.addWidget(self.audit_status)
        self.audit_tbl = QTableWidget(0, 4)
        self.audit_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.audit_tbl.horizontalHeader().setStretchLastSection(True)
        self.audit_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.audit_tbl.verticalHeader().setVisible(False)
        v.addWidget(self.audit_tbl)
        self.tabs.addTab(w, "")

        # Sozlamalar
        w = QWidget()
        f = QFormLayout(w)
        self.s_cam = QComboBox()
        self.s_voice = QCheckBox()
        self.s_mirror = QCheckBox()
        self.s_hwmirror = QCheckBox()
        self.s_thr = QDoubleSpinBox()
        self.s_thr.setRange(0.30, 0.80)
        self.s_thr.setSingleStep(0.01)
        self.s_pad = QDoubleSpinBox()
        self.s_pad.setRange(0.30, 0.99)
        self.s_pad.setSingleStep(0.01)
        self.s_ch = QSpinBox()
        self.s_ch.setRange(2, 5)
        self.s_block = QCheckBox()
        self.s_labels = [QLabel() for _ in range(8)]
        for lbl, wid in zip(self.s_labels, (self.s_cam, self.s_voice, self.s_mirror, self.s_hwmirror, self.s_thr,
                                            self.s_pad, self.s_ch, self.s_block), strict=True):
            f.addRow(lbl, wid)
        self.s_save = QPushButton()
        self.s_save.setObjectName("primary")
        self.s_save.clicked.connect(self._save_settings)
        f.addRow("", self.s_save)
        self.tabs.addTab(w, "")

        # Tizim
        w = QWidget()
        v = QVBoxLayout(w)
        self.sys_info = QLabel()
        self.sys_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.sys_info.setWordWrap(True)
        v.addWidget(self.sys_info)
        v.addStretch()
        self.wipe_btn = QPushButton()
        self.wipe_btn.setObjectName("danger")
        self.wipe_btn.clicked.connect(self._wipe)
        v.addWidget(self.wipe_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.tabs.addTab(w, "")
        self.retranslate()

    # ============================================================== i18n
    def retranslate(self) -> None:
        self.h_title.setText(t("app_title"))
        self.h_sub.setText(t("subtitle"))
        self.btn_login.setText(t("btn_login"))
        self.btn_enroll.setText(t("btn_enroll"))
        self.btn_admin.setText(t("btn_admin"))
        self.ef_title.setText(t("btn_enroll"))
        self.ef_name.setPlaceholderText(t("enroll_name"))
        self.ef_consent_text.setText(t("consent"))
        self.ef_back.setText(t("btn_back"))
        self.ef_go.setText(t("btn_continue"))
        self.cam_cancel.setText(t("btn_cancel"))
        self.r_retry.setText(t("btn_retry"))
        self.r_home.setText(t("btn_back"))
        self.a_title.setText(t("btn_admin"))
        self.a_back.setText(t("btn_back"))
        self.u_del.setText(t("btn_delete"))
        for i, k in enumerate(("tab_users", "tab_audit", "tab_settings", "tab_system")):
            self.tabs.setTabText(i, t(k))
        self.users_tbl.setHorizontalHeaderLabels(
            ["ID", t("col_name"), t("col_role"), t("col_created"), t("col_last"), t("col_templates")])
        self.audit_tbl.setHorizontalHeaderLabels([t("col_time"), t("col_event"), t("col_user"), t("col_details")])
        for lbl, k in zip(self.s_labels, ("set_camera", "set_voice", "set_mirror", "set_hw_mirror", "set_threshold",
                                          "set_pad", "set_challenges", "set_block_virtual"), strict=True):
            lbl.setText(t(k))
        self.s_save.setText(t("btn_save"))
        self.wipe_btn.setText(t("wipe_all"))
        if self.engine is None:
            self.h_status.setText(t("loading_models"))
        else:
            self._update_status()

    def _change_language(self) -> None:
        self.settings.language = self.lang_box.currentData()
        self.settings.save()
        set_language(self.settings.language)
        self.voice.close()
        self.voice = Voice(self.settings.language, self.settings.voice_enabled)
        self.retranslate()

    # ============================================================ loading
    def _on_load_progress(self, name: str, pct: int) -> None:
        self.h_status.setText(t("loading_models") if pct < 0 else t("downloading", name=name, pct=pct))

    def _on_loaded(self, engine) -> None:
        self.engine = engine
        for b in (self.btn_login, self.btn_enroll, self.btn_admin):
            b.setEnabled(True)
        self._update_status()

    def _on_load_failed(self, msg: str) -> None:
        self.h_status.setText("⚠ " + msg)
        self.h_status.setStyleSheet("color:#FF5C5C")

    def _update_status(self) -> None:
        n = len(self.service.db.users())
        key = "Windows DPAPI / OS keyring" if self.service.keystore.backend == "keyring" else "file key"
        self.h_status.setText(f"v{__version__} · {n} 👤 · AES-256-GCM ({key}) · offline")

    # ============================================================ flows
    def go_home(self) -> None:
        self._stop_worker()
        self._update_status() if self.engine else None
        self.stack.setCurrentWidget(self.home)

    def start_login(self) -> None:
        if not self.service.db.users():
            self._show_result(False, t("fail_no_users"), "")
            return
        locked = self.service.global_locked_for()
        if locked:
            self.mode = Mode.AUTH
            self._show_result(False, t("fail_locked", sec=locked), "")
            return
        self.mode = Mode.AUTH
        self._start_session()

    def open_enroll(self) -> None:
        if self.service.db.users() and not self._ask_admin():
            return
        self.ef_name.clear()
        self.ef_consent.setChecked(False)
        self.ef_err.clear()
        self.ef_note.setText("" if self.service.db.users() else t("first_enroll_admin"))
        self.stack.setCurrentWidget(self.enroll_form)
        self.ef_name.setFocus()

    def _enroll_continue(self) -> None:
        name = self.ef_name.text().strip()
        if not name:
            self.ef_err.setText(t("name_required"))
            return
        if self.service.db.user_by_name(name):
            self.ef_err.setText(t("name_taken"))
            return
        if not self.ef_consent.isChecked():
            self.ef_err.setText(t("consent_required"))
            return
        self.pending_name = name
        self.mode = Mode.ENROLL
        self._start_session()

    def _start_session(self) -> None:
        self._stop_worker()
        self.view.clear()
        self.view.mirror = self.settings.mirror_preview
        self.view.selfie_view = self.settings.mirror_preview != self.settings.camera_hw_mirrored
        self.instr.setText(t("q_no_face"))
        self.dots.set(0, 0)
        self._last_instr = ""
        self.stack.setCurrentWidget(self.cam_page)
        self.worker = SessionWorker(self.engine, self.settings, self.mode, self.service.gallery,
                                    source_path=self.source_path)
        self.worker.frame.connect(self._on_frame)
        self.worker.finished_result.connect(self._on_session_done)
        self.worker.error.connect(self._on_session_error)
        self.worker.status.connect(self._on_worker_status)
        self.worker.start()

    def _stop_worker(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(3000)
            self.worker = None

    def cancel_session(self) -> None:
        self.go_home()

    def _on_frame(self, img: QImage, rep: FrameReport) -> None:
        self.view.set_frame(img, rep)
        text = t(rep.instruction)
        self.instr.setText(text)
        if rep.steps and rep.step:
            self.dots.set(rep.step, rep.steps)
        q = f"{rep.quality.score:.0f}" if rep.quality else "—"
        pad = f"{rep.pad_score * 100:.0f}%" if rep.pad_score is not None else "…"
        self.meters.setText(f"{t('quality')}: {q}   ·   {t('liveness')}: {pad}")
        if rep.instruction != self._last_instr and not rep.instruction.startswith(("pos_hold", "q_")):
            self.voice.say(text)
        self._last_instr = rep.instruction

    def _on_session_error(self, key: str, detail: str) -> None:
        self._stop_worker()  # oqim to'liq tugaguncha kutamiz — aks holda Qt ilovani yiqitadi
        help_text = t("fail_camera_help") if key.startswith("fail_camera") else ""
        self._show_result(False, t(key), "\n\n".join(x for x in (help_text, detail) if x))

    def _on_worker_status(self, key: str) -> None:
        self.instr.setText(t(key))

    def _on_session_done(self, res: SessionResult) -> None:
        self._stop_worker()
        self.view.final = res.success
        self.view.update()
        if self.mode is Mode.ENROLL:
            self._finish_enroll(res)
        else:
            self._finish_auth(res)

    def _finish_auth(self, res: SessionResult) -> None:
        out = self.service.record_auth(res)
        det = f"score {out.score:.3f} · liveness {res.pad_score * 100:.0f}%"
        if out.success and out.user:
            msg = t("ok_welcome", name=out.user.name)
            self.voice.say(msg + "!")
            self._show_result(True, msg, det)
        elif out.locked_for_s:
            self._show_result(False, t("fail_locked", sec=out.locked_for_s), det)
        else:
            self._show_result(False, t("fail_" + out.reason), det)

    def _finish_enroll(self, res: SessionResult) -> None:
        if not res.success:
            extra = ""
            if res.reason == "already_enrolled" and res.user_id:
                u = self.service.db.user(res.user_id)
                extra = u.name if u else ""
            extra_audit = {k: v for k, v in res.details.items() if k in ("action", "step", "pad_mean", "consistency")}
            self.service.db.audit("enroll_failed", reason=res.reason, pad=round(res.pad_score, 3), **extra_audit)
            self._show_result(False, t("fail_" + res.reason), extra)
            return
        first = not self.service.db.users()
        try:
            self.service.complete_enrollment(self.pending_name, res)
        except ValueError as exc:
            self._show_result(False, t(str(exc)), "")
            return
        self._show_result(True, t("ok_enrolled"), self.pending_name)
        if first or not self.service.has_admin_password:
            QTimer.singleShot(300, self._setup_admin_password)

    def _show_result(self, ok: bool, msg: str, details: str) -> None:
        self.r_icon.setText("✓" if ok else "✕")
        self.r_icon.setStyleSheet(f"color: {'#2ECC71' if ok else '#FF5C5C'}")
        self.r_msg.setText(msg)
        self.r_det.setText(details)
        self.r_retry.setVisible(not ok)
        self.stack.setCurrentWidget(self.result_page)
        if not ok:
            self.voice.say(msg + "!")

    def _retry(self) -> None:
        if self.mode is Mode.ENROLL:
            self.stack.setCurrentWidget(self.enroll_form)
        else:
            self.start_login()

    # ============================================================ admin
    def _setup_admin_password(self) -> None:
        while True:
            pw, ok = QInputDialog.getText(self, t("admin_setup"), t("admin_pw_new"), QLineEdit.EchoMode.Password)
            if not ok:
                return
            pw2, ok = QInputDialog.getText(self, t("admin_setup"), t("admin_pw_repeat"), QLineEdit.EchoMode.Password)
            if not ok:
                return
            if pw != pw2:
                QMessageBox.warning(self, t("admin_setup"), t("admin_pw_mismatch"))
                continue
            try:
                self.service.set_admin_password(pw)
                return
            except ValueError:
                QMessageBox.warning(self, t("admin_setup"), t("admin_pw_new"))

    def _ask_admin(self) -> bool:
        if not self.service.has_admin_password:
            self._setup_admin_password()
            return self.service.has_admin_password
        locked = self.service.admin_locked_for()
        if locked:
            QMessageBox.warning(self, t("btn_admin"), t("fail_locked", sec=locked))
            return False
        pw, ok = QInputDialog.getText(self, t("btn_admin"), t("admin_pw"), QLineEdit.EchoMode.Password)
        if not ok:
            return False
        if self.service.check_admin_password(pw):
            return True
        QMessageBox.warning(self, t("btn_admin"), t("admin_pw_wrong"))
        return False

    def open_admin(self) -> None:
        if not self._ask_admin():
            return
        self._refresh_admin()
        self.stack.setCurrentWidget(self.admin)

    def _refresh_admin(self) -> None:
        users = self.service.db.users()
        self.users_tbl.setRowCount(len(users))
        for r, u in enumerate(users):
            for c, val in enumerate((str(u.id), u.name, u.role, _fmt_ts(u.created_at), _fmt_ts(u.last_login),
                                     str(u.templates))):
                self.users_tbl.setItem(r, c, QTableWidgetItem(val))
        names = {u.id: u.name for u in users}
        rows = self.service.db.audit_log(500)
        self.audit_tbl.setRowCount(len(rows))
        for r, row in enumerate(rows):
            d = json.loads(row["data"] or "{}")
            uid = row["user_id"]
            vals = (_fmt_ts(row["ts"]), row["event"], names.get(uid, str(uid) if uid else "—"),
                    ", ".join(f"{k}={v}" for k, v in d.items()))
            for c, val in enumerate(vals):
                self.audit_tbl.setItem(r, c, QTableWidgetItem(val))
        ok, bad = self.service.db.verify_audit()
        self.audit_status.setText(t("audit_ok") if ok else t("audit_broken", id=bad))
        self.audit_status.setStyleSheet(f"color: {'#2ECC71' if ok else '#FF5C5C'}; font-weight:600")

        self.s_cam.clear()
        for cam in list_cameras():
            self.s_cam.addItem(cam.label(), cam.index)
        if self.s_cam.count() == 0:
            self.s_cam.addItem(f"{self.settings.camera_index}: —", self.settings.camera_index)
        idx = self.s_cam.findData(self.settings.camera_index)
        self.s_cam.setCurrentIndex(max(idx, 0))
        self.s_voice.setChecked(self.settings.voice_enabled)
        self.s_mirror.setChecked(self.settings.mirror_preview)
        self.s_hwmirror.setChecked(self.settings.camera_hw_mirrored)
        self.s_thr.setValue(self.settings.match_threshold)
        self.s_pad.setValue(self.settings.passive_threshold)
        self.s_ch.setValue(self.settings.challenge_count)
        self.s_block.setChecked(self.settings.block_virtual_cameras)

        import onnxruntime as ort

        info = [
            f"FaceID Next {__version__} · Python {sys.version.split()[0]}",
            f"Data: {data_dir()}",
            f"Models: {models_dir()}",
            f"Key storage: {self.service.keystore.backend}",
            f"ONNX Runtime {ort.__version__}: {', '.join(ort.get_available_providers())}",
            "Detector: SCRFD-10G · Recognizer: ArcFace R50 (WebFace600K) · PAD: MiniFASNet V2 + V1SE · "
            "Landmarks: MediaPipe Face Landmarker",
        ]
        self.sys_info.setText("\n".join(info))

    def _delete_user(self) -> None:
        row = self.users_tbl.currentRow()
        if row < 0:
            return
        uid = int(self.users_tbl.item(row, 0).text())
        name = self.users_tbl.item(row, 1).text()
        if QMessageBox.question(self, t("btn_delete"), t("confirm_delete", name=name)) == QMessageBox.StandardButton.Yes:
            self.service.delete_user(uid)
            self._refresh_admin()

    def _wipe(self) -> None:
        if QMessageBox.question(self, t("wipe_all"), t("confirm_wipe")) == QMessageBox.StandardButton.Yes:
            self.service.wipe_all()
            self._refresh_admin()

    def _save_settings(self) -> None:
        s = self.settings
        s.camera_index = int(self.s_cam.currentData() or 0)
        s.voice_enabled = self.s_voice.isChecked()
        s.mirror_preview = self.s_mirror.isChecked()
        s.camera_hw_mirrored = self.s_hwmirror.isChecked()
        s.match_threshold = round(self.s_thr.value(), 3)
        s.passive_threshold = round(self.s_pad.value(), 3)
        s.challenge_count = self.s_ch.value()
        s.block_virtual_cameras = self.s_block.isChecked()
        s.save()
        self.voice.enabled = s.voice_enabled
        self.service.db.audit("settings_changed", threshold=s.match_threshold, pad=s.passive_threshold,
                              challenges=s.challenge_count, block_virtual=s.block_virtual_cameras)
        QMessageBox.information(self, t("tab_settings"), t("saved"))

    def closeEvent(self, ev) -> None:  # noqa: N802
        self._stop_worker()
        self.voice.close()
        if self.engine is not None:
            self.engine.close()
        super().closeEvent(ev)


def run(source_path: str | None = None) -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow(source_path)
    win.show()
    return app.exec()
