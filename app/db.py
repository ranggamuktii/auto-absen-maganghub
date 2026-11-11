"""Database operations with PostgreSQL (Neon Serverless)."""

import os
import ssl
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, unquote

import pg8000.dbapi

from app.crypto import encrypt_password, decrypt_password


def get_db_url() -> str:
    """Get Postgres database URL from environment with fallback detection."""
    # 1. Direct connection string variants
    for var in (
        "POSTGRES_URL",
        "DATABASE_URL",
        "POSTGRES_PRISMA_URL",
        "POSTGRES_URL_NON_POOLING",
        "DATABASE_URL_UNPOOLED",
        "NEON_DATABASE_URL",
    ):
        val = os.environ.get(var, "").strip()
        if val:
            return val

    # 2. Reconstruct from components if present
    host = (os.environ.get("PGHOST") or os.environ.get("POSTGRES_HOST") or "").strip()
    user = (os.environ.get("PGUSER") or os.environ.get("POSTGRES_USER") or "").strip()
    pwd = (os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD") or "").strip()
    db = (os.environ.get("PGDATABASE") or os.environ.get("POSTGRES_DATABASE") or "").strip() or "neondb"
    port = (os.environ.get("PGPORT") or os.environ.get("POSTGRES_PORT") or "").strip() or "5432"

    if host and user and pwd:
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}?sslmode=require"

    return ""


def get_connection():
    """Create a connection to Neon PostgreSQL using pg8000."""
    url = get_db_url()
    if not url:
        return None

    # Handle postgres:// scheme if provided
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    parsed = urlparse(url)
    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None
    dbname = unquote(parsed.path.lstrip("/").split("?")[0]) if parsed.path else "neondb"
    port = parsed.port or 5432

    # Enable SSL for Neon / cloud databases
    ssl_context = None
    if "sslmode=require" in url or (parsed.hostname and "neon.tech" in parsed.hostname) or "vercel-storage" in url:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    return pg8000.dbapi.connect(
        user=username,
        password=password,
        host=parsed.hostname,
        port=port,
        database=dbname,
        ssl_context=ssl_context,
        timeout=15,
    )


def check_connection() -> Tuple[bool, str]:
    """Test connection and return (success, message)."""
    url = get_db_url()
    if not url:
        return False, "Environment variable POSTGRES_URL / DATABASE_URL belum ditemukan di Vercel."
    try:
        conn = get_connection()
        if not conn:
            return False, "Gagal membuat koneksi socket database."
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        return True, "Koneksi ke Neon Postgres berhasil!"
    except Exception as e:
        return False, f"Koneksi gagal: {e}"


def init_db() -> bool:
    """Initialize database tables if they do not exist."""
    conn = get_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        # Table tb_user
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_user (
                user_id SERIAL PRIMARY KEY,
                user_username VARCHAR(150) UNIQUE NOT NULL,
                user_password TEXT NOT NULL,
                user_location VARCHAR(100) DEFAULT 'Karawang',
                user_latitude NUMERIC(10, 6) DEFAULT -6.370891,
                user_longitude NUMERIC(10, 6) DEFAULT 107.272352,
                user_activity_log TEXT,
                user_lesson_learned TEXT,
                user_obstacles TEXT,
                user_auto_absen BOOLEAN DEFAULT TRUE,
                user_last_absen_date DATE,
                user_last_absen_status VARCHAR(50),
                user_last_absen_log TEXT,
                user_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Table tb_attendance_log
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tb_attendance_log (
                log_id SERIAL PRIMARY KEY,
                user_username VARCHAR(150) NOT NULL,
                log_date DATE NOT NULL,
                log_status VARCHAR(50) NOT NULL,
                log_message TEXT,
                log_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Add profile columns to tb_user if they don't exist
        cur.execute("""
            ALTER TABLE tb_user ADD COLUMN IF NOT EXISTS user_fullname VARCHAR(200);
            ALTER TABLE tb_user ADD COLUMN IF NOT EXISTS user_photo_url TEXT;
            ALTER TABLE tb_user ADD COLUMN IF NOT EXISTS user_mitra VARCHAR(200);
            ALTER TABLE tb_user ADD COLUMN IF NOT EXISTS user_position VARCHAR(200);
            ALTER TABLE tb_user ADD COLUMN IF NOT EXISTS user_clock_in_time VARCHAR(10) DEFAULT '13:30';
        """)

        conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"[DB] Init error: {e}")
        return False
    finally:
        conn.close()


def validate_clock_in_time(val: Optional[str]) -> str:
    """Validate and enforce safe clock-in window between 13:00 and 20:00 WIB."""
    if not val or not isinstance(val, str) or ":" not in val:
        return "13:30"
    try:
        parts = val.strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        total_min = h * 60 + m
        # Clamp between 13:00 (780 min) and 20:00 (1200 min)
        if total_min < 780:
            return "13:00"
        if total_min > 1200:
            return "20:00"
        return f"{h:02d}:{m:02d}"
    except (ValueError, IndexError):
        return "13:30"


def save_or_update_user(
    username: str,
    password: str,
    location: str = "Karawang",
    latitude: float = -6.370891,
    longitude: float = 107.272352,
    activity_log: str = "",
    lesson_learned: str = "",
    obstacles: str = "",
    auto_absen: bool = True,
    clock_in_time: str = "13:30",
) -> bool:
    """Save or update user settings with AES-256 encrypted password and validated clock-in time."""
    conn = get_connection()
    if not conn:
        return False

    stored_password = encrypt_password(password)
    safe_clock_in_time = validate_clock_in_time(clock_in_time)

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tb_user (
                user_username, user_password, user_location,
                user_latitude, user_longitude, user_activity_log,
                user_lesson_learned, user_obstacles, user_auto_absen,
                user_clock_in_time, user_updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_username) DO UPDATE SET
                user_password = EXCLUDED.user_password,
                user_location = EXCLUDED.user_location,
                user_latitude = EXCLUDED.user_latitude,
                user_longitude = EXCLUDED.user_longitude,
                user_activity_log = EXCLUDED.user_activity_log,
                user_lesson_learned = EXCLUDED.user_lesson_learned,
                user_obstacles = EXCLUDED.user_obstacles,
                user_auto_absen = EXCLUDED.user_auto_absen,
                user_clock_in_time = EXCLUDED.user_clock_in_time,
                user_updated_at = CURRENT_TIMESTAMP;
            """,
            (
                username,
                stored_password,
                location,
                latitude,
                longitude,
                activity_log,
                lesson_learned,
                obstacles,
                auto_absen,
                safe_clock_in_time,
            ),
        )
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"[DB] save_or_update_user error: {e}")
        return False
    finally:
        conn.close()


def update_user_profile(
    username: str,
    fullname: str = "",
    photo_url: str = "",
    mitra: str = "",
    position: str = "",
) -> bool:
    """Update profile information for an existing user."""
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tb_user
            SET user_fullname = COALESCE(NULLIF(%s, ''), user_fullname),
                user_photo_url = COALESCE(NULLIF(%s, ''), user_photo_url),
                user_mitra = COALESCE(NULLIF(%s, ''), user_mitra),
                user_position = COALESCE(NULLIF(%s, ''), user_position),
                user_updated_at = CURRENT_TIMESTAMP
            WHERE user_username = %s;
            """,
            (fullname, photo_url, mitra, position, username),
        )
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"[DB] update_user_profile error: {e}")
        return False
    finally:
        conn.close()


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve user settings with decrypted password."""
    conn = get_connection()
    if not conn:
        return None

    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT user_id, user_username, user_password, user_location,
                       user_latitude, user_longitude, user_activity_log,
                       user_lesson_learned, user_obstacles, user_auto_absen,
                       user_last_absen_date, user_last_absen_status, user_last_absen_log,
                       user_fullname, user_photo_url, user_mitra, user_position,
                       COALESCE(user_clock_in_time, '13:30')
                FROM tb_user
                WHERE user_username = %s
                LIMIT 1;
                """,
                (username,),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None

            raw_pwd = decrypt_password(row[2])

            return {
                "user_id": row[0],
                "user_username": row[1],
                "user_password": raw_pwd,
                "user_location": row[3],
                "user_latitude": float(row[4]) if row[4] is not None else -6.370891,
                "user_longitude": float(row[5]) if row[5] is not None else 107.272352,
                "user_activity_log": row[6] or "",
                "user_lesson_learned": row[7] or "",
                "user_obstacles": row[8] or "",
                "user_auto_absen": bool(row[9]),
                "user_last_absen_date": str(row[10]) if row[10] else None,
                "user_last_absen_status": row[11] or "",
                "user_last_absen_log": row[12] or "",
                "user_fullname": row[13] or "",
                "user_photo_url": row[14] or "",
                "user_mitra": row[15] or "",
                "user_position": row[16] or "",
                "user_clock_in_time": row[17] or "13:30",
            }
        except Exception:
            # Fallback if profile or clock_in_time columns don't exist yet
            conn.rollback()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id, user_username, user_password, user_location,
                       user_latitude, user_longitude, user_activity_log,
                       user_lesson_learned, user_obstacles, user_auto_absen,
                       user_last_absen_date, user_last_absen_status, user_last_absen_log
                FROM tb_user
                WHERE user_username = %s
                LIMIT 1;
                """,
                (username,),
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None

            raw_pwd = decrypt_password(row[2])

            return {
                "user_id": row[0],
                "user_username": row[1],
                "user_password": raw_pwd,
                "user_location": row[3],
                "user_latitude": float(row[4]) if row[4] is not None else -6.370891,
                "user_longitude": float(row[5]) if row[5] is not None else 107.272352,
                "user_activity_log": row[6] or "",
                "user_lesson_learned": row[7] or "",
                "user_obstacles": row[8] or "",
                "user_auto_absen": bool(row[9]),
                "user_last_absen_date": str(row[10]) if row[10] else None,
                "user_last_absen_status": row[11] or "",
                "user_last_absen_log": row[12] or "",
                "user_fullname": "",
                "user_photo_url": "",
                "user_mitra": "",
                "user_position": "",
                "user_clock_in_time": "13:30",
            }
    except Exception as e:
        print(f"[DB] get_user error: {e}")
        return None
    finally:
        conn.close()


def get_active_auto_absen_users() -> List[Dict[str, Any]]:
    """Get all users who have enabled auto-absen with decrypted passwords and clock-in time."""
    conn = get_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT user_id, user_username, user_password, user_location,
                       user_latitude, user_longitude, user_activity_log,
                       user_lesson_learned, user_obstacles, user_last_absen_date,
                       COALESCE(user_clock_in_time, '13:30')
                FROM tb_user
                WHERE user_auto_absen = TRUE;
                """
            )
            rows = cur.fetchall()
            cur.close()
            users = []
            for row in rows:
                raw_pwd = decrypt_password(row[2])
                users.append({
                    "user_id": row[0],
                    "user_username": row[1],
                    "user_password": raw_pwd,
                    "user_location": row[3],
                    "user_latitude": float(row[4]) if row[4] is not None else -6.370891,
                    "user_longitude": float(row[5]) if row[5] is not None else 107.272352,
                    "user_activity_log": row[6] or "",
                    "user_lesson_learned": row[7] or "",
                    "user_obstacles": row[8] or "",
                    "user_last_absen_date": str(row[9]) if row[9] else None,
                    "user_clock_in_time": row[10] or "13:30",
                })
            return users
        except Exception:
            conn.rollback()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT user_id, user_username, user_password, user_location,
                       user_latitude, user_longitude, user_activity_log,
                       user_lesson_learned, user_obstacles, user_last_absen_date
                FROM tb_user
                WHERE user_auto_absen = TRUE;
                """
            )
            rows = cur.fetchall()
            cur.close()
            users = []
            for row in rows:
                raw_pwd = decrypt_password(row[2])
                users.append({
                    "user_id": row[0],
                    "user_username": row[1],
                    "user_password": raw_pwd,
                    "user_location": row[3],
                    "user_latitude": float(row[4]) if row[4] is not None else -6.370891,
                    "user_longitude": float(row[5]) if row[5] is not None else 107.272352,
                    "user_activity_log": row[6] or "",
                    "user_lesson_learned": row[7] or "",
                    "user_obstacles": row[8] or "",
                    "user_last_absen_date": str(row[9]) if row[9] else None,
                    "user_clock_in_time": "13:30",
                })
            return users
    except Exception as e:
        print(f"[DB] get_active_auto_absen_users error: {e}")
        return []
    finally:
        conn.close()


def record_attendance_result(
    username: str,
    absen_date: str,
    status: str,
    message: str = "",
) -> bool:
    """Record attendance execution log and update user last absen date."""
    conn = get_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE tb_user
            SET user_last_absen_date = %s,
                user_last_absen_status = %s,
                user_last_absen_log = %s,
                user_updated_at = CURRENT_TIMESTAMP
            WHERE user_username = %s;
            """,
            (absen_date, status, message, username),
        )
        cur.execute(
            """
            INSERT INTO tb_attendance_log (
                user_username, log_date, log_status, log_message
            ) VALUES (%s, %s, %s, %s);
            """,
            (username, absen_date, status, message),
        )
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"[DB] record_attendance_result error: {e}")
        return False
    finally:
        conn.close()


def get_recent_logs(username: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Get recent attendance audit logs for traceability."""
    conn = get_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT log_id, user_username, log_date, log_status, log_message, log_created_at
            FROM tb_attendance_log
            WHERE user_username = %s
            ORDER BY log_id DESC
            LIMIT %s;
            """,
            (username, limit),
        )
        rows = cur.fetchall()
        cur.close()
        logs = []
        for r in rows:
            created_val = r[5]
            if isinstance(created_val, datetime):
                # Neon Postgres TIMESTAMP disimpan dalam UTC, konversi ke WIB (+7 jam)
                wib_time = created_val + timedelta(hours=7)
                created_str = wib_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_str = str(created_val) if created_val else ""
            logs.append({
                "log_id": r[0],
                "username": r[1],
                "date": str(r[2]),
                "status": r[3],
                "message": r[4] or "",
                "created_at": created_str,
            })
        return logs
    except Exception as e:
        print(f"[DB] get_recent_logs error: {e}")
        return []
    finally:
        conn.close()
