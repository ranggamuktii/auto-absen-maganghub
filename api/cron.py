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
                from app.db import get_db_url, get_active_auto_absen_users, record_attendance_result
                active_users = get_active_auto_absen_users() if get_db_url() else []

                if active_users:
                    current_time_str = now_wib().strftime("%H:%M")
                    today = today_str()
                    processed_any = False

                    for u in active_users:
                        u_time = u.get("user_clock_in_time") or "13:30"
                        username = u["user_username"]
                        
                        # Jalankan jika sudah memasuki jam target user dan belum absen hari ini
                        if current_time_str >= u_time and u.get("user_last_absen_date") != today:
                            processed_any = True
                            print(f"[CRON] Memproses auto-absen untuk user: {username} (Jadwal: {u_time} WIB)")
                            try:
                                svc = AttendanceService(
                                    username=username,
                                    password=u["user_password"],
                                    location=u.get("user_location"),
                                    latitude=u.get("user_latitude"),
                                    longitude=u.get("user_longitude"),
                                    activity_log=u.get("user_activity_log"),
                                    lesson_learned=u.get("user_lesson_learned"),
                                    obstacles=u.get("user_obstacles"),
                                )
                                code = cmd_absen(svc)
                                status_str = "SUCCESS" if code == 0 else "FAILED"
                                msg = f"Auto-absen {'berhasil' if code == 0 else 'gagal'} dieksekusi pada {current_time_str} WIB"
                                record_attendance_result(username, today, status_str, msg)
                            except Exception as user_err:
                                print(f"[CRON] Error memproses {username}: {user_err}")
                                record_attendance_result(username, today, "FAILED", str(user_err))

                    if not processed_any:
                        print(f"[CRON] Belum ada user yang mencapai jadwal target atau semua user sudah absen ({current_time_str} WIB).")
                    exit_code = 0
                else:
                    # Fallback single-user dari environment variables
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

