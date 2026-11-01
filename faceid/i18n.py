"""Interfeys matnlari: o'zbek (lotin), rus, ingliz."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    # --- Joylashish va sifat ---
    "q_no_face": {"uz": "Yuzingizni kameraga qarating", "ru": "Посмотрите в камеру", "en": "Look at the camera"},
    "q_multiple_faces": {"uz": "Kadrda faqat bitta yuz bo'lishi kerak", "ru": "В кадре должно быть только одно лицо", "en": "Only one face may be in view"},
    "q_too_far": {"uz": "Yaqinroq keling", "ru": "Подойдите ближе", "en": "Move closer"},
    "q_too_close": {"uz": "Biroz uzoqlashing", "ru": "Отодвиньтесь немного", "en": "Move back a little"},
    "q_blurry": {"uz": "Qimirlamang — tasvir xira", "ru": "Не двигайтесь — изображение размыто", "en": "Hold still — image is blurry"},
    "q_too_dark": {"uz": "Juda qorong'i — yorug'roq joyga o'ting", "ru": "Слишком темно — нужно больше света", "en": "Too dark — find more light"},
    "q_too_bright": {"uz": "Juda yorug' — to'g'ridan tushayotgan nurdan qoching", "ru": "Слишком ярко — избегайте прямого света", "en": "Too bright — avoid direct light"},
    "q_low_contrast": {"uz": "Yoritish yetarli emas", "ru": "Недостаточный контраст", "en": "Low contrast lighting"},
    "q_uneven_light": {"uz": "Yuzingiz bir tomondan yoritilgan", "ru": "Лицо освещено неравномерно", "en": "Lighting is uneven"},
    "q_look_straight": {"uz": "To'g'ri kameraga qarang", "ru": "Смотрите прямо в камеру", "en": "Look straight at the camera"},
    "q_center_face": {"uz": "Yuzingizni ramka markaziga keltiring", "ru": "Поместите лицо в центр рамки", "en": "Center your face in the frame"},
    "q_low_quality": {"uz": "Tasvir sifati past", "ru": "Низкое качество изображения", "en": "Image quality is too low"},
    "q_neutral_face": {"uz": "Yuzingizni bo'shashtiring, to'g'ri qarang", "ru": "Расслабьте лицо, смотрите прямо", "en": "Relax your face, look straight"},
    "pos_move_closer": {"uz": "Yaqinroq keling", "ru": "Подойдите ближе", "en": "Move closer"},
    "pos_move_back": {"uz": "Biroz uzoqlashing", "ru": "Отодвиньтесь немного", "en": "Move back a little"},
    "pos_center": {"uz": "Yuzingizni ramka markaziga keltiring", "ru": "Поместите лицо в центр рамки", "en": "Center your face in the frame"},
    "pos_hold_still": {"uz": "Yaxshi, qimirlamang...", "ru": "Хорошо, не двигайтесь...", "en": "Good, hold still..."},
    # --- Challenge ---
    "ch_blink": {"uz": "Ko'zingizni qisib oching", "ru": "Моргните", "en": "Blink your eyes"},
    "ch_smile": {"uz": "Jilmaying", "ru": "Улыбнитесь", "en": "Smile"},
    "ch_open_mouth": {"uz": "Og'zingizni oching", "ru": "Откройте рот", "en": "Open your mouth"},
    "ch_turn_left": {"uz": "Boshingizni chapga buring", "ru": "Поверните голову влево", "en": "Turn your head left"},
    "ch_turn_right": {"uz": "Boshingizni o'ngga buring", "ru": "Поверните голову вправо", "en": "Turn your head right"},
    "ch_return_neutral": {"uz": "To'g'ri qarang", "ru": "Смотрите прямо", "en": "Look straight ahead"},
    "cap_look_straight": {"uz": "To'g'ri qarang — tekshirilmoqda", "ru": "Смотрите прямо — проверка", "en": "Look straight — verifying"},
    "en_front": {"uz": "To'g'ri kameraga qarang", "ru": "Смотрите прямо в камеру", "en": "Look straight at the camera"},
    "en_slight_left": {"uz": "Boshingizni biroz chapga buring", "ru": "Слегка поверните голову влево", "en": "Turn your head slightly left"},
    "en_slight_right": {"uz": "Boshingizni biroz o'ngga buring", "ru": "Слегка поверните голову вправо", "en": "Turn your head slightly right"},
    # --- Natijalar ---
    "ok_welcome": {"uz": "Xush kelibsiz, {name}!", "ru": "Добро пожаловать, {name}!", "en": "Welcome, {name}!"},
    "ok_enrolled": {"uz": "Yuz muvaffaqiyatli ro'yxatga olindi", "ru": "Лицо успешно зарегистрировано", "en": "Face enrolled successfully"},
    "fail_session_timeout": {"uz": "Vaqt tugadi. Qaytadan urinib ko'ring", "ru": "Время истекло. Попробуйте снова", "en": "Time is up. Please try again"},
    "fail_inj_frozen_stream": {"uz": "Kamera oqimi shubhali (muzlagan kadr)", "ru": "Подозрительный видеопоток (застывший кадр)", "en": "Suspicious stream (frozen frames)"},
    "fail_inj_synthetic_stream": {"uz": "Kamera oqimi shubhali (sun'iy video)", "ru": "Подозрительный видеопоток (синтетический)", "en": "Suspicious stream (synthetic video)"},
    "fail_inj_resolution_change": {"uz": "Kamera oqimi o'zgardi", "ru": "Видеопоток изменился", "en": "Camera stream changed"},
    "fail_inj_virtual_camera": {"uz": "Virtual kamera taqiqlangan", "ru": "Виртуальная камера запрещена", "en": "Virtual cameras are not allowed"},
    "fail_face_lost": {"uz": "Yuz kadrdan chiqib ketdi", "ru": "Лицо пропало из кадра", "en": "Face left the frame"},
    "fail_multiple_faces": {"uz": "Kadrda bir nechta yuz aniqlandi", "ru": "В кадре обнаружено несколько лиц", "en": "Multiple faces detected"},
    "fail_face_swap": {"uz": "Tekshiruv davomida yuz almashdi", "ru": "Лицо сменилось во время проверки", "en": "Face changed during the check"},
    "fail_challenge_timeout": {"uz": "Harakat vaqtida bajarilmadi", "ru": "Действие не выполнено вовремя", "en": "Action was not completed in time"},
    "fail_challenge_wrong": {"uz": "Noto'g'ri harakat bajarildi", "ru": "Выполнено неверное действие", "en": "Wrong action performed"},
    "fail_pad_insufficient": {"uz": "Hayotiylikni tasdiqlash uchun ma'lumot yetarli emas", "ru": "Недостаточно данных для проверки живости", "en": "Not enough data to confirm liveness"},
    "fail_pad_spoof": {"uz": "Soxta yuz aniqlandi (rasm/ekran)", "ru": "Обнаружена подделка (фото/экран)", "en": "Spoof detected (photo/screen)"},
    "fail_no_match": {"uz": "Yuz tanilmadi", "ru": "Лицо не распознано", "en": "Face not recognized"},
    "fail_ambiguous": {"uz": "Shaxsni aniq belgilab bo'lmadi", "ru": "Не удалось однозначно определить личность", "en": "Identity is ambiguous"},
    "fail_no_users": {"uz": "Hali hech kim ro'yxatdan o'tmagan", "ru": "Пока никто не зарегистрирован", "en": "No users enrolled yet"},
    "fail_enroll_inconsistent": {"uz": "Namunalar bir-biriga mos emas — qayta urinib ko'ring", "ru": "Образцы не согласованы — повторите", "en": "Samples are inconsistent — try again"},
    "fail_already_enrolled": {"uz": "Bu yuz allaqachon ro'yxatda bor", "ru": "Это лицо уже зарегистрировано", "en": "This face is already enrolled"},
    "fail_locked": {"uz": "Ko'p muvaffaqiyatsiz urinish. {sec} soniyadan keyin urinib ko'ring", "ru": "Слишком много попыток. Повторите через {sec} с", "en": "Too many attempts. Try again in {sec}s"},
    "cam_opening": {"uz": "Kamera ochilmoqda...", "ru": "Открываем камеру...", "en": "Opening camera..."},
    "cam_black": {"uz": "Kadr qop-qora — kamera pardasi (shutter) yopiq emasmi?", "ru": "Кадр чёрный — не закрыта ли шторка камеры?", "en": "Image is black — is the camera shutter closed?"},
    "fail_camera_no_frames": {"uz": "Kamera ochildi, lekin tasvir bermadi", "ru": "Камера открылась, но не передаёт изображение", "en": "The camera opened but sends no image"},
    "fail_camera_stopped": {"uz": "Kamera tasvir berishni to'xtatdi", "ru": "Камера перестала передавать изображение", "en": "The camera stopped sending images"},
    "fail_internal": {"uz": "Ichki xatolik", "ru": "Внутренняя ошибка", "en": "Internal error"},
    "fail_camera_help": {
        "uz": "1) Kamerani ishlatayotgan boshqa dasturlarni yoping (Zoom, Teams, Telegram, brauzer, DroidCam, Kamera ilovasi).\n"
              "2) Windows Sozlamalari → Maxfiylik va xavfsizlik → Kamera: \"Kameraga kirish\" va "
              "\"Ish stoli ilovalariga kameraga kirishga ruxsat berish\" yoqilgan bo'lsin.\n"
              "3) Noutbukdagi kamera pardasi (shutter) ochiq va klaviaturadagi kamera tugmasi o'chirilmagan bo'lsin.\n"
              "4) Boshqaruv paneli → Sozlamalar dan boshqa kamerani tanlab ko'ring.",
        "ru": "1) Закройте другие программы, использующие камеру (Zoom, Teams, Telegram, браузер, DroidCam).\n"
              "2) Параметры Windows → Конфиденциальность → Камера: разрешите доступ, в т.ч. классическим приложениям.\n"
              "3) Откройте шторку камеры и проверьте клавишу отключения камеры.\n"
              "4) Выберите другую камеру в Панели управления → Настройки.",
        "en": "1) Close other apps using the camera (Zoom, Teams, Telegram, browser, DroidCam).\n"
              "2) Windows Settings → Privacy & security → Camera: allow access, including for desktop apps.\n"
              "3) Open the camera shutter and check the camera kill key.\n"
              "4) Pick another camera in Admin panel → Settings.",
    },
    "fail_camera": {"uz": "Kamerani ochib bo'lmadi", "ru": "Не удалось открыть камеру", "en": "Could not open the camera"},
    "done": {"uz": "Tugadi", "ru": "Готово", "en": "Done"},
    # --- Interfeys ---
    "app_title": {"uz": "FaceID Next", "ru": "FaceID Next", "en": "FaceID Next"},
    "subtitle": {"uz": "Yuz orqali xavfsiz kirish", "ru": "Безопасный вход по лицу", "en": "Secure face sign-in"},
    "btn_login": {"uz": "Yuz orqali kirish", "ru": "Войти по лицу", "en": "Sign in with face"},
    "btn_enroll": {"uz": "Ro'yxatdan o'tish", "ru": "Регистрация", "en": "Enroll"},
    "btn_admin": {"uz": "Boshqaruv paneli", "ru": "Панель управления", "en": "Admin panel"},
    "btn_cancel": {"uz": "Bekor qilish", "ru": "Отмена", "en": "Cancel"},
    "btn_back": {"uz": "Orqaga", "ru": "Назад", "en": "Back"},
    "btn_retry": {"uz": "Qayta urinish", "ru": "Повторить", "en": "Try again"},
    "btn_delete": {"uz": "O'chirish", "ru": "Удалить", "en": "Delete"},
    "btn_save": {"uz": "Saqlash", "ru": "Сохранить", "en": "Save"},
    "btn_continue": {"uz": "Davom etish", "ru": "Продолжить", "en": "Continue"},
    "enroll_name": {"uz": "Ismingiz", "ru": "Ваше имя", "en": "Your name"},
    "consent": {
        "uz": "Yuz tasvirimdan biometrik shablon yaratilishiga va u ushbu kompyuterda shifrlangan holda saqlanishiga roziman. "
              "Rasmlar saqlanmaydi. Ma'lumotlarimni istalgan vaqtda o'chirishim mumkin.",
        "ru": "Я согласен(на) на создание биометрического шаблона по изображению лица и его зашифрованное хранение на этом "
              "компьютере. Фотографии не сохраняются. Данные можно удалить в любое время.",
        "en": "I consent to a biometric template being created from my face and stored encrypted on this computer. "
              "No photos are stored. I can delete my data at any time.",
    },
    "consent_required": {"uz": "Davom etish uchun rozilik bering", "ru": "Для продолжения дайте согласие", "en": "Consent is required to continue"},
    "name_required": {"uz": "Ismni kiriting", "ru": "Введите имя", "en": "Enter a name"},
    "name_taken": {"uz": "Bu ism band", "ru": "Это имя уже занято", "en": "This name is taken"},
    "first_enroll_admin": {"uz": "Birinchi ro'yxatdan o'tgan foydalanuvchi administrator bo'ladi.", "ru": "Первый пользователь станет администратором.", "en": "The first enrolled user becomes the administrator."},
    "admin_pw": {"uz": "Administrator paroli", "ru": "Пароль администратора", "en": "Administrator password"},
    "admin_pw_new": {"uz": "Yangi administrator paroli (kamida 8 belgi)", "ru": "Новый пароль администратора (мин. 8 символов)", "en": "New admin password (min. 8 chars)"},
    "admin_pw_repeat": {"uz": "Parolni takrorlang", "ru": "Повторите пароль", "en": "Repeat password"},
    "admin_pw_mismatch": {"uz": "Parollar mos emas", "ru": "Пароли не совпадают", "en": "Passwords do not match"},
    "admin_pw_wrong": {"uz": "Parol noto'g'ri", "ru": "Неверный пароль", "en": "Wrong password"},
    "admin_setup": {"uz": "Boshqaruv panelini himoyalash uchun parol o'rnating", "ru": "Установите пароль для панели управления", "en": "Set a password to protect the admin panel"},
    "tab_users": {"uz": "Foydalanuvchilar", "ru": "Пользователи", "en": "Users"},
    "tab_audit": {"uz": "Audit jurnali", "ru": "Журнал аудита", "en": "Audit log"},
    "tab_settings": {"uz": "Sozlamalar", "ru": "Настройки", "en": "Settings"},
    "tab_system": {"uz": "Tizim", "ru": "Система", "en": "System"},
    "col_name": {"uz": "Ism", "ru": "Имя", "en": "Name"},
    "col_role": {"uz": "Rol", "ru": "Роль", "en": "Role"},
    "col_created": {"uz": "Yaratilgan", "ru": "Создан", "en": "Created"},
    "col_last": {"uz": "Oxirgi kirish", "ru": "Последний вход", "en": "Last sign-in"},
    "col_templates": {"uz": "Shablonlar", "ru": "Шаблоны", "en": "Templates"},
    "col_time": {"uz": "Vaqt", "ru": "Время", "en": "Time"},
    "col_event": {"uz": "Hodisa", "ru": "Событие", "en": "Event"},
    "col_user": {"uz": "Foydalanuvchi", "ru": "Пользователь", "en": "User"},
    "col_details": {"uz": "Tafsilotlar", "ru": "Подробности", "en": "Details"},
    "confirm_delete": {"uz": "{name} ning barcha biometrik ma'lumotlari butunlay o'chirilsinmi?", "ru": "Удалить все биометрические данные {name}?", "en": "Permanently delete all biometric data of {name}?"},
    "audit_ok": {"uz": "Audit zanjiri butun ✓", "ru": "Цепочка аудита цела ✓", "en": "Audit chain intact ✓"},
    "audit_broken": {"uz": "DIQQAT: audit jurnali #{id} yozuvda o'zgartirilgan!", "ru": "ВНИМАНИЕ: журнал изменён на записи #{id}!", "en": "WARNING: audit log tampered at entry #{id}!"},
    "set_language": {"uz": "Til", "ru": "Язык", "en": "Language"},
    "set_camera": {"uz": "Kamera", "ru": "Камера", "en": "Camera"},
    "set_voice": {"uz": "Ovozli ko'rsatmalar", "ru": "Голосовые подсказки", "en": "Voice prompts"},
    "set_mirror": {"uz": "Tasvirni ko'zgu kabi ko'rsatish", "ru": "Зеркальное отображение", "en": "Mirror preview"},
    "set_hw_mirror": {"uz": "Kamera tasvirni o'zi ko'zgulaydi", "ru": "Камера сама зеркалит изображение", "en": "Camera hardware mirrors image"},
    "set_threshold": {"uz": "Tanib olish chegarasi (yuqori — xavfsizroq)", "ru": "Порог распознавания (выше — строже)", "en": "Match threshold (higher — stricter)"},
    "set_pad": {"uz": "Hayotiylik chegarasi", "ru": "Порог живости", "en": "Liveness threshold"},
    "set_challenges": {"uz": "Challenge soni", "ru": "Количество действий", "en": "Number of challenges"},
    "set_block_virtual": {"uz": "Virtual kameralarni bloklash", "ru": "Блокировать виртуальные камеры", "en": "Block virtual cameras"},
    "saved": {"uz": "Saqlandi", "ru": "Сохранено", "en": "Saved"},
    "loading_models": {"uz": "Neyron tarmoqlar yuklanmoqda...", "ru": "Загрузка нейросетей...", "en": "Loading neural networks..."},
    "downloading": {"uz": "Modellar yuklab olinmoqda: {name} {pct}%", "ru": "Скачивание моделей: {name} {pct}%", "en": "Downloading models: {name} {pct}%"},
    "step": {"uz": "{i}/{n}-qadam", "ru": "Шаг {i}/{n}", "en": "Step {i}/{n}"},
    "liveness": {"uz": "Hayotiylik", "ru": "Живость", "en": "Liveness"},
    "quality": {"uz": "Sifat", "ru": "Качество", "en": "Quality"},
    "wipe_all": {"uz": "Barcha biometrik ma'lumotlarni o'chirish", "ru": "Удалить все биометрические данные", "en": "Delete all biometric data"},
    "confirm_wipe": {"uz": "Barcha foydalanuvchilar o'chiriladi. Davom etasizmi?", "ru": "Все пользователи будут удалены. Продолжить?", "en": "All users will be deleted. Continue?"},
}

_lang = "uz"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in ("uz", "ru", "en") else "uz"


def language() -> str:
    return _lang


def t(key: str, **kw) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    s = entry.get(_lang) or entry["en"]
    try:
        return s.format(**kw) if kw else s
    except (KeyError, IndexError):
        return s
