#!/usr/bin/env python3
"""
sync_windows_term.py — Bidirectional sync for Windows Terminal settings.json.

Compares modification times between the stow-managed settings.json and the
Windows Terminal LocalState copy. Copies the newer one over the older one.

Usage:
  sync_windows_term.py              # auto-detect paths, sync newer → older
  sync_windows_term.py --dry-run    # show what would happen without writing
  sync_windows_term.py --help       # this message
"""

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DOTFILES_DIR = SCRIPT_DIR.parents[3]
STOW_SOURCE = DOTFILES_DIR / "stow-packages" / "windows-terminal" / "settings.json"


def find_wt_target() -> Path | None:
    users_dir = Path("/mnt/c/Users")
    if not users_dir.is_dir():
        return None
    for wt_settings in users_dir.rglob("*/LocalState/settings.json"):
        if "WindowsTerminal" in str(wt_settings):
            return wt_settings
    return None


def sync(dry_run: bool) -> int:
    if not STOW_SOURCE.is_file():
        print(f"❌ Stow source not found: {STOW_SOURCE}", file=sys.stderr)
        return 1

    wt_target = find_wt_target()
    if wt_target is None:
        print(
            "❌ Windows Terminal settings.json not found under /mnt/c/Users\n"
            "   Make sure /mnt/c is mounted and Windows Terminal has been\n"
            "   opened at least once.",
            file=sys.stderr,
        )
        return 1

    print(f"  Stow source: {STOW_SOURCE}")
    print(f"  WT target:   {wt_target}")

    stow_mtime = STOW_SOURCE.stat().st_mtime
    wt_mtime = wt_target.stat().st_mtime

    if stow_mtime == wt_mtime:
        print("✅ Both files are identical in age — no sync needed")
        return 0

    if stow_mtime > wt_mtime:
        newer, older, label = STOW_SOURCE, wt_target, "Stow source → Windows Terminal"
    else:
        newer, older, label = wt_target, STOW_SOURCE, "Windows Terminal → stow source"

    newer_time = newer.stat().st_mtime
    print(f"  → Newer: {newer.name} ({datetime.fromtimestamp(newer_time).strftime('%Y-%m-%d %H:%M:%S')})")
    print(f"  → Syncing: {label}")

    if dry_run:
        print("  (dry-run, skipped)")
        return 0

    backup = older.with_suffix(".json.bak")
    if backup.exists():
        backup = older.parent / f"{older.stem}.{time.time_ns()}.bak"
    shutil.copy2(older, backup)
    shutil.copy2(newer, older)
    print(f"  ✅ Synced. Backup saved as {backup.name}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bidirectional sync for Windows Terminal settings.json"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would happen without writing",
    )
    args = parser.parse_args()
    sys.exit(sync(args.dry_run))


if __name__ == "__main__":
    main()
