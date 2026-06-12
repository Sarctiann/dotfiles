import json
import re
import shutil
from pathlib import Path, PurePosixPath

import manifest as mf
from core import DOTFILES_DIR, STOW_DIR, is_wsl, run, run_optional, which
import core

BACKUP_DIR = Path.home() / ".local" / "share" / "dotfiles" / "backups"
STOWIGNORE_PATH = DOTFILES_DIR / ".stowignore"


def _load_stowignore() -> list[str]:
    if not STOWIGNORE_PATH.exists():
        return []
    patterns = []
    for line in STOWIGNORE_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _glob_to_stow_regex(pattern: str) -> str:
    parts = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                if i == 0 and i + 2 < len(pattern) and pattern[i + 2] == "/":
                    i += 3
                    continue
                parts.append(".*")
                i += 2
            else:
                parts.append("[^/]*")
                i += 1
        else:
            parts.append(re.escape(c))
            i += 1
    return f"(?:.*/)?{''.join(parts)}$"


def _is_ignored(rel_path: str, ignore_patterns: list[str]) -> bool:
    p = PurePosixPath(rel_path)
    for pat in ignore_patterns:
        if p.match(pat):
            return True
    return False


def resolve_stow_plan(config: dict, requested: list[str]) -> set[str]:
    deps = config.get("stow", {}).get("deps", {})
    base = set(config.get("stow", {}).get("base", []))
    plan = set(requested)
    changed = True
    while changed:
        changed = False
        for pkg in list(plan):
            for dep in deps.get(pkg, []):
                if dep not in plan:
                    plan.add(dep)
                    changed = True
    return plan | base


def _migrate_backups_flat_to_per_pkg(manifest: dict) -> None:
    raw = manifest.get("stow", {}).get("backups", {})
    if not raw or any(isinstance(v, dict) for v in raw.values()):
        return
    pkgs = manifest.get("stow", {}).get("packages", [])
    old = dict(raw)
    raw.clear()
    for rel_path, backup_path in old.items():
        bp = Path(backup_path)
        for pkg in pkgs:
            if (BACKUP_DIR / pkg) in bp.parents:
                raw.setdefault(pkg, {})[rel_path] = backup_path
                break
        else:
            raw.setdefault("_unknown", {})[rel_path] = backup_path


def _backup_targets(pkg_name: str, manifest: dict, ignore_pats: list[str]) -> None:
    pkg_dir = STOW_DIR / pkg_name
    if not pkg_dir.is_dir():
        return
    backups = manifest.setdefault("stow", {}).setdefault("backups", {})
    _migrate_backups_flat_to_per_pkg(manifest)
    for filepath in pkg_dir.rglob("*"):
        if not filepath.is_file() or filepath.is_symlink():
            continue
        rel_path = filepath.relative_to(pkg_dir)
        if _is_ignored(str(rel_path), ignore_pats):
            continue
        target = Path.home() / rel_path
        if not target.exists() or target.is_symlink():
            continue
        if STOW_DIR in target.resolve().parents:
            continue
        backup_path = BACKUP_DIR / pkg_name / rel_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup_path)
        target.unlink()
        backups.setdefault(pkg_name, {})[str(rel_path)] = str(backup_path)
        print(f"   (backed up {rel_path})")


def _restore_backups(manifest: dict, packages: set[str] | None = None) -> None:
    raw = manifest.get("stow", {}).get("backups", {})
    if not raw:
        return
    _migrate_backups_flat_to_per_pkg(manifest)
    print("♻️  Restoring stow backups...")
    for pkg_name, pkg_backups in raw.items():
        if packages is not None and pkg_name not in packages:
            continue
        for rel_path, backup_path in pkg_backups.items():
            target = Path.home() / rel_path
            backup = Path(backup_path)
            if backup.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, target)
                backup.unlink()
                print(f"   (restored {rel_path})")
            else:
                print(f"   ⚠  backup not found: {backup_path}")
    if BACKUP_DIR.is_dir():
        for pkg_dir in sorted(BACKUP_DIR.iterdir(), reverse=True):
            if pkg_dir.is_dir():
                for dirpath, dirnames, filenames in sorted(
                    pkg_dir.walk(top_down=False), reverse=True
                ):
                    for f in filenames:
                        (dirpath / f).unlink()
                    for d in dirnames:
                        (dirpath / d).rmdir()
                if not any(pkg_dir.rglob("*")):
                    pkg_dir.rmdir()


def _uninstall_stow(_: dict) -> None:
    manifest = mf.saved_version()
    if not manifest:
        print("⚠️  No manifest found. Nothing to uninstall.")
        return
    packages: list[str] = manifest.get("stow", {}).get("packages", [])
    plan = core.STOW_PLAN

    if plan is not None:
        to_unstow = sorted(set(packages) & plan)
        if not to_unstow:
            print("   (no matching packages in manifest)")
            return
        print(f"🗑  Removing stow symlinks ({', '.join(to_unstow)})...")
    else:
        to_unstow = packages
        print("🗑  Removing stow symlinks...")

    for pkg_name in to_unstow:
        pkg_dir = STOW_DIR / pkg_name
        if not pkg_dir.is_dir():
            print(f"   ⚠  package '{pkg_name}' not found, skipping")
            continue
        print(f"   → {pkg_name}")
        run_optional(
            ["stow", "-D", "-t", str(Path.home()), pkg_name], cwd=str(STOW_DIR)
        )

    _restore_backups(manifest, packages=plan)

    if plan is not None:
        manifest["stow"]["packages"] = [p for p in packages if p not in plan]
        for pkg in plan:
            manifest["stow"]["backups"].pop(pkg, None)
    else:
        manifest["stow"] = {"packages": [], "backups": {}}
    mf.save(manifest)


def _validate_packages(candidates: list[str]) -> None:
    warned = False
    for pkg in candidates:
        if pkg == "windows-terminal":
            continue
        pkg_dir = STOW_DIR / pkg
        if not pkg_dir.is_dir():
            continue
        for entry in pkg_dir.iterdir():
            if entry.is_file() and not entry.name.startswith("."):
                print(
                    f"   ⚠  {pkg}: {entry.name} at root — would symlink to ~/{entry.name}"
                )
                warned = True
    if warned:
        print("   ℹ️  Stow packages should have dotfiles or subdirectories at root")


def _config_package_diff(config: dict) -> None:
    stow_cfg = config.get("stow", {})
    known = set(stow_cfg.get("deps", {}).keys()) | set(stow_cfg.get("base", []))
    on_disk = {p.name for p in STOW_DIR.iterdir() if p.is_dir()}

    missing_on_disk = known - on_disk
    for pkg in sorted(missing_on_disk):
        print(f"   ⚠  config references '{pkg}' but no directory in stow-packages/")

    unknown_in_dir = on_disk - known
    for pkg in sorted(unknown_in_dir):
        print(
            f"   ⚠  stow-packages/{pkg} exists but not mentioned in config stow.deps"
        )


def stow_packages(config: dict, mode: str = "install") -> None:
    if mode == "uninstall":
        _uninstall_stow(config)
        return

    if not config.get("stow", {}).get("enabled", True):
        return

    if not which("stow"):
        print("❌ stow is not installed. Cannot create symlinks.")
        return

    ignore_pats = _load_stowignore()

    plan = core.STOW_PLAN
    stow_cfg = config.get("stow", {})
    ghostty_enabled = stow_cfg.get("ghostty_or_windowsTerminal", True)
    alacritty_enabled = stow_cfg.get("alacritty", False)
    wezterm_enabled = stow_cfg.get("wezterm", False)
    wsl = is_wsl()

    if plan is None:
        candidates = sorted(p.name for p in STOW_DIR.iterdir() if p.is_dir())
    else:
        candidates = sorted(plan)

    manifest = mf.load()

    _validate_packages(candidates)
    _config_package_diff(config)

    if mode == "check":
        print("🔗 Stow symlinks (dry-run):")
        for pkg_name in candidates:
            if plan is None:
                if pkg_name == "ghostty":
                    if wsl or not ghostty_enabled:
                        print(f"   (skipped {pkg_name} — {'WSL' if wsl else 'not selected'})")
                        continue
                elif pkg_name == "alacritty":
                    if not alacritty_enabled:
                        print(f"   (skipped {pkg_name} — not selected)")
                        continue
                elif pkg_name == "wezterm":
                    if not wezterm_enabled:
                        print(f"   (skipped {pkg_name} — not selected)")
                        continue
            if pkg_name == "windows-terminal":
                continue
            pkg_dir = STOW_DIR / pkg_name
            if not pkg_dir.is_dir():
                print(f"   ⚠  package '{pkg_name}' not found")
                continue
            print(f"   → {pkg_name}")
            stow_args = ["stow", "--no", "-v", "-R", "-t", str(Path.home())]
            for pat in ignore_pats:
                stow_args += ["--ignore", _glob_to_stow_regex(pat)]
            stow_args.append(pkg_name)
            run_optional(stow_args, cwd=str(STOW_DIR))
        print()
        return

    print("🔗 Creating symlinks with stow...")

    manifest["stow"]["packages"] = []

    for pkg_name in candidates:
        if plan is None:
            if pkg_name == "ghostty":
                if wsl or not ghostty_enabled:
                    print(f"   (skipped {pkg_name} — {'WSL' if wsl else 'not selected'})")
                    continue
            elif pkg_name == "alacritty":
                if not alacritty_enabled:
                    print(f"   (skipped {pkg_name} — not selected)")
                    continue
            elif pkg_name == "wezterm":
                if not wezterm_enabled:
                    print(f"   (skipped {pkg_name} — not selected)")
                    continue
        if pkg_name == "windows-terminal":
            continue

        pkg_dir = STOW_DIR / pkg_name
        if not pkg_dir.is_dir():
            print(f"   ⚠  package '{pkg_name}' not found in stow-packages")
            continue

        _backup_targets(pkg_name, manifest, ignore_pats)
        print(f"   → {pkg_name}")
        stow_args = ["stow", "-R", "-t", str(Path.home())]
        for pat in ignore_pats:
            stow_args += ["--ignore", _glob_to_stow_regex(pat)]
        stow_args.append(pkg_name)
        run(stow_args, cwd=str(STOW_DIR))

        stow_pkgs = manifest.setdefault("stow", {}).setdefault("packages", [])
        if pkg_name not in stow_pkgs:
            stow_pkgs.append(pkg_name)

    mf.save(manifest)


def _patch_wt_font(settings: dict, font_base: str) -> None:
    """Patch the font family in a windows-terminal settings dict."""
    full = f"{font_base} Nerd Font Propo"
    for profile in settings.get("profiles", {}).get("list", []):
        if "font" in profile:
            profile["font"]["face"] = full


def stow_windows_terminal(terminal_font: str | None = None) -> None:
    pkg_dir = STOW_DIR / "windows-terminal"
    if not pkg_dir.is_dir():
        return

    packages_dir = Path("/mnt/c/Users")
    if not packages_dir.is_dir():
        print("⚠️  /mnt/c/Users not found — is /mnt/c mounted?")
        print(f"   Copy manually: cp '{pkg_dir / 'settings.json'}' to Windows Terminal LocalState")
        return

    # Search for any Windows Terminal package folder
    wt_glob = list(packages_dir.glob("*/AppData/Local/Packages/*WindowsTerminal*"))
    if not wt_glob:
        print(f"   Searched: {packages_dir}/<user>/AppData/Local/Packages/*WindowsTerminal*")
        print("⚠️  Windows Terminal package folder not found.")
        print("   Open Windows Terminal once (it creates the folder), then re-run install.")
        print(f"   Or copy manually: cp '{pkg_dir / 'settings.json'}' to the LocalState folder inside the Windows Terminal package.")
        return

    wt_pkg = wt_glob[0]
    local_state = wt_pkg / "LocalState"
    local_state.mkdir(parents=True, exist_ok=True)
    target = local_state / "settings.json"

    print(f"   Found package: {wt_pkg.name}")
    print(f"   Settings path: {target}")

    # Remove broken symlink if one exists from a previous install
    if target.is_symlink():
        target.unlink()
        print("   (removed stale symlink)")

    # Back up existing file before copying
    backup_restored = False
    if target.is_file():
        bak = target.with_suffix(".json.bak")
        # Don't overwrite an existing backup — it's the user's original
        if not bak.exists():
            target.rename(bak)
            print(f"   (backed up existing settings.json → {bak.name})")
            backup_restored = True
        else:
            print(f"   (backup already exists at {bak.name})")

    try:
        source = pkg_dir / "settings.json"
        if terminal_font:
            wt_settings = json.loads(source.read_text())
            _patch_wt_font(wt_settings, terminal_font)
            target.write_text(json.dumps(wt_settings, indent=2))
            print(f"   ✓ Patched font to '{terminal_font}'")
        else:
            shutil.copy2(source, target)
        print(f"   ✓ Copied settings.json to {target}")
    except (OSError, PermissionError) as e:
        print(f"   ⚠  Could not copy Windows Terminal settings: {e}")
