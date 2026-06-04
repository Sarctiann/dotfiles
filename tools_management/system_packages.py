import time
from pathlib import Path

import core
from core import detect_os, run, which


def _install_brew(packages: list[str]) -> None:
    if not which("brew"):
        print("⚠️  Homebrew not found")
        return
    run(["brew", "update"])
    run(["brew", "install", *packages])


def _install_apt(packages: list[str]) -> None:
    lists_dir = Path("/var/lib/apt/lists")
    stale = True
    if lists_dir.is_dir():
        files = [f for f in lists_dir.iterdir() if f.is_file()]
        if files:
            oldest = min(f.stat().st_mtime for f in files)
            stale = (time.time() - oldest) > 3600
    if stale:
        run(["sudo", "apt", "update"])
    run(["sudo", "apt", "install", "-y", *packages])


def _install_pacman(packages: list[str]) -> None:
    run(["sudo", "pacman", "-Syu", "--noconfirm", *packages])


def _install_dnf(packages: list[str]) -> None:
    run(["sudo", "dnf", "install", "-y", *packages])


def install_system_packages(config: dict, mode: str = "install") -> None:
    if mode == "uninstall":
        print("   (system packages are not removed)")
        return
    pkgs = list(config.get("system_packages", []))
    plan = core.STOW_PLAN
    for pkg, needs in config.get("conditional_system_packages", {}).items():
        if plan is None or set(needs) & plan:
            pkgs.append(pkg)
    if not pkgs:
        return

    os_name = detect_os()

    if mode == "check":
        pm = {"macos": "brew", "linux": "apt/pacman/dnf"}.get(os_name, "?")
        print(f"📦 System packages (via {pm}):")
        for pkg in pkgs:
            status = "✅" if which(pkg) else "⬜"
            print(f"   {status} {pkg}")
        print()
        return

    print("📦 Installing system packages...")

    match os_name:
        case "macos":
            _install_brew(pkgs)
        case "linux":
            if which("apt"):
                _install_apt(pkgs)
            elif which("pacman"):
                _install_pacman(pkgs)
            elif which("dnf"):
                _install_dnf(pkgs)
            else:
                print("⚠️  No supported package manager found")
    print()
