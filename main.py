"""Fallback attendance tool for MagangHub Monev."""

import sys
import argparse

import requests

from app.commands import cmd_absen, cmd_doctor, cmd_dry_run, cmd_remind, cmd_status
from app.models.attendance import AttendanceService
from app.utils.log import log
from app.utils.net import net_msg, with_retry
from app.utils.whatsapp import log_notify


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


# Vercel Serverless Function entry point (WSGI Standard)
from http.server import BaseHTTPRequestHandler
import json
import io
import os
from contextlib import redirect_stdout, redirect_stderr


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
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": True,
                "message": "Login berhasil! Selamat datang.",
                "user": {"username": user}
            }).encode("utf-8")]
        except Exception as e:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": False,
                "message": f"Login gagal: {e}"
            }).encode("utf-8")]

    # 3. Dry Run
    if path in ("/api/dry_run", "/api/dry-run"):
        try:
            from app.models.attendance import AttendanceService
            from app.utils.time import today_str
            payload = AttendanceService.attendance_payload(today_str())
            body = json.dumps({"status": True, "output": json.dumps(payload, ensure_ascii=False, indent=2)}).encode("utf-8")
        except Exception as e:
            body = json.dumps({"status": False, "output": f"Simulasi gagal: {e}"}).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [body]

    # 4. Cron / Trigger Absen
    if path == "/api/cron":
        cron_secret = os.environ.get("CRON_SECRET", "").strip()
        auth_header = environ.get("HTTP_AUTHORIZATION", "").strip()
        if cron_secret and auth_header != f"Bearer {cron_secret}":
            start_response("401 Unauthorized", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({"status": False, "message": "Unauthorized"}).encode("utf-8")]

        user, pwd = _get_credentials(environ)
        if not user or not pwd:
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps({
                "status": False,
                "message": "Kredensial belum tersedia. Silakan login terlebih dahulu."
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

    # 5. Status Check
    if path == "/api/status":
        from app.utils.time import today_str, now_wib
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
        res_data = {
            "status": True,
            "date": today_str(),
            "time_wib": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
            "is_attended": is_attended,
            "error": err_msg,
            "output": out,
            "env": {
                "location": settings.location,
                "clock_in_time": "15:00",
                "activity_log": settings.activity_log,
                "lesson_learned": settings.lesson_learned,
                "obstacles": settings.obstacles
            }
        }
        start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
        return [json.dumps(res_data, ensure_ascii=False, indent=2).encode("utf-8")]

    # 6. Serve static HTML for root
    html_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "index.html")
    if os.path.exists(html_file):
        with open(html_file, "rb") as f:
            html_bytes = f.read()
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [html_bytes]

    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]


# Alias for compatibility
handler = app


# Alias for compatibility
handler = app


if __name__ == "__main__":
    main()
