"""Fallback attendance tool for MagangHub Monev."""

import sys
import argparse
import io
import json
import os
from contextlib import redirect_stdout, redirect_stderr

import requests

from app.commands import cmd_absen, cmd_doctor, cmd_dry_run, cmd_remind, cmd_status
from app.models.attendance import AttendanceService
from app.utils.log import log
from app.utils.net import net_msg, with_retry
from app.utils.whatsapp import log_notify
from app.utils.time import today_str, now_wib


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Auto Absen MagangHub")
    parser.add_argument("action", choices=["absen", "status", "remind", "doctor"], help="Tindakan")
    parser.add_argument("--dry-run", action="store_true", help="Tampilkan payload absen tanpa mengirim")
    parser.add_argument("--days", type=int, default=1, help="Jumlah hari ke belakang untuk status")
    args = parser.parse_args()

    if args.action == "doctor":
        sys.exit(cmd_doctor())

    if args.dry_run:
        if args.action != "absen":
            parser.error("--dry-run hanya berlaku untuk perintah absen")
        sys.exit(cmd_dry_run())

    if args.days < 1:
        parser.error("--days minimal 1")

    try:
        svc = AttendanceService()
        with_retry("Login", svc.login)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        log_notify(net_msg(e))
        sys.exit(1)
    except Exception as e:
        log_notify(f"[FAIL] {e}")
        sys.exit(1)
    log("[OK] Login berhasil")

    if args.action == "absen":
        sys.exit(cmd_absen(svc))
    elif args.action == "remind":
        sys.exit(cmd_remind(svc))
    else:
        sys.exit(cmd_status(svc, days=args.days))


def _get_credentials(environ, body_data=None):
    """Extract username & password from headers, body, or server settings."""
    from app.config import settings
    user = environ.get("HTTP_X_AUTH_USERNAME", "")
    pwd = environ.get("HTTP_X_AUTH_PASSWORD", "")

    if body_data and isinstance(body_data, dict):
        user = user or body_data.get("username", "")
        pwd = pwd or body_data.get("password", "")

    user = (user or settings.siapkerja_username or "").strip()
    pwd = (pwd or settings.siapkerja_password or "").strip()
    return user, pwd


def _read_body_json(environ):
    """Parse JSON body from WSGI environ if available."""
    try:
        content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
    except (ValueError, TypeError):
        content_length = 0

    if content_length > 0:
        wsgi_input = environ.get("wsgi.input")
        if wsgi_input:
            raw = wsgi_input.read(content_length).decode("utf-8")
            try:
                return json.loads(raw)
            except Exception:
                pass
    return {}


def app(environ, start_response):
    """WSGI application callable for Vercel Serverless runtime."""
    raw_path = environ.get("PATH_INFO", "") or ""
    path = raw_path.rstrip("/") if raw_path != "/" else "/"
    method = environ.get("REQUEST_METHOD", "GET").upper()

    # 1. Favicon
    if path == "/favicon.ico":
        start_response("204 No Content", [])
        return []

    # 2. Login Endpoint (POST /api/login)
    if path == "/api/login":
        body_data = _read_body_json(environ)
        user, pwd = _get_credentials(environ, body_data)

        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": False,
                "message": "Email/username dan password akun SIAPkerja wajib diisi."
            }).encode("utf-8")]

        try:
            from app.models.attendance import AttendanceService
            svc = AttendanceService(username=user, password=pwd)
            svc.login()

            # Attempt to fetch profile immediately on login
            profile = {}
            try:
                profile = svc.get_profile()
            except Exception as pe:
                print(f"[API] Profile fetch on login warning: {pe}")

            # Database integration (Neon Postgres)
            preferences = None
            try:
                from app.db import init_db, save_or_update_user, update_user_profile, get_user, get_db_url
                if get_db_url():
                    init_db()
                    existing = get_user(user)
                    if not existing:
                        from app.config import settings
                        try:
                            lat = float(settings.latitude)
                        except (ValueError, TypeError):
                            lat = -6.370891
                        try:
                            lon = float(settings.longitude)
                        except (ValueError, TypeError):
                            lon = 107.272352

                        save_or_update_user(
                            username=user,
                            password=pwd,
                            location=settings.location or "Karawang",
                            latitude=lat,
                            longitude=lon,
                            activity_log=settings.activity_log or "",
                            lesson_learned=settings.lesson_learned or "",
                            obstacles=settings.obstacles or "",
                            auto_absen=True,
                        )
                    else:
                        # Update password in case it changed
                        save_or_update_user(
                            username=user,
                            password=pwd,
                            location=existing.get("user_location") or "Karawang",
                            latitude=existing.get("user_latitude") or -6.370891,
                            longitude=existing.get("user_longitude") or 107.272352,
                            activity_log=existing.get("user_activity_log", ""),
                            lesson_learned=existing.get("user_lesson_learned", ""),
                            obstacles=existing.get("user_obstacles", ""),
                            auto_absen=existing.get("user_auto_absen", True),
                        )

                    if profile and not profile.get("error"):
                        update_user_profile(
                            username=user,
                            fullname=profile.get("name", ""),
                            photo_url=profile.get("photo_url", ""),
                            mitra=profile.get("mitra_name", ""),
                            position=profile.get("position", ""),
                        )
                    preferences = get_user(user)
            except Exception as dbe:
                print(f"[DB] Non-critical error on login: {dbe}")

            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": True,
                "message": "Login berhasil! Selamat datang.",
                "user": {"username": user},
                "profile": profile,
                "preferences": preferences,
                "db_connected": bool(preferences)
            }).encode("utf-8")]
        except Exception as e:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": False,
                "message": f"Login gagal: {e}"
            }).encode("utf-8")]

    # 3. Save Settings Endpoint (POST /api/save_settings)
    if path == "/api/save_settings":
        body_data = _read_body_json(environ)
        user, pwd = _get_credentials(environ, body_data)
        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({"status": False, "message": "Belum terautentikasi."}).encode("utf-8")]

        try:
            from app.db import save_or_update_user, get_user
            loc = body_data.get("location") or "Karawang"
            try:
                lat = float(body_data.get("latitude"))
            except (ValueError, TypeError):
                lat = -6.370891
            try:
                lon = float(body_data.get("longitude"))
            except (ValueError, TypeError):
                lon = 107.272352
            act = body_data.get("activity_log", "")
            les = body_data.get("lesson_learned", "")
            obs = body_data.get("obstacles", "")
            auto = bool(body_data.get("auto_absen", True))

            ok = save_or_update_user(
                username=user,
                password=pwd,
                location=loc,
                latitude=lat,
                longitude=lon,
                activity_log=act,
                lesson_learned=les,
                obstacles=obs,
                auto_absen=auto,
            )
            updated = get_user(user)
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": ok,
                "message": "Pengaturan auto-absen berhasil disimpan!" if ok else "Gagal menyimpan ke database.",
                "preferences": updated
            }).encode("utf-8")]
        except Exception as e:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({"status": False, "message": f"Error: {e}"}).encode("utf-8")]

    # 4. Dry Run
    if path in ("/api/dry_run", "/api/dry-run"):
        body_data = _read_body_json(environ)
        lat = body_data.get("latitude")
        lon = body_data.get("longitude")
        loc = body_data.get("location")
        act = body_data.get("activity_log")
        les = body_data.get("lesson_learned")
        obs = body_data.get("obstacles")

        try:
            from app.models.attendance import AttendanceService
            payload = AttendanceService.attendance_payload(
                today_str(),
                latitude=lat,
                longitude=lon,
                location=loc,
                activity_log=act,
                lesson_learned=les,
                obstacles=obs,
            )
            body = json.dumps({"status": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}).encode("utf-8")
        except Exception as e:
            body = json.dumps({"status": False, "output": f"Simulasi gagal: {e}"}).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [body]

    # 5. Manual Trigger / Absen Sekarang (POST /api/trigger or /api/absen)
    if path in ("/api/trigger", "/api/absen"):
        body_data = _read_body_json(environ)
        user, pwd = _get_credentials(environ, body_data)
        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": False,
                "message": "Kredensial belum tersedia. Silakan login terlebih dahulu."
            }).encode("utf-8")]

        loc = body_data.get("location")
        lat = body_data.get("latitude")
        lon = body_data.get("longitude")
        act = body_data.get("activity_log")
        les = body_data.get("lesson_learned")
        obs = body_data.get("obstacles")

        buffer = io.StringIO()
        code = 1
        err_msg = None
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                from app.models.attendance import AttendanceService
                from app.commands import cmd_absen
                svc = AttendanceService(
                    username=user,
                    password=pwd,
                    location=loc,
                    latitude=lat,
                    longitude=lon,
                    activity_log=act,
                    lesson_learned=les,
                    obstacles=obs,
                )
                code = cmd_absen(svc)
        except Exception as e:
            err_msg = str(e)
            buffer.write(f"\n[EXCEPTION] {err_msg}")

        out = buffer.getvalue().strip()
        is_ok = (code == 0)

        # Record result in database if available
        try:
            from app.db import record_attendance_result, get_db_url
            if get_db_url():
                record_attendance_result(
                    username=user,
                    absen_date=today_str(),
                    status="SUCCESS" if is_ok else "FAILED",
                    message=out or err_msg or "",
                )
        except Exception:
            pass

        res_data = {
            "status": is_ok,
            "exit_code": code,
            "message": "Absen berhasil diproses!" if is_ok else (err_msg or "Gagal memproses absen"),
            "output": out
        }
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps(res_data, ensure_ascii=False, indent=2).encode("utf-8")]

    # 6. Automated Multi-User Cron Endpoint (/api/cron)
    if path == "/api/cron":
        cron_secret = os.environ.get("CRON_SECRET", "").strip()
        auth_header = environ.get("HTTP_AUTHORIZATION", "").strip()
        if cron_secret and auth_header != f"Bearer {cron_secret}":
            start_response("401 Unauthorized", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({"status": False, "message": "Unauthorized"}).encode("utf-8")]

        # Check if database has registered auto-absen users
        active_users = []
        try:
            from app.db import get_active_auto_absen_users, record_attendance_result, get_db_url
            if get_db_url():
                active_users = get_active_auto_absen_users()
        except Exception as dbe:
            print(f"[DB] Error querying active users: {dbe}")

        results = []
        if active_users:
            from app.models.attendance import AttendanceService
            from app.commands import cmd_absen

            for u in active_users:
                uname = u["user_username"]
                upwd = u["user_password"]
                buffer = io.StringIO()
                code = 1
                try:
                    with redirect_stdout(buffer), redirect_stderr(buffer):
                        svc = AttendanceService(
                            username=uname,
                            password=upwd,
                            location=u.get("user_location"),
                            latitude=u.get("user_latitude"),
                            longitude=u.get("user_longitude"),
                            activity_log=u.get("user_activity_log"),
                            lesson_learned=u.get("user_lesson_learned"),
                            obstacles=u.get("user_obstacles"),
                        )
                        code = cmd_absen(svc)
                except Exception as e:
                    buffer.write(f"\n[EXCEPTION] {e}")

                out = buffer.getvalue().strip()
                status_str = "SUCCESS" if code == 0 else "FAILED"
                try:
                    record_attendance_result(uname, today_str(), status_str, out)
                except Exception:
                    pass

                results.append({
                    "username": uname,
                    "status": (code == 0),
                    "output": out
                })

            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": True,
                "message": f"Cron selesai mengeksekusi {len(active_users)} pengguna.",
                "total_users": len(active_users),
                "results": results
            }, ensure_ascii=False, indent=2).encode("utf-8")]

        # Fallback to single user from headers or ENV
        user, pwd = _get_credentials(environ)
        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": False,
                "message": "Tidak ada pengguna aktif di database dan kredensial belum tersedia."
            }).encode("utf-8")]

        buffer = io.StringIO()
        code = 1
        err_msg = None
        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                from app.models.attendance import AttendanceService
                from app.commands import cmd_absen
                svc = AttendanceService(username=user, password=pwd)
                code = cmd_absen(svc)
        except Exception as e:
            err_msg = str(e)
            buffer.write(f"\n[EXCEPTION] {err_msg}")

        out = buffer.getvalue().strip()
        is_ok = (code == 0)
        res_data = {
            "status": is_ok,
            "exit_code": code,
            "message": "Absen berhasil diproses" if is_ok else (err_msg or "Gagal memproses absen"),
            "output": out
        }
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps(res_data, ensure_ascii=False, indent=2).encode("utf-8")]

    # 7. Status Check (/api/status)
    if path == "/api/status":
        from app.config import settings

        user, pwd = _get_credentials(environ)
        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": False,
                "need_login": True,
                "message": "Silakan login menggunakan akun Kemnaker untuk melihat status presensi.",
                "env": {
                    "location": settings.location,
                    "clock_in_time": "15:00",
                    "activity_log": settings.activity_log,
                    "lesson_learned": settings.lesson_learned,
                    "obstacles": settings.obstacles
                }
            }, ensure_ascii=False, indent=2).encode("utf-8")]

        # Query user preferences from DB if available
        user_pref = None
        db_connected = False
        db_message = ""
        try:
            from app.db import get_user, init_db, check_connection
            is_ok, msg = check_connection()
            db_connected = is_ok
            db_message = msg
            if is_ok:
                init_db()
                user_pref = get_user(user)
        except Exception as e:
            db_connected = False
            db_message = str(e)


        buffer = io.StringIO()
        is_attended = False
        err_msg = None

        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                from app.models.attendance import AttendanceService
                from app.commands import cmd_status
                svc = AttendanceService(username=user, password=pwd)
                entry = svc.get_log(today_str())
                is_attended = bool(entry)
                cmd_status(svc, days=1)
        except Exception as e:
            err_msg = str(e)
            buffer.write(f"\n[EXCEPTION] {err_msg}")

        out = buffer.getvalue().strip()

        # Profile from DB cache or fresh from /users/me
        profile_data = None
        if user_pref and (user_pref.get("user_fullname") or user_pref.get("user_photo_url") or user_pref.get("user_mitra")):
            profile_data = {
                "name": user_pref.get("user_fullname", ""),
                "photo_url": user_pref.get("user_photo_url", ""),
                "mitra_name": user_pref.get("user_mitra", ""),
                "position": user_pref.get("user_position", ""),
            }
        else:
            try:
                from app.models.attendance import AttendanceService
                _svc_prof = AttendanceService(username=user, password=pwd)
                p = _svc_prof.get_profile()
                if p and not p.get("error"):
                    profile_data = p
                    try:
                        from app.db import update_user_profile, get_db_url
                        if get_db_url():
                            update_user_profile(
                                username=user,
                                fullname=p.get("name", ""),
                                photo_url=p.get("photo_url", ""),
                                mitra=p.get("mitra_name", ""),
                                position=p.get("position", ""),
                            )
                    except Exception:
                        pass
            except Exception:
                pass

        res_data = {
            "status": True,
            "date": today_str(),
            "time_wib": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
            "is_attended": is_attended,
            "error": err_msg,
            "output": out,
            "profile": profile_data,
            "db_connected": db_connected,
            "db_message": db_message,
            "preferences": user_pref,
            "env": {
                "location": (user_pref.get("user_location") if user_pref else None) or settings.location,
                "latitude": (user_pref.get("user_latitude") if user_pref else None) or settings.latitude,
                "longitude": (user_pref.get("user_longitude") if user_pref else None) or settings.longitude,
                "clock_in_time": "08:25",
                "activity_log": (user_pref.get("user_activity_log") if user_pref else None) or settings.activity_log,
                "lesson_learned": (user_pref.get("user_lesson_learned") if user_pref else None) or settings.lesson_learned,
                "obstacles": (user_pref.get("user_obstacles") if user_pref else None) or settings.obstacles,
                "auto_absen": (user_pref.get("user_auto_absen") if user_pref else True)
            }
        }
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps(res_data, ensure_ascii=False, indent=2).encode("utf-8")]

    # 8. User Profile Endpoint (/api/profile or /api/me)
    if path in ("/api/profile", "/api/me"):
        user, pwd = _get_credentials(environ)
        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({"status": False, "message": "Belum terautentikasi."}).encode("utf-8")]

        try:
            from app.models.attendance import AttendanceService
            svc = AttendanceService(username=user, password=pwd)
            profile = svc.get_profile()

            try:
                from app.db import update_user_profile, get_db_url
                if get_db_url() and profile and not profile.get("error"):
                    update_user_profile(
                        username=user,
                        fullname=profile.get("name", ""),
                        photo_url=profile.get("photo_url", ""),
                        mitra=profile.get("mitra_name", ""),
                        position=profile.get("position", ""),
                    )
            except Exception as dbe:
                print(f"[DB] Profile cache warning: {dbe}")

            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": True,
                "profile": profile
            }, ensure_ascii=False, indent=2).encode("utf-8")]
        except Exception as e:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({"status": False, "message": str(e)}).encode("utf-8")]

    # 9. Traceability Audit Logs Endpoint (/api/logs)
    if path == "/api/logs":
        user, pwd = _get_credentials(environ)
        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({"status": False, "logs": [], "message": "Belum terautentikasi."}).encode("utf-8")]

        logs = []
        try:
            from app.db import get_recent_logs, get_db_url
            if get_db_url():
                logs = get_recent_logs(user, limit=15)
        except Exception as e:
            print(f"[DB] Error loading audit logs: {e}")

        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps({"status": True, "logs": logs}, ensure_ascii=False, indent=2).encode("utf-8")]

    # 9. Serve static HTML for root
    html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "rb") as f:
            html_bytes = f.read()
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [html_bytes]

    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


# Alias for Vercel
handler = app


if __name__ == "__main__":
    main()
