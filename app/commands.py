"""CLI command handlers for absen, status, dry-run, and doctor."""

import json
import os
import subprocess

from app.config import settings
from app.models.attendance import AttendanceService
from app.models.holiday import Holiday, HolidayService
from app.utils.log import log
from app.utils.net import network_guard, with_retry
from app.utils.whatsapp import log_notify, notify
from app.utils.time import date_str, now_wib, today_str

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
TASK_NAME = "AutoAbsenMaganghub"
REMINDER_TASK_NAME = "AutoAbsenMaganghubReminder"


def should_skip() -> bool:
    """Return True if today is listed in HARI_LIBUR."""
    today_name = HARI[now_wib().weekday()]
    for d in settings.hari_libur.split(","):
        if d.strip().casefold() == today_name.casefold():
            return True
    return False


def invalid_days() -> list[str]:
    """Return HARI_LIBUR entries that match no known day name."""
    known = {d.casefold() for d in HARI}
    bad = []
    for d in settings.hari_libur.split(","):
        name = d.strip()
        if name and name.casefold() not in known:
            bad.append(name)
    return bad


def invalid_reminder_times() -> list[str]:
    """Return REMINDER_TIMES entries that are not valid HH:MM."""
    bad = []
    for raw in settings.reminder_times.split(","):
        value = raw.strip()
        if not value:
            continue
        parts = value.split(":")
        valid = len(parts) == 2 and all(p.isdigit() for p in parts)
        if valid:
            hour, minute = int(parts[0]), int(parts[1])
            valid = 0 <= hour <= 23 and 0 <= minute <= 59
        if not valid:
            bad.append(value)
    return bad


def holiday_service(svc: AttendanceService | None = None) -> HolidayService | None:
    """Return a holiday service, or None if the holiday check is disabled."""
    if not settings.libur_nasional:
        return None
    user = getattr(svc, "_username", None) or settings.siapkerja_username
    pwd = getattr(svc, "_password", None) or settings.siapkerja_password
    client = getattr(svc, "_client", None)
    if not client and (not user or not pwd):
        return None
    return HolidayService(username=user, password=pwd, client=client)


def find_holiday(holidays: HolidayService | None, date: str) -> Holiday | None:
    """Return the holiday on a date, or None. Never raises.

    A holiday calendar is a convenience, not a requirement, so a failure
    to reach the API is logged and attendance still proceeds.

    Args:
        holidays: Holiday service, or None when the check is disabled.
        date: Date in YYYY-MM-DD format.
    """
    if holidays is None:
        return None
    try:
        return holidays.find(date)
    except Exception as e:
        log(f"[WARN] Gagal membaca daftar libur, absen tetap dilanjutkan: {e}")
        return None


def skip_reason(svc: AttendanceService | None = None) -> str | None:
    """Return why today is skipped, or None when today is a workday."""
    if should_skip():
        return "Hari ini libur"
    try:
        hs = holiday_service(svc)
    except TypeError:
        hs = holiday_service()
    holiday = find_holiday(hs, today_str())
    if holiday:
        return f"{holiday.date} hari libur: {holiday.name}"
    return None


def validate_env(svc: AttendanceService | None = None) -> bool:
    """Return True if required credentials and notes are set, else log error."""
    missing = []
    user = getattr(svc, "_username", None) or settings.siapkerja_username
    pwd = getattr(svc, "_password", None) or settings.siapkerja_password
    act = getattr(svc, "_activity_log", None) or settings.activity_log
    les = getattr(svc, "_lesson_learned", None) or settings.lesson_learned
    obs = getattr(svc, "_obstacles", None) or settings.obstacles

    if not user:
        missing.append("SIAPKERJA_USERNAME")
    if not pwd:
        missing.append("SIAPKERJA_PASSWORD")
    if not act:
        missing.append("ACTIVITY_LOG")
    if not les:
        missing.append("LESSON_LEARNED")
    if not obs:
        missing.append("OBSTACLES")

    if missing:
        log(f"[FAIL] Variabel/data berikut wajib diisi: {', '.join(missing)}")
        return False
    return True


@network_guard
def cmd_absen(svc: AttendanceService) -> int:
    """Send attendance for today. Return 0 on success, 1 on failure."""
    if not validate_env(svc):
        notify("[FAIL] Konfigurasi tidak lengkap. Cek absen.log untuk detail.")
        return 1
    unknown = invalid_days()
    if unknown:
        log_notify(f"[FAIL] Nama hari tidak dikenal di HARI_LIBUR: {', '.join(unknown)}")
        return 1
    reason = skip_reason(svc)
    if reason:
        log(f"[SKIP] {reason}. Absen dilewati.")
        return 0
    if hasattr(svc, "get_log"):
        try:
            entry = svc.get_log(today_str())
            if entry:
                log_notify(f"[OK] Sudah absen hari ini ({today_str()}). Absen otomatis dilewati.")
                return 0
        except Exception as e:
            log(f"[WARN] Gagal membaca log absen hari ini, tetap mencoba absen: {e}")
    try:
        with_retry("Absen", lambda: svc.clock_in(today_str()))
    except Exception as e:
        if getattr(e, "status_code", None) == 409:
            log_notify("[OK] Sudah absen hari ini.")
            return 0
        log_notify(f"[FAIL] {e}")
        return 1
    log_notify(f"[OK] Absen {today_str()} berhasil terkirim.")
    return 0


@network_guard
def cmd_remind(svc: AttendanceService) -> int:
    """Send a WhatsApp reminder if today's attendance is still missing.

    Returns 0 on success, 1 on failure.
    """
    reason = skip_reason(svc)
    if reason:
        log(f"[SKIP] {reason}. Pengingat dilewati.")
        return 0
    entry = svc.get_log(today_str())
    if entry:
        log(f"[OK] Sudah absen pada {today_str()}. Pengingat tidak dikirim.")
        return 0
    log_notify(
        f"[INGAT] Belum absen MagangHub untuk {today_str()} "
        f"(pukul {now_wib().strftime('%H:%M')} WIB). Segera kirim absen hari ini."
    )
    return 0


def cmd_dry_run() -> int:
    """Show the payload absen would send, without network. Return exit code."""
    if not validate_env():
        return 1
    payload = AttendanceService.attendance_payload(today_str())
    log(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


@network_guard
def cmd_status(svc: AttendanceService, days: int = 1) -> int:
    """Show attendance status. Return 0 on success, 1 on failure.

    Args:
        svc: Authenticated attendance service.
        days: How many days back to show. 1 means detailed today view.
    """
    try:
        holidays = holiday_service(svc)
    except TypeError:
        holidays = holiday_service()

    if days == 1:
        entry = svc.get_log(today_str())
        if not entry:
            holiday = find_holiday(holidays, today_str())
            if holiday:
                log(f"{today_str()} hari libur: {holiday.name}")
                return 0
            log(f"Belum ada absen pada {today_str()}")
            return 0
        log(f"Status: {entry.date}")
        log(f"  Aktivitas:  {entry.activity_log or 'tidak tercatat'}")
        log(f"  Pelajaran:  {entry.lesson_learned or 'tidak tercatat'}")
        log(f"  Kendala:    {entry.obstacles or 'tidak tercatat'}")
        return 0
    for ago in range(days):
        date = date_str(ago)
        entry = svc.get_log(date)
        if entry:
            log(f"[OK] {date}  Hadir")
            continue
        holiday = find_holiday(holidays, date)
        if holiday:
            log(f"[OK] {date}  Libur: {holiday.name}")
        else:
            log(f"[OK] {date}  Tidak Hadir")
    return 0


def cmd_doctor() -> int:
    """Run setup self-checks. Return 0 if all pass, 1 otherwise."""
    failed = 0

    if validate_env():
        log("[OK] Variabel wajib lengkap.")
    else:
        failed += 1

    unknown = invalid_days()
    if not unknown:
        log("[OK] Nama hari di HARI_LIBUR valid.")
    else:
        log(f"[FAIL] Nama hari tidak dikenal: {', '.join(unknown)}")
        failed += 1

    bad_times = invalid_reminder_times()
    if not bad_times:
        log("[OK] Jam pengingat di REMINDER_TIMES valid.")
    else:
        log(f"[FAIL] Jam pengingat tidak valid: {', '.join(bad_times)}")
        failed += 1

    try:
        svc = AttendanceService()
        with_retry("Login", svc.login)
        log("[OK] Login berhasil.")
    except Exception as e:
        log(f"[FAIL] Login gagal: {e}")
        failed += 1

    holidays = holiday_service()
    if holidays is None:
        log("[SKIP] Cek libur nasional dinonaktifkan (LIBUR_NASIONAL=false).")
    else:
        try:
            log(f"[OK] Daftar libur terbaca: {len(holidays.list_holidays())} entri.")
        except Exception as e:
            log(f"[WARN] Daftar libur tidak terbaca, absen tetap berjalan: {e}")

    if settings.twilio_account_sid and settings.twilio_auth_token and settings.whatsapp_to:
        notify("Notifikasi WhatsApp aktif. (Pesan tes dari doctor.)")
        log("[OK] Pesan tes WhatsApp terkirim, cek WhatsApp Anda.")
    else:
        log("[SKIP] Notifikasi WhatsApp Twilio belum dikonfigurasi.")

    if os.name == "nt":
        try:
            r = subprocess.run(
                ["schtasks", "/query", "/tn", TASK_NAME],
                capture_output=True,
            )
            if r.returncode == 0:
                log("[OK] Tugas scheduler terdaftar.")
            else:
                log(f"[FAIL] Tugas scheduler '{TASK_NAME}' tidak ditemukan.")
                failed += 1
        except OSError as e:
            log(f"[FAIL] Cek scheduler gagal: {e}")
            failed += 1

        if settings.reminder_times.strip() and not invalid_reminder_times():
            try:
                r = subprocess.run(
                    ["schtasks", "/query", "/tn", REMINDER_TASK_NAME],
                    capture_output=True,
                )
                if r.returncode == 0:
                    log("[OK] Tugas pengingat terdaftar.")
                else:
                    log(f"[FAIL] Tugas pengingat '{REMINDER_TASK_NAME}' tidak ditemukan.")
                    failed += 1
            except OSError as e:
                log(f"[FAIL] Cek tugas pengingat gagal: {e}")
                failed += 1
    else:
        log("[SKIP] Cek scheduler hanya di Windows.")

    if failed:
        log(f"[FAIL] Doctor: {failed} pemeriksaan gagal.")
        return 1
    log("[OK] Doctor: semua pemeriksaan lolos.")
    return 0
