import json
from datetime import datetime
from pathlib import Path

from core import DOTFILES_DIR, detect_arch, detect_os

MANIFEST_DIR = Path.home() / ".local" / "share" / "dotfiles"
REPO_PATH = DOTFILES_DIR / "tools_management" / "manifest.json"
RUNTIME_PATH = MANIFEST_DIR / "manifest.json"


def create() -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "system": {"os": detect_os(), "arch": detect_arch()},
        "cli_tools": {"preexisting": [], "installed": []},
        "runtimes": {"preexisting": [], "installed": []},
        "fonts": {"preexisting": [], "installed": []},
        "stow": {"packages": [], "backups": {}},
        "post_install": {"tpm_installed": False, "windows_terminal_linked": False},
    }


def record_preexisting(manifest: dict, section: str, names: list[str]) -> None:
    existing = manifest.setdefault(section, {}).setdefault("preexisting", [])
    for name in names:
        if name not in existing:
            existing.append(name)


def record_installed(manifest: dict, section: str, names: list[str]) -> None:
    preexisting = manifest.get(section, {}).get("preexisting", [])
    installed = manifest.setdefault(section, {}).setdefault("installed", [])
    for name in names:
        if name in preexisting or name in installed:
            continue
        installed.append(name)


def get_uninstall_list(manifest: dict, section: str) -> list[str]:
    return list(manifest.get(section, {}).get("installed", []))


def update_timestamp(manifest: dict) -> None:
    manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")


def save(manifest: dict) -> None:
    update_timestamp(manifest)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, indent=2)
    RUNTIME_PATH.write_text(text)
    REPO_PATH.write_text(text)


def load() -> dict:
    for path in [RUNTIME_PATH, REPO_PATH]:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                print(f"   ⚠  Corrupt manifest at {path}, creating fresh one")
                continue
    return create()


def exists() -> bool:
    """Check if a manifest was previously saved to disk."""
    return RUNTIME_PATH.exists() or REPO_PATH.exists()


def saved_version() -> dict | None:
    """Load only an existing manifest (returns None if never saved)."""
    for path in [RUNTIME_PATH, REPO_PATH]:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                print(f"   ⚠  Corrupt manifest at {path}, ignoring")
                continue
    return None


def delete() -> None:
    for path in [RUNTIME_PATH, REPO_PATH]:
        if path.exists():
            path.unlink()
