"""Database operations with PostgreSQL (Neon Serverless)."""

import os
import ssl
from datetime import date
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import pg8000.dbapi


def get_db_url() -> str:
    """Get Postgres database URL from environment."""
    return (
        os.environ.get("POSTGRES_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_PRISMA_URL")
        or ""
    ).strip()


def get_connection():
    """Create a connection to Neon PostgreSQL using pg8000."""
    url = get_db_url()
    if not url:
        return None

    # Handle postgres:// scheme if provided by some providers
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    parsed = urlparse(url)
    ssl_context = None
    if "sslmode=require" in url or (parsed.hostname and "neon.tech" in parsed.hostname):
        ssl_context = ssl.create_default_context()

    port = parsed.port or 5432
    return pg8000.dbapi.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=port,
        database=parsed.path.lstrip("/"),
        ssl_context=ssl_context,
        timeout=15,
    )


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
                user_location VARCHAR(100) DEFAULT 'Jakarta',
                user_latitude NUMERIC(10, 6) DEFAULT -6.208800,
                user_longitude NUMERIC(10, 6) DEFAULT 106.845600,
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
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        print(f"[DB] Init error: {e}")
        return False
    finally:
        conn.close()


def save_or_update_user(
    username: str,
    password: str,
    location: str = "Jakarta",
    latitude: float = -6.208800,
    longitude: float = 106.845600,
    activity_log: str = "",
    lesson_learned: str = "",
    obstacles: str = "",
    auto_absen: bool = True,
) -> bool:
    """Save or update user settings in the database."""
    conn = get_connection()
    if not conn:
        return False

    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO tb_user (
                user_username, user_password, user_location,
                user_latitude, user_longitude, user_activity_log,
                user_lesson_learned, user_obstacles, user_auto_absen,
                user_updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_username) DO UPDATE SET
                user_password = EXCLUDED.user_password,
                user_location = EXCLUDED.user_location,
                user_latitude = EXCLUDED.user_latitude,
                user_longitude = EXCLUDED.user_longitude,
                user_activity_log = EXCLUDED.user_activity_log,
                user_lesson_learned = EXCLUDED.user_lesson_learned,
                user_obstacles = EXCLUDED.user_obstacles,
                user_auto_absen = EXCLUDED.user_auto_absen,
                user_updated_at = CURRENT_TIMESTAMP;
            """,
            (
                username,
                password,
                location,
                latitude,
                longitude,
                activity_log,
                lesson_learned,
                obstacles,
                auto_absen,
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


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve user settings by username."""
    conn = get_connection()
    if not conn:
        return None

    try:
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

        return {
            "user_id": row[0],
            "user_username": row[1],
            "user_password": row[2],
            "user_location": row[3],
            "user_latitude": float(row[4]) if row[4] is not None else -6.208800,
            "user_longitude": float(row[5]) if row[5] is not None else 106.845600,
            "user_activity_log": row[6] or "",
            "user_lesson_learned": row[7] or "",
            "user_obstacles": row[8] or "",
            "user_auto_absen": bool(row[9]),
            "user_last_absen_date": str(row[10]) if row[10] else None,
            "user_last_absen_status": row[11] or "",
            "user_last_absen_log": row[12] or "",
        }
    except Exception as e:
        print(f"[DB] get_user error: {e}")
        return None
    finally:
        conn.close()


def get_active_auto_absen_users() -> List[Dict[str, Any]]:
    """Get all users who have enabled auto-absen."""
    conn = get_connection()
    if not conn:
        return []

    try:
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
            users.append({
                "user_id": row[0],
                "user_username": row[1],
                "user_password": row[2],
                "user_location": row[3],
                "user_latitude": float(row[4]) if row[4] is not None else -6.208800,
                "user_longitude": float(row[5]) if row[5] is not None else 106.845600,
                "user_activity_log": row[6] or "",
                "user_lesson_learned": row[7] or "",
                "user_obstacles": row[8] or "",
                "user_last_absen_date": str(row[9]) if row[9] else None,
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
