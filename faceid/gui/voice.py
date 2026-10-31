"""Ovozli ko'rsatmalar — alohida oqimda, interfeysni bloklamaydi."""

from __future__ import annotations

import queue
import threading
import time

_VOICE_HINTS = {
    "uz": ("uzbek", "uz-", "uz_"),
    "ru": ("russian", "irina", "pavel", "ru-", "ru_"),
    "en": ("english", "zira", "david", "en-", "en_"),
}


class Voice:
    def __init__(self, lang: str = "uz", enabled: bool = True) -> None:
        self.lang = lang
        self.enabled = enabled
        self._q: queue.Queue[str | None] = queue.Queue()
        self._last_text = ""
        self._last_t = 0.0
        self._thread = threading.Thread(target=self._loop, name="voice", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
        except Exception:  # noqa: BLE001 — TTS yo'q bo'lsa jim ishlaymiz
            return
        voice_ok = self._pick_voice(engine)
        engine.setProperty("rate", 165)
        while True:
            text = self._q.get()
            if text is None:
                break
            while not self._q.empty():  # faqat eng so'nggi ko'rsatma
                nxt = self._q.get_nowait()
                if nxt is None:
                    return
                text = nxt
            if not voice_ok:
                continue
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception:  # noqa: BLE001
                pass

    def _pick_voice(self, engine) -> bool:
        try:
            voices = engine.getProperty("voices") or []
        except Exception:  # noqa: BLE001
            return False
        hints = _VOICE_HINTS.get(self.lang, ())
        for v in voices:
            blob = f"{v.name} {v.id} {getattr(v, 'languages', '')}".lower()
            if any(h in blob for h in hints):
                engine.setProperty("voice", v.id)
                return True
        # Tanlangan til uchun ovoz yo'q — noto'g'ri talaffuzdan ko'ra jim turgan yaxshi
        return False

    def say(self, text: str, min_gap: float = 2.5) -> None:
        if not self.enabled or not text:
            return
        now = time.monotonic()
        if text == self._last_text and now - self._last_t < min_gap * 2:
            return
        if now - self._last_t < min_gap and text != self._last_text and not text.endswith("!"):
            return
        self._last_text, self._last_t = text, now
        self._q.put(text)

    def close(self) -> None:
        self._q.put(None)
