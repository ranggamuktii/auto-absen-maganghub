import io
import json
import os
import sys
from contextlib import redirect_stdout, redirect_stderr
from http.server import BaseHTTPRequestHandler

# Pastikan root project terdaftar di sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.models.attendance import AttendanceService
from app.commands import cmd_absen
from app.utils.time import today_str, now_wib


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function Handler for Attendance Cron."""

    def do_GET(self):
        # 1. Verifikasi CRON_SECRET jika dikonfigurasi di Environment Variables
        cron_secret = os.environ.get("CRON_SECRET", "").strip()
        auth_header = self.headers.get("Authorization", "").strip()

        if cron_secret and auth_header != f"Bearer {cron_secret}":
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "status": False,
                    "message": "Unauthorized: Invalid CRON_SECRET"
                }).encode("utf-8")
            )
            return

        # 2. Eksekusi absen dan tangkap log output
        buffer = io.StringIO()
        exit_code = 1
        error_msg = None

        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                svc = AttendanceService()
                exit_code = cmd_absen(svc)
        except Exception as e:
            error_msg = str(e)
            buffer.write(f"\n[EXCEPTION] {error_msg}")

        output_log = buffer.getvalue().strip()
        is_success = (exit_code == 0)

        # 3. Kembalikan response JSON
        self.send_response(200 if is_success else 500)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

        response_data = {
            "status": is_success,
            "exit_code": exit_code,
            "date": today_str(),
            "time_wib": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Absen berhasil diproses" if is_success else (error_msg or "Gagal memproses absen"),
            "output": output_log
        }
        self.wfile.write(json.dumps(response_data, ensure_ascii=False, indent=2).encode("utf-8"))
        return
