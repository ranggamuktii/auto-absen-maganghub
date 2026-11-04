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
from app.commands import cmd_status
from app.utils.time import today_str, now_wib


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function Handler for Attendance Status."""

    def do_GET(self):
        buffer = io.StringIO()
        is_attended = False
        error_msg = None

        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                svc = AttendanceService()
                entry = svc.get_log(today_str())
                is_attended = bool(entry)
                cmd_status(svc, days=1)
        except Exception as e:
            error_msg = str(e)
            buffer.write(f"\n[EXCEPTION] {error_msg}")

        output_log = buffer.getvalue().strip()

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()

        response_data = {
            "status": True,
            "date": today_str(),
            "time_wib": now_wib().strftime("%Y-%m-%d %H:%M:%S"),
            "is_attended": is_attended,
            "error": error_msg,
            "output": output_log
        }
        self.wfile.write(json.dumps(response_data, ensure_ascii=False, indent=2).encode("utf-8"))
        return

