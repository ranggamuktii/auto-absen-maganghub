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


if __name__ == "__main__":
    main()
