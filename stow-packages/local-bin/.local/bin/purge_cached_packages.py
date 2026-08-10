#!/usr/bin/env python3
"""
purge_cached_packages.py - Purge cached packages created by install.sh and stow-packages.

Removes the package caches that the dotfiles setup generates:
  - ~/.bun/install/cache/            bun install -g downloads (aggie, gemini)
  - ~/.npm/_cacache/                 npm/npx tarball downloads
  - ~/.cache/opencode/packages/      opencode plugin cache (quota, notifier, superpowers)
  - ~/.npm/_npx/                     npx-executed packages (playwright, mcp-neovim-server, untun)

These are re-downloaded automatically the next time the tool runs, so nothing
is permanently lost. Nothing is deleted until you confirm.

Usage:
  python3 purge_cached_packages.py [options]

Options:
  -n, --dry-run    Show what would be removed without actually removing anything
  -y, --yes        Skip confirmation prompt
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()

CACHE_DIRS = [
    ("bun install cache", HOME / ".bun" / "install" / "cache"),
    ("npm cacache", HOME / ".npm" / "_cacache"),
    ("opencode plugin cache", HOME / ".cache" / "opencode" / "packages"),
    ("npx cache", HOME / ".npm" / "_npx"),
]


def dir_size_bytes(path: Path) -> int:
    try:
        result = subprocess.run(
            ["du", "-sk", str(path)], capture_output=True, text=True, check=True
        )
        return int(result.stdout.split()[0]) * 1024
    except Exception:
        return 0


def human_size(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024 or unit == "TB":
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def discover() -> list[dict]:
    items = []
    for label, path in CACHE_DIRS:
        if not path.exists():
            continue
        items.append(
            {
                "label": label,
                "path": path,
                "size": dir_size_bytes(path),
                "display": f"  {label}: {path} ({human_size(dir_size_bytes(path))})",
            }
        )
    return items


def execute_removal(items: list[dict]) -> None:
    for item in items:
        try:
            print(f"  => Removing {item['label']}: {item['path']}")
            shutil.rmtree(item["path"])
        except Exception as e:
            print(f"  Warning: Could not remove {item['path']}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Purge cached packages created by install.sh and stow-packages.",
        epilog="Example: python3 purge_cached_packages.py --dry-run",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompt"
    )
    args = parser.parse_args()

    print("Scanning package caches...\n")
    items = discover()
    for item in items:
        print(item["display"])

    if not items:
        print("\nNo cached packages found. Nothing to do.")
        sys.exit(0)

    total = sum(item["size"] for item in items)
    print(f"\n{'=' * 60}")
    print(f"Found {len(items)} cache directories, {human_size(total)} to free")

    if args.dry_run:
        print("Dry-run mode enabled. No changes were made.")
        sys.exit(0)

    if not args.yes:
        confirm = input("Proceed with removal? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    print("\nRemoving cached packages...")
    execute_removal(items)
    print("\nDone. Caches will be re-downloaded on the next use.")


if __name__ == "__main__":
    main()
