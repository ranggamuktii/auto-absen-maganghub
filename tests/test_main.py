"""Tests for attendance CLI logic. No network access."""

import re
from pathlib import Path

import requests

import app.commands as commands
import app.utils.net as netmod
from app.api.client import ApiError
from app.commands import cmd_dry_run, cmd_status, find_holiday, holiday_service, invalid_days, invalid_reminder_times, should_skip, validate_env
from app.models.attendance import AttendanceService
from app.models.attendance import DailyLog
from app.models.holiday import Holiday, HolidayService
from app.utils.net import net_msg, retryable, with_retry
from app.utils.time import date_str, now_wib


def testretryable_network_errors():
    assert retryable(requests.exceptions.ConnectionError("putus"))
    assert retryable(requests.exceptions.Timeout("lambat"))


def testretryable_server_errors():
    assert retryable(ApiError(500, "salah server"))
    assert retryable(ApiError(503, "sibuk"))


def test_not_retryable_errors():
    assert not retryable(ApiError(409, "sudah absen"))
    assert not retryable(ApiError(401, "token salah"))
    assert not retryable(ValueError("lainnya"))


def testwith_retry_succeeds_after_flaky_attempts(monkeypatch):
    monkeypatch.setattr(netmod, "RETRY_DELAY", 0)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise requests.exceptions.ConnectionError("blip")
        return "ok"

    assert with_retry("Tes", flaky) == "ok"
    assert len(calls) == 3


def testwith_retry_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(netmod, "RETRY_DELAY", 0)
    calls = []

    def always_fail():
        calls.append(1)
        raise requests.exceptions.Timeout("mati")

    try:
        with_retry("Tes", always_fail)
        raise AssertionError("seharusnya melempar")
    except requests.exceptions.Timeout:
        pass
    assert len(calls) == netmod.MAX_ATTEMPTS


def testwith_retry_skips_retry_for_final_errors(monkeypatch):
    monkeypatch.setattr(netmod, "RETRY_DELAY", 0)
    calls = []

    def fail_409():
        calls.append(1)
        raise ApiError(409, "sudah absen")

    try:
        with_retry("Tes", fail_409)
        raise AssertionError("seharusnya melempar")
    except ApiError:
        pass
    assert len(calls) == 1


def testnet_msg():
    assert net_msg(requests.exceptions.Timeout("lambat")) == "[FAIL] Koneksi timeout."
    assert net_msg(requests.exceptions.ConnectionError("putus")) == (
        "[FAIL] Gagal terhubung ke server. Cek koneksi internet."
    )


def testshould_skip_today(monkeypatch):
    today_name = commands.HARI[now_wib().weekday()]
    monkeypatch.setattr(commands.settings, "hari_libur", today_name)
    assert should_skip() is True


def testshould_skip_case_insensitive(monkeypatch):
    today_name = commands.HARI[now_wib().weekday()]
    monkeypatch.setattr(commands.settings, "hari_libur", today_name.lower())
    assert should_skip() is True
    monkeypatch.setattr(commands.settings, "hari_libur", today_name.upper())
    assert should_skip() is True


def test_should_not_skip_other_day(monkeypatch):
    monkeypatch.setattr(commands.settings, "hari_libur", "TidakAdaHari")
    assert should_skip() is False


def _fill_env(monkeypatch, **overrides):
    values = {
        "siapkerja_username": "user",
        "siapkerja_password": "sandi",
        "activity_log": "aktivitas",
        "lesson_learned": "pelajaran",
        "obstacles": "kendala",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setattr(commands.settings, key, value)


def testvalidate_env_complete(monkeypatch, capsys):
    _fill_env(monkeypatch)
    assert validate_env() is True


def testvalidate_env_missing(monkeypatch, capsys):
    _fill_env(monkeypatch, obstacles="")
    assert validate_env() is False
    assert "OBSTACLES" in capsys.readouterr().out


def test_daily_log_parsing():
    log_entry = DailyLog({
        "id": 1,
        "date": "2026-09-21",
        "clock_in": "16:00",
        "activity_log": "Magang hari ini",
        "lesson_learned": "Belajar hal baru",
        "obstacles": "Tidak ada",
    })
    assert log_entry.id == 1
    assert log_entry.date == "2026-09-21"
    assert log_entry.clock_in == "16:00"
    assert log_entry.activity_log == "Magang hari ini"
    assert log_entry.lesson_learned == "Belajar hal baru"
    assert log_entry.obstacles == "Tidak ada"


def test_daily_log_missing_optional_fields():
    log_entry = DailyLog({"id": 2, "date": "2026-09-21"})
    assert log_entry.clock_in is None
    assert log_entry.activity_log is None
    assert log_entry.lesson_learned is None
    assert log_entry.obstacles is None


def test_log_writes_to_console_and_file(tmp_path, monkeypatch, capsys):
    import app.utils.log as logmod

    monkeypatch.setattr(logmod, "LOG_FILE", tmp_path / "test.log")
    logmod.log("[OK] Tes tulis")
    assert "[OK] Tes tulis" in capsys.readouterr().out
    content = (tmp_path / "test.log").read_text(encoding="utf-8")
    assert "[OK] Tes tulis" in content
    assert re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content)


def test_log_never_raises(monkeypatch, capsys):
    import app.utils.log as logmod

    monkeypatch.setattr(logmod, "LOG_FILE", Path("/jalur-tidak-ada-xyz/test.log"))
    logmod.log("[OK] Tes aman")
    assert "[OK] Tes aman" in capsys.readouterr().out


def test_invalid_days_empty(monkeypatch):
    monkeypatch.setattr(commands.settings, "hari_libur", "")
    assert invalid_days() == []


def test_invalid_days_valid(monkeypatch):
    monkeypatch.setattr(commands.settings, "hari_libur", "Sabtu,minggu")
    assert invalid_days() == []


def test_invalid_days_typo(monkeypatch):
    monkeypatch.setattr(commands.settings, "hari_libur", "Sabtu,Saptu,Foo")
    assert invalid_days() == ["Saptu", "Foo"]


def test_attendance_payload_shape():
    payload = AttendanceService.attendance_payload("2026-09-21")
    assert payload["date"] == "2026-09-21"
    assert payload["status"] == "PRESENT"
    assert set(payload) == {
        "date",
        "status",
        "latitude",
        "longitude",
        "location",
        "activity_log",
        "lesson_learned",
        "obstacles",
    }


def test_date_str_format():
    assert re.match(r"\d{4}-\d{2}-\d{2}", date_str(3))
    assert date_str(0) == date_str()


def test_cmd_dry_run_success(monkeypatch, capsys):
    _fill_env(monkeypatch)
    assert cmd_dry_run() == 0
    assert "PRESENT" in capsys.readouterr().out


def test_cmd_dry_run_missing_env(monkeypatch, capsys):
    _fill_env(monkeypatch, obstacles="")
    assert cmd_dry_run() == 1


class FakeService:
    """Stub attendance service backed by a dict, no network."""

    def __init__(self, entries):
        self.entries = entries

    def get_log(self, date):
        return self.entries.get(date)


def test_status_single_day_detailed(capsys):
    entry = DailyLog({
        "id": 1,
        "date": date_str(0),
        "clock_in": "16:00",
        "activity_log": "Magang",
        "lesson_learned": "Belajar",
        "obstacles": "Tidak ada",
    })
    assert cmd_status(FakeService({date_str(0): entry})) == 0
    out = capsys.readouterr().out
    assert "Pelajaran:  Belajar" in out
    assert "Kendala:    Tidak ada" in out


def test_status_single_day_missing(capsys):
    assert cmd_status(FakeService({})) == 0
    assert "Belum ada absen" in capsys.readouterr().out


def test_status_empty_fields_explained(capsys):
    entry = DailyLog({"id": 1, "date": date_str(0)})
    assert cmd_status(FakeService({date_str(0): entry})) == 0
    out = capsys.readouterr().out
    assert "tidak tercatat" in out
    assert "  -" not in out


def test_get_log_matches_requested_date():
    svc = AttendanceService()

    class FakeApiClient:
        def get(self, path, params=None):
            return {"data": [
                {"id": 9, "date": "2026-09-21"},
                {"id": 8, "date": "2026-09-18"},
            ]}

    svc._client = FakeApiClient()
    assert svc.get_log("2026-09-18").id == 8
    assert svc.get_log("2026-09-20") is None


def test_get_log_searches_next_pages():
    svc = AttendanceService()
    calls = []

    class PagedApiClient:
        def get(self, path, params=None):
            calls.append((params or {}).get("page", 1))
            if (params or {}).get("page", 1) == 1:
                return {"data": [{"id": 9, "date": "2026-09-21"}], "total": 3}
            if (params or {}).get("page") == 2:
                return {"data": [{"id": 8, "date": "2026-09-18"}], "total": 3}
            return {"data": [], "total": 3}

    svc._client = PagedApiClient()
    assert svc.get_log("2026-09-18").id == 8
    assert calls == [1, 2]


def test_get_log_single_page_short_circuits():
    svc = AttendanceService()
    calls = []

    class SinglePageApiClient:
        def get(self, path, params=None):
            calls.append((params or {}).get("page", 1))
            return {"data": [{"id": 9, "date": "2026-09-21"}], "total": 1}

    svc._client = SinglePageApiClient()
    assert svc.get_log("2026-09-20") is None
    assert calls == [1]


def test_status_history_readable(capsys):
    svc = FakeService({
        date_str(0): DailyLog({"id": 1, "date": date_str(0), "clock_in": "16:00"}),
        date_str(2): DailyLog({"id": 2, "date": date_str(2)}),
    })
    assert cmd_status(svc, days=3) == 0
    out = capsys.readouterr().out
    assert f"[OK] {date_str(0)}  Hadir" in out
    assert f"[OK] {date_str(1)}  Tidak Hadir" in out
    assert f"[OK] {date_str(2)}  Hadir" in out
    assert "tercatat" not in out


def _national_holiday(date, name="Proklamasi Kemerdekaan"):
    return {
        "id": 1,
        "date": date,
        "name": name,
        "type": "NATIONAL",
        "scope": "NATIONAL",
        "province_code": None,
        "regency_code": None,
    }


def _provincial_holiday(date, name="Cuti Bersama"):
    return {
        "id": 2,
        "date": date,
        "name": name,
        "type": "REGIONAL",
        "scope": "PROVINCE",
        "province_code": "96",
        "regency_code": None,
    }


def test_holiday_parsing():
    h = Holiday(_national_holiday("2026-08-17"))
    assert h.date == "2026-08-17"
    assert h.name == "Proklamasi Kemerdekaan"
    assert h.is_national is True


def test_holiday_missing_optional_fields():
    h = Holiday({"date": "2026-12-25"})
    assert h.name == ""
    assert h.scope == ""
    assert h.is_national is False


def test_provincial_holiday_is_not_national():
    h = Holiday(_provincial_holiday("2026-08-24"))
    assert h.is_national is False


def test_holiday_service_finds_date():
    svc = HolidayService()

    class FakeApiClient:
        def get(self, path, params=None):
            return {"data": [
                _national_holiday("2026-08-25", "Maulid Nabi"),
                _national_holiday("2026-12-25"),
            ], "total": 2}

    svc._client = FakeApiClient()
    assert svc.find("2026-08-25").name == "Maulid Nabi"
    assert svc.find("2026-12-25") is not None
    assert svc.find("2026-10-01") is None


def test_holiday_service_ignores_regional_holidays():
    svc = HolidayService()

    class FakeApiClient:
        def get(self, path, params=None):
            return {"data": [_provincial_holiday("2026-08-24")], "total": 1}

    svc._client = FakeApiClient()
    assert svc.find("2026-08-24") is None


def test_holiday_service_follows_pagination():
    svc = HolidayService()
    calls = []

    class PagedApiClient:
        def get(self, path, params=None):
            page = (params or {}).get("page", 1)
            calls.append((path, page))
            if page == 1:
                return {"data": [_national_holiday("2026-08-17")], "total": 2}
            return {"data": [_national_holiday("2026-08-25")], "total": 2}

    svc._client = PagedApiClient()
    assert len(svc.list_holidays()) == 2
    assert svc.find("2026-08-25") is not None
    assert calls == [("/holidays", 1), ("/holidays", 2)]


def test_holiday_service_caches_one_request():
    svc = HolidayService()
    calls = []

    class CountingApiClient:
        def get(self, path, params=None):
            calls.append(path)
            return {"data": [_national_holiday("2026-08-17")], "total": 1}

    svc._client = CountingApiClient()
    assert svc.find("2026-08-17") is not None
    assert svc.find("2026-08-18") is None
    assert calls == ["/holidays"]


def test_holiday_service_disabled(monkeypatch):
    monkeypatch.setattr(commands.settings, "libur_nasional", False)
    assert holiday_service() is None
    assert find_holiday(None, "2026-08-17") is None


def test_holiday_lookup_fails_open(monkeypatch, capsys):
    monkeypatch.setattr(commands.settings, "libur_nasional", True)

    class BrokenService:
        def find(self, date):
            raise ApiError(500, "server libur mati")

    assert find_holiday(BrokenService(), "2026-08-17") is None
    assert "[WARN]" in capsys.readouterr().out


def test_cmd_absen_skips_on_national_holiday(monkeypatch, capsys):
    _fill_env(monkeypatch)
    monkeypatch.setattr(commands.settings, "hari_libur", "")

    class StubService:
        def clock_in(self, date):
            raise AssertionError("tidak boleh absen pada hari libur")

    class HolidayOnToday:
        def find(self, date):
            return Holiday(_national_holiday(date, "Maulid Nabi"))

    monkeypatch.setattr(commands, "holiday_service", lambda: HolidayOnToday())
    assert commands.cmd_absen(StubService()) == 0
    out = capsys.readouterr().out
    assert "[SKIP]" in out
    assert "Maulid Nabi" in out


def test_cmd_absen_proceeds_on_workday(monkeypatch, capsys):
    _fill_env(monkeypatch)
    monkeypatch.setattr(commands.settings, "hari_libur", "")
    sent = []

    class StubService:
        def clock_in(self, date):
            sent.append(date)
            return {"ok": True}

    class NoHolidayToday:
        def find(self, date):
            return None

    monkeypatch.setattr(commands, "holiday_service", lambda: NoHolidayToday())
    monkeypatch.setattr(commands.settings, "twilio_account_sid", "")
    monkeypatch.setattr(commands.settings, "whatsapp_to", "")
    assert commands.cmd_absen(StubService()) == 0
    assert sent == [date_str(0)]


def test_cmd_absen_skips_when_already_clocked_in(monkeypatch, capsys):
    _fill_env(monkeypatch)
    monkeypatch.setattr(commands.settings, "hari_libur", "")
    sent = []
    notified = []

    class StubService:
        def get_log(self, date):
            return DailyLog({"id": 1, "date": date})

        def clock_in(self, date):
            sent.append(date)
            return {"ok": True}

    class NoHolidayToday:
        def find(self, date):
            return None

    monkeypatch.setattr(commands, "holiday_service", lambda: NoHolidayToday())
    monkeypatch.setattr(commands, "log_notify", notified.append)
    assert commands.cmd_absen(StubService()) == 0
    assert sent == []
    assert len(notified) == 1
    assert "Sudah absen hari ini" in notified[0]


def test_invalid_reminder_times_default(monkeypatch):
    monkeypatch.setattr(commands.settings, "reminder_times", "16:00,21:00")
    assert invalid_reminder_times() == []


def test_invalid_reminder_times_rejects_bad_values(monkeypatch):
    monkeypatch.setattr(commands.settings, "reminder_times", "16:00,25:00,abc,21:70")
    assert invalid_reminder_times() == ["25:00", "abc", "21:70"]


def test_cmd_remind_skips_when_already_absent(monkeypatch, capsys):
    monkeypatch.setattr(commands.settings, "hari_libur", "")
    monkeypatch.setattr(commands, "holiday_service", lambda: None)
    sent = []
    monkeypatch.setattr(commands, "log_notify", sent.append)
    entry = DailyLog({"id": 1, "date": date_str(0)})
    assert commands.cmd_remind(FakeService({date_str(0): entry})) == 0
    assert sent == []
    assert "Sudah absen" in capsys.readouterr().out


def test_cmd_remind_notifies_when_missing(monkeypatch, capsys):
    monkeypatch.setattr(commands.settings, "hari_libur", "")
    monkeypatch.setattr(commands, "holiday_service", lambda: None)
    sent = []
    monkeypatch.setattr(commands, "log_notify", sent.append)
    assert commands.cmd_remind(FakeService({})) == 0
    assert len(sent) == 1
    assert "[INGAT]" in sent[0]
    assert date_str(0) in sent[0]


def test_cmd_remind_skips_on_national_holiday(monkeypatch, capsys):
    monkeypatch.setattr(commands.settings, "hari_libur", "")

    class StubService:
        def get_log(self, date):
            raise AssertionError("tidak boleh cek absen pada hari libur")

    class HolidayOnToday:
        def find(self, date):
            return Holiday(_national_holiday(date, "Maulid Nabi"))

    monkeypatch.setattr(commands, "holiday_service", lambda: HolidayOnToday())
    assert commands.cmd_remind(StubService()) == 0
    out = capsys.readouterr().out
    assert "[SKIP]" in out
    assert "Maulid Nabi" in out


def test_cmd_remind_skips_on_weekend(monkeypatch, capsys):
    today_name = commands.HARI[now_wib().weekday()]
    monkeypatch.setattr(commands.settings, "hari_libur", today_name)
    sent = []
    monkeypatch.setattr(commands, "log_notify", sent.append)
    assert commands.cmd_remind(FakeService({})) == 0
    assert sent == []
    assert "[SKIP]" in capsys.readouterr().out


def test_status_history_marks_holidays(monkeypatch, capsys):
    monkeypatch.setattr(commands.settings, "hari_libur", "")

    class HolidayYesterday:
        def find(self, date):
            if date == date_str(1):
                return Holiday(_national_holiday(date, "Proklamasi Kemerdekaan"))
            return None

    monkeypatch.setattr(commands, "holiday_service", lambda: HolidayYesterday())
    assert cmd_status(FakeService({}), days=3) == 0
    out = capsys.readouterr().out
    assert f"[OK] {date_str(1)}  Libur: Proklamasi Kemerdekaan" in out
    assert f"[OK] {date_str(2)}  Tidak Hadir" in out


def test_status_today_explains_holiday(monkeypatch, capsys):
    monkeypatch.setattr(commands.settings, "hari_libur", "")

    class HolidayToday:
        def find(self, date):
            return Holiday(_national_holiday(date, "Kelahiran Yesus Kristus"))

    monkeypatch.setattr(commands, "holiday_service", lambda: HolidayToday())
    assert cmd_status(FakeService({})) == 0
    assert "hari libur: Kelahiran Yesus Kristus" in capsys.readouterr().out


def test_send_whatsapp_skips_when_empty(monkeypatch):
    import app.utils.whatsapp as wamod
    calls = []
    monkeypatch.setattr(wamod.requests, "post", lambda *a, **kw: calls.append(1))
    monkeypatch.setattr(wamod.settings, "twilio_account_sid", "")
    monkeypatch.setattr(wamod.settings, "twilio_auth_token", "")
    monkeypatch.setattr(wamod.settings, "whatsapp_to", "")
    wamod.send_whatsapp("Tes")
    assert calls == []


def test_send_whatsapp_posts_when_configured(monkeypatch):
    import app.utils.whatsapp as wamod
    calls = []

    class FakeResponse:
        status_code = 201

    monkeypatch.setattr(wamod.requests, "post", lambda url, data=None, **kw: calls.append((url, data)) or FakeResponse())
    monkeypatch.setattr(wamod.settings, "twilio_account_sid", "AC123")
    monkeypatch.setattr(wamod.settings, "twilio_auth_token", "secret")
    monkeypatch.setattr(wamod.settings, "twilio_whatsapp_from", "+14155238886")
    monkeypatch.setattr(wamod.settings, "whatsapp_to", "+628123456789")

    wamod.send_whatsapp("Tes Pesan")
    assert len(calls) == 1
    assert "AC123" in calls[0][0]
    assert calls[0][1]["From"] == "whatsapp:+14155238886"
    assert calls[0][1]["To"] == "whatsapp:+628123456789"
    assert calls[0][1]["Body"] == "Tes Pesan"


def test_attendance_service_get_profile(monkeypatch):
    class FakeClient:
        def get(self, path, params=None):
            if path == "/users/me":
                return {
                    "data": {
                        "name": "Budi Santoso",
                        "email": "budi@example.com",
                        "photo": "https://cdn.kemnaker.go.id/avatar.jpg",
                        "phone": "081234567890",
                        "nik": "3201234567890001",
                        "internship": {
                            "company_name": "PT Maju Mundur",
                            "position": "Backend Developer",
                        },
                    }
                }
            raise AssertionError(f"Unexpected path: {path}")

    svc = AttendanceService(username="u", password="p")
    svc._client = FakeClient()
    prof = svc.get_profile()

    assert prof["name"] == "Budi Santoso"
    assert prof["email"] == "budi@example.com"
    assert prof["photo_url"] == "https://cdn.kemnaker.go.id/avatar.jpg"
    assert prof["phone"] == "081234567890"
    assert prof["nik"] == "3201234567890001"
    assert prof["mitra_name"] == "PT Maju Mundur"
    assert prof["position"] == "Backend Developer"


def test_attendance_service_get_profile_relative_photo(monkeypatch):
    class FakeClient:
        def get(self, path, params=None):
            return {
                "nama": "Siti Nurhaliza",
                "avatar": "/storage/photos/siti.png",
                "mitra": {"name": "PT Telkom Indonesia"},
            }

    svc = AttendanceService(username="u", password="p")
    svc._client = FakeClient()
    prof = svc.get_profile()

    assert prof["name"] == "Siti Nurhaliza"
    assert prof["photo_url"] == "https://monev.maganghub.kemnaker.go.id/storage/photos/siti.png"
    assert prof["mitra_name"] == "PT Telkom Indonesia"


def test_attendance_service_get_profile_handles_error():
    class BrokenClient:
        def get(self, path, params=None):
            raise Exception("Network timeout")

    svc = AttendanceService(username="u", password="p")
    svc._client = BrokenClient()
    prof = svc.get_profile()
    assert "error" in prof
    assert "Network timeout" in prof["error"]


def test_api_profile_endpoint():
    import json
    from main import app

    # Unauthenticated
    environ = {"PATH_INFO": "/api/profile", "REQUEST_METHOD": "GET"}
    headers = []
    status_code = []

    def start_response(status, h):
        status_code.append(status)
        headers.extend(h)

    res = app(environ, start_response)
    data = json.loads(res[0].decode("utf-8"))
    assert data["status"] is False
    assert "Belum terautentikasi" in data["message"]


def test_api_profile_endpoint_authenticated(monkeypatch):
    import json
    from main import app

    monkeypatch.setattr(
        AttendanceService,
        "get_profile",
        lambda self: {"name": "Test User", "photo_url": "https://example.com/p.jpg", "mitra_name": "PT Test"},
    )

    environ = {
        "PATH_INFO": "/api/profile",
        "REQUEST_METHOD": "GET",
        "HTTP_X_AUTH_USERNAME": "testuser",
        "HTTP_X_AUTH_PASSWORD": "secretpassword",
    }
    status_code = []
    headers = []

    def start_response(status, h):
        status_code.append(status)
        headers.extend(h)

    res = app(environ, start_response)
    data = json.loads(res[0].decode("utf-8"))
    assert data["status"] is True
    assert data["profile"]["name"] == "Test User"
    assert data["profile"]["photo_url"] == "https://example.com/p.jpg"


def test_holiday_service_with_authenticated_svc(monkeypatch):
    monkeypatch.setattr(commands.settings, "siapkerja_username", "")
    monkeypatch.setattr(commands.settings, "siapkerja_password", "")
    monkeypatch.setattr(commands.settings, "libur_nasional", True)

    class FakeClient:
        pass

    svc = AttendanceService(username="peserta@gmail.com", password="rahasia123")
    svc._client = FakeClient()

    hs = commands.holiday_service(svc)
    assert hs is not None
    assert hs._client is svc._client


def test_holiday_service_returns_none_when_no_credentials(monkeypatch, capsys):
    monkeypatch.setattr(commands.settings, "siapkerja_username", "")
    monkeypatch.setattr(commands.settings, "siapkerja_password", "")
    monkeypatch.setattr(commands.settings, "libur_nasional", True)

    svc = AttendanceService()  # no credentials, no client
    hs = commands.holiday_service(svc)
    assert hs is None
    # Verify find_holiday with None does not raise or emit any warning
    assert commands.find_holiday(hs, "2026-08-17") is None
    assert "[WARN]" not in capsys.readouterr().out


def test_attendance_service_rich_profile(monkeypatch):
    class FakeClient:
        def get(self, path, params=None):
            if path == "/users/me":
                return {
                    "data": {
                        "id": "e1ef7ae0-336d-4900-8951-3b6363ec3e91",
                        "name": "Rangga Mukti Daniswara",
                        "email": "daniswara.ranggamukti@gmail.com",
                        "job_role": "IT Staff",
                        "internship_company": "Asian Isuzu Casting Center",
                        "internship_location_latitude": -6.3227303,
                        "internship_location_longitude": 107.3375791,
                        "mentor_name": "TAUFIQ HIDAYATULLAH",
                        "internship_start_date": "2026-09-21T00:00:00+07:00",
                        "internship_end_date": "2027-03-20T23:59:59+07:00",
                    }
                }
            raise AssertionError(f"Unexpected path: {path}")

    svc = AttendanceService(username="u", password="p")
    svc._client = FakeClient()
    prof = svc.get_profile()

    assert prof["participant_id"] == "e1ef7ae0-336d-4900-8951-3b6363ec3e91"
    assert prof["name"] == "Rangga Mukti Daniswara"
    assert prof["job_role"] == "IT Staff"
    assert prof["mitra_name"] == "Asian Isuzu Casting Center"
    assert prof["company_latitude"] == -6.3227303
    assert prof["company_longitude"] == 107.3375791
    assert prof["mentor_name"] == "TAUFIQ HIDAYATULLAH"


def test_attendance_service_get_daily_logs_and_attendances(monkeypatch):
    class FakeClient:
        def get(self, path, params=None):
            if path == "/daily-logs":
                return {
                    "data": [
                        {
                            "id": 14096822,
                            "date": "2026-10-30",
                            "activity_log": "Membuat proposal project LLM",
                            "state": "APPROVED",
                        }
                    ]
                }
            if path == "/attendances":
                return {
                    "data": [
                        {
                            "id": 15464566,
                            "date": "2026-11-11",
                            "status": "PRESENT",
                            "approval_status": "SUBMITTED",
                        }
                    ]
                }
            if path == "/system/time":
                return {"data": {"datetime": "2026-11-11T06:30:57.776277129Z"}}
            raise AssertionError(f"Unexpected path: {path}")

    svc = AttendanceService(username="u", password="p")
    svc._client = FakeClient()

    logs = svc.get_daily_logs(participant_id="abc")
    assert len(logs) == 1
    assert logs[0]["id"] == 14096822
    assert logs[0]["state"] == "APPROVED"

    att = svc.get_attendances(participant_id="abc")
    assert len(att) == 1
    assert att[0]["status"] == "PRESENT"

    st = svc.get_system_time()
    assert "datetime" in st


def test_api_daily_logs_endpoint(monkeypatch):
    import json
    from main import app

    monkeypatch.setattr(
        AttendanceService,
        "get_daily_logs",
        lambda self, participant_id=None, limit=25: [{"id": 1, "date": "2026-10-30", "activity_log": "Test"}],
    )

    environ = {
        "PATH_INFO": "/api/daily_logs",
        "REQUEST_METHOD": "GET",
        "HTTP_X_AUTH_USERNAME": "testuser",
        "HTTP_X_AUTH_PASSWORD": "secretpassword",
    }
    status_code = []
    headers = []

    def start_response(status, h):
        status_code.append(status)
        headers.extend(h)

    res = app(environ, start_response)
    data = json.loads(res[0].decode("utf-8"))
    assert data["status"] is True
    assert len(data["logs"]) == 1
    assert data["logs"][0]["activity_log"] == "Test"
