"""Network error handling and retry helpers."""

import functools
import time

import requests

from app.utils.log import log
from app.utils.whatsapp import log_notify

MAX_ATTEMPTS = 3
RETRY_DELAY = 60  # seconds


def net_msg(e: Exception) -> str:
    """Return a message for a network error.

    Args:
        e: The caught exception.
    """
    if isinstance(e, requests.exceptions.Timeout):
        return "[FAIL] Koneksi timeout."
    return "[FAIL] Gagal terhubung ke server. Cek koneksi internet."


def network_guard(func):
    """Catch network errors, log and notify, and return exit code 1.

    Args:
        func: Command function returning an exit code.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            log_notify(net_msg(e))
            return 1
        except Exception as e:
            log_notify(f"[FAIL] {e}")
            return 1
    return wrapper


def retryable(e: Exception) -> bool:
    """Return True if the error is transient and worth retrying.

    Args:
        e: The caught exception.
    """
    if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    status = getattr(e, "status_code", None)
    return isinstance(status, int) and 500 <= status <= 599


def with_retry(label: str, func):
    """Run func, retrying transient errors. Raise on final failure.

    Args:
        label: Name shown in retry warnings.
        func: Zero-argument callable to run.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return func()
        except Exception as e:
            if not retryable(e) or attempt == MAX_ATTEMPTS:
                raise
            log(f"[WARN] {label} gagal (percobaan {attempt}/{MAX_ATTEMPTS}). Coba lagi dalam {RETRY_DELAY} detik.")
            time.sleep(RETRY_DELAY)
