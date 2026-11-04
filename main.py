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


# Vercel Serverless Function entry point
from http.server import BaseHTTPRequestHandler
import json
import io
import os
from contextlib import redirect_stdout, redirect_stderr


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function handler for API endpoints."""

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path.endswith("/cron"):
            cron_secret = os.environ.get("CRON_SECRET", "").strip()
            auth_header = self.headers.get("Authorization", "").strip()
            if cron_secret and auth_header != f"Bearer {cron_secret}":
                self.send_response(401)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"status": False, "message": "Unauthorized"}).encode("utf-8"))
                return

            buffer = io.StringIO()
            code = 1
            err = None
            try:
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    svc = AttendanceService()
                    code = cmd_absen(svc)
            except Exception as e:
                err = str(e)
                buffer.write(f"\n[EXCEPTION] {err}")

            self.send_response(200 if code == 0 else 500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": code == 0,
                "exit_code": code,
                "message": "Absen berhasil diproses" if code == 0 else (err or "Gagal memproses absen"),
                "output": buffer.getvalue().strip()
            }, ensure_ascii=False, indent=2).encode("utf-8"))
            return
        elif path.endswith("/status"):
            from app.utils.time import today_str, now_wib
            buffer = io.StringIO()
            is_attended = False
            err = None
            try:
                with redirect_stdout(buffer), redirect_stderr(buffer):
                    svc = AttendanceService()
                    entry = svc.get_log(today_str())
                    is_attended = bool(entry)
                    cmd_status(svc, days=1)
            except Exception as e:
                err = str(e)
                buffer.write(f"\n[EXCEPTION] {err}")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": True,
                "date": today_str(),
                "time_wib": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
                "is_attended": is_attended,
                "output": buffer.getvalue().strip()
            }, ensure_ascii=False, indent=2).encode("utf-8"))
            return
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": True,
                "message": "Auto Absen MagangHub Serverless API",
                "endpoints": ["/api/cron", "/api/status"]
            }, indent=2).encode("utf-8"))
            return


if __name__ == "__main__":
    main()
