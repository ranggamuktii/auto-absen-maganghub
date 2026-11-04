import json
import os
import sys
from http.server import BaseHTTPRequestHandler

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.models.attendance import AttendanceService
from app.utils.time import today_str


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function Handler for Dry Run Simulation."""

    def do_GET(self):
        try:
            payload = AttendanceService.attendance_payload(today_str())
            output_text = json.dumps(payload, ensure_ascii=False, indent=2)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": True,
                "output": output_text
            }).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": False,
                "output": f"Error: {e}"
            }).encode("utf-8"))

