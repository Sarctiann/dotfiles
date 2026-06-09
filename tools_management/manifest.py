import hashlib
import json
from datetime import datetime
from pathlib import Path

from core import DOTFILES_DIR, detect_arch, detect_os

MANIFEST_DIR = Path.home() / ".local" / "share" / "dotfiles"
MANIFEST_PATH = MANIFEST_DIR / "manifest.json"
ROOT_MANIFEST_PATH = DOTFILES_DIR / "dotfiles-manifest.json"


def create() -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "version": 1,
        "created_at": now,
        "updated_at": now,
        "system": {"os": detect_os(), "arch": detect_arch()},
        "cli_tools": {"preexisting": [], "installed": []},
        "npm_packages": {"preexisting": [], "installed": []},
        "runtimes": {"preexisting": [], "installed": []},
        "fonts": {"preexisting": [], "installed": []},
        "stow": {"packages": [], "backups": {}},
        "post_install": {
            "tpm_installed": False,
            "windows_terminal_linked": False,
            "zsh_plugins_installed": [],
        },
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
    payload = json.dumps(manifest, indent=2)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(payload)
    ROOT_MANIFEST_PATH.write_text(payload)


def load() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except json.JSONDecodeError:
            print("   ⚠  Corrupt manifest, creating fresh one")
    return create()


def exists() -> bool:
    return MANIFEST_PATH.exists()


def saved_version() -> dict | None:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return None


def delete() -> None:
    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()


STEP_CONFIG_KEYS: dict[str, list[str]] = {
    "System packages": ["system_packages", "conditional_system_packages"],
    "CLI tools": ["cli_tools"],
    "Fonts": ["fonts"],
    "Stow symlinks": ["stow"],
    "Git config": [],
    "Runtimes": ["runtimes"],
    "NPM packages": ["npm_packages"],
    "Post-install": ["post_install"],
}


def _hash_config_subset(config: dict, keys: list[str]) -> str:
    sub = {k: config.get(k) for k in keys}
    return hashlib.sha256(
        json.dumps(sub, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]


def store_config_snapshot(config: dict) -> dict:
    manifest = load()
    snapshot = manifest.setdefault("config_snapshot", {})
    for step, keys in STEP_CONFIG_KEYS.items():
        snapshot[step] = _hash_config_subset(config, keys)
    save(manifest)
    return manifest


def changed_steps(config: dict) -> set[str]:
    manifest = saved_version()
    if not manifest:
        return set(STEP_CONFIG_KEYS.keys())
    snapshot = manifest.get("config_snapshot", {})
    return {
        step
        for step, keys in STEP_CONFIG_KEYS.items()
        if snapshot.get(step) != _hash_config_subset(config, keys)
    }
