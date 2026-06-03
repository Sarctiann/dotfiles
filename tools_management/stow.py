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


def _backup_targets(pkg_name: str, manifest: dict, ignore_pats: list[str]) -> None:
    pkg_dir = STOW_DIR / pkg_name
    if not pkg_dir.is_dir():
        return
    backups = manifest.setdefault("stow", {}).setdefault("backups", {})
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
        backups[str(rel_path)] = str(backup_path)
        print(f"   (backed up {rel_path})")


def _restore_backups(manifest: dict) -> None:
    backups = manifest.get("stow", {}).get("backups", {})
    if not backups:
        return
    print("♻️  Restoring stow backups...")
    for rel_path, backup_path in backups.items():
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
    packages = manifest.get("stow", {}).get("packages", [])
    print("🗑  Removing stow symlinks...")
    for pkg_name in packages:
        pkg_dir = STOW_DIR / pkg_name
        if not pkg_dir.is_dir():
            print(f"   ⚠  package '{pkg_name}' not found, skipping")
            continue
        print(f"   → {pkg_name}")
        run_optional(
            ["stow", "-D", "-t", str(Path.home()), pkg_name], cwd=str(STOW_DIR)
        )
    _restore_backups(manifest)
    manifest["stow"] = {"packages": [], "backups": {}}
    mf.save(manifest)


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
    terminal = config.get("stow", {}).get("terminal", "ghostty")
    wsl = is_wsl()

    if plan is None:
        candidates = sorted(p.name for p in STOW_DIR.iterdir() if p.is_dir())
    else:
        candidates = sorted(plan)

    manifest = mf.load()

    print("🔗 Creating symlinks with stow...")

    manifest["stow"]["packages"] = []

    for pkg_name in candidates:
        if plan is None:
            if pkg_name in ("ghostty", "alacritty", "wezterm"):
                if wsl:
                    print(f"   (skipped {pkg_name} — WSL)")
                    continue
                if pkg_name != terminal:
                    print(f"   (skipped {pkg_name} — using {terminal})")
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


def stow_windows_terminal() -> None:
    pkg_dir = STOW_DIR / "windows-terminal"
    if not pkg_dir.is_dir():
        return

    wt_glob = list(
        Path("/mnt/c/Users").glob(
            "*/AppData/Local/Packages/Microsoft.WindowsTerminal_*"
        )
    )
    if not wt_glob:
        print("⚠️  Windows Terminal folder not found. Link manually:")
        print(
            f"   {pkg_dir / 'settings.json'} → %LOCALAPPDATA%\\Packages\\Microsoft.WindowsTerminal_*\\LocalState\\settings.json"
        )
        return

    target = wt_glob[0] / "LocalState" / "settings.json"

    if target.is_file() and not target.is_symlink():
        bak = target.with_suffix(".json.bak")
        target.rename(bak)
        print(f"   (backed up existing settings.json → {bak.name})")

    target.symlink_to(pkg_dir / "settings.json")
    print(f"   → windows-terminal: linked to {target}")
