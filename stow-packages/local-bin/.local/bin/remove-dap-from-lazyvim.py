#!/usr/bin/env python3
"""
Remove all traces of nvim-dap (core + python) from a LazyVim installation.

Handles:
  - lazyvim.json       : extras array
  - lazy-lock.json     : plugin pin entries
  - pkg-cache.lua      : rockspec-driven package cache
  - plugin directories : ~/.local/share/nvim/lazy/nvim-dap*
"""

import json
import shutil
import sys
from pathlib import Path

NVIM_CONFIG = Path.home() / ".config" / "nvim"
NVIM_DATA = Path.home() / ".local" / "share" / "nvim"
NVIM_STATE = Path.home() / ".local" / "state" / "nvim"

DAP_EXTRAS = {
    "lazyvim.plugins.extras.dap.core",
    "lazyvim.plugins.extras.dap.python",
}

DAP_LOCK_PREFIXES = (
    '"nvim-dap"',
    '"nvim-dap-python"',
    '"nvim-dap-ui"',
    '"nvim-dap-virtual-text"',
)


def log(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def skip(msg: str) -> None:
    print(f"[SKIP] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)


# --- lazyvim.json -----------------------------------------------------------


def clean_lazyvim_json(path: Path) -> bool:
    if not path.exists():
        skip(f"{path} not found")
        return False

    with open(path, "r") as fh:
        data = json.load(fh)

    extras = data.get("extras", [])
    before = len(extras)
    kept = [e for e in extras if e not in DAP_EXTRAS]
    after = len(kept)

    if before == after:
        skip("no dap extras in lazyvim.json")
        return False

    data["extras"] = kept
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    ok(f"removed {before - after} dap extra(s) from lazyvim.json")
    return True


# --- lazy-lock.json ---------------------------------------------------------


def clean_lazy_lock(path: Path) -> bool:
    if not path.exists():
        skip(f"{path} not found")
        return False

    with open(path, "r") as fh:
        lines = fh.readlines()

    new_lines = []
    removed = 0
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in DAP_LOCK_PREFIXES):
            removed += 1
            continue
        new_lines.append(line)

    if removed == 0:
        skip("no dap entries in lazy-lock.json")
        return False

    with open(path, "w") as fh:
        fh.writelines(new_lines)
    ok(f"removed {removed} dap line(s) from lazy-lock.json")
    return True


# --- pkg-cache.lua ----------------------------------------------------------


def clean_pkg_cache(path: Path) -> bool:
    if not path.exists():
        skip(f"{path} not found")
        return False

    path.unlink()
    ok(f"removed {path}")
    return True


# --- plugin directories -----------------------------------------------------


def clean_plugin_dirs(base: Path) -> bool:
    if not base.exists():
        skip(f"{base} not found")
        return False

    removed_any = False
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        if "dap" in entry.name.lower():
            shutil.rmtree(entry)
            ok(f"removed {entry}")
            removed_any = True

    if not removed_any:
        skip("no dap plugin directories found")
    return removed_any


# --- main -------------------------------------------------------------------


def main() -> None:
    lazy_dir = NVIM_DATA / "lazy"

    print("Removing nvim-dap from LazyVim …\n")

    clean_lazyvim_json(NVIM_CONFIG / "lazyvim.json")
    clean_lazy_lock(NVIM_CONFIG / "lazy-lock.json")
    clean_pkg_cache(NVIM_STATE / "lazy" / "pkg-cache.lua")
    clean_plugin_dirs(lazy_dir)

    print("\nDone. Restart Neovim for changes to take effect.")


if __name__ == "__main__":
    main()
