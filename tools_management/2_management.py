#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config as cfg
import core
import manifest as mf
from cli_tools import install_cli_tools
from core import DOTFILES_DIR, detect_arch, detect_os, is_wsl
from fonts import install_fonts
from git_setup import git_setup
from npm_packages import install_npm_packages
from post_install import run_post_install
from runtimes import install_runtimes
from stow import resolve_stow_plan, stow_packages
from system_packages import install_system_packages
from verify import verify


def banner(text: str) -> None:
    print(f"\n═══ {text} ═══")


INSTALL_STEPS = [
    ("System packages", install_system_packages),
    ("CLI tools", install_cli_tools),
    ("Fonts", install_fonts),
    ("Stow symlinks", stow_packages),
    ("Git config", git_setup),
    ("Runtimes", install_runtimes),
    ("NPM packages", install_npm_packages),
    ("Post-install", run_post_install),
    ("Verification", verify),
]

UNINSTALL_STEPS = [
    ("Post-install", run_post_install),
    ("NPM packages", install_npm_packages),
    ("Runtimes", install_runtimes),
    ("Git config", git_setup),
    ("Stow symlinks", stow_packages),
    ("Fonts", install_fonts),
    ("CLI tools", install_cli_tools),
    ("Verification", verify),
]


def print_summary(conf: dict) -> None:
    print()
    print("  The following will be installed:")
    tools = list(conf.get("cli_tools", {}).keys())
    if tools:
        print(f"  • CLI tools: {', '.join(tools)}")
    npm_pkgs = list(conf.get("npm_packages", {}).keys())
    if npm_pkgs:
        print(f"  • NPM packages: {', '.join(npm_pkgs)}")
    runtimes = [k for k, v in conf.get("runtimes", {}).items() if v]
    if runtimes:
        print(f"  • Runtimes: {', '.join(runtimes)}")
    font = conf.get("terminal_font", "")
    if font:
        print(f"  • Terminal font: {font} Nerd Font")
    stow_cfg = conf.get("stow", {})
    terminals = []
    if stow_cfg.get("ghostty_or_windowsTerminal"):
        terminals.append("ghostty" if not is_wsl() else "windows-terminal")
    if stow_cfg.get("alacritty"):
        terminals.append("alacritty")
    if stow_cfg.get("wezterm"):
        terminals.append("wezterm")
    if terminals:
        print(f"  • Terminals: {', '.join(terminals)}")
    print()


def should_skip_step(label: str, plan: set[str], config: dict) -> bool:
    base = set(config.get("base_steps", []))
    if label in base:
        return False
    if label == "Verification":
        return True
    step_deps = config.get("step_deps", {})
    needs = set(step_deps.get(label, []))
    return not (needs & plan)


def cmd_check() -> None:
    conf = cfg.load()

    print("========================================")
    print("  🔍 Dotfiles Check (dry-run)")
    print("========================================")

    os_name = detect_os()
    wsl = is_wsl()
    print(f"   OS: {os_name}{' (WSL)' if wsl else ''}")
    print(f"   Arch: {detect_arch()}")
    print()

    print_summary(conf)

    for label, fn in INSTALL_STEPS:
        if label == "Verification":
            continue
        banner(label)
        try:
            fn(conf, mode="check")
        except Exception as e:
            print(f"   ⚠  {label} check failed — continuing. ({e})")

    banner("Verification")
    verify(conf, mode="install")

    print("✅ Check complete — no changes made.\n")


def cmd_install(args: argparse.Namespace) -> None:
    if args.check:
        cmd_check()
        return

    if args.interactive:
        core.INTERACTIVE = True

    conf = cfg.load()

    if args.just:
        core.STOW_PLAN = resolve_stow_plan(conf, args.just)
        print(f"📦 Resolved plan: {', '.join(sorted(core.STOW_PLAN))}")

    print("========================================")
    print("  🚀 Dotfiles Bootstrap")
    print("========================================")

    os_name = detect_os()
    wsl = is_wsl()
    print(f"   OS: {os_name}{' (WSL)' if wsl else ''}")
    print(f"   Arch: {detect_arch()}")
    print()

    if core.INTERACTIVE:
        print_summary(conf)

    changed = mf.changed_steps(conf)

    base_steps = set(conf.get("base_steps", []))

    for label, fn in INSTALL_STEPS:
        if core.STOW_PLAN is not None and should_skip_step(label, core.STOW_PLAN, conf):
            print(f"   (skipped — not needed by {', '.join(args.just)})")
            continue
        if not args.force and core.STOW_PLAN is None and label not in changed and label != "Verification":
            print("   (config unchanged — skipping)")
            continue
        if core.INTERACTIVE and not core.confirm(f"▶ {label}?"):
            continue
        banner(label)
        try:
            fn(conf, mode="install")
        except Exception as e:
            if label in base_steps:
                print(f"❌ {label} failed — aborting. ({e})")
                sys.exit(1)
            print(f"   ⚠  {label} failed — continuing. ({e})")

    mf.store_config_snapshot(conf)
    print("✅ Done!")
    print("   - Open Neovim so Lazy can install plugins")
    print("   - In tmux, press Prefix + I to install TPM plugins")
    print()
    stow_dirs = sorted(
        p.name for p in DOTFILES_DIR.joinpath("stow-packages").iterdir() if p.is_dir()
    )
    print(f"📦 Stow packages active: {', '.join(stow_dirs)}")
    font = conf.get("terminal_font", "")
    if font:
        print(f"🔤 Terminal font: {font} Nerd Font")
    stow_cfg = conf.get("stow", {})
    terminals = []
    if stow_cfg.get("ghostty_or_windowsTerminal"):
        terminals.append("windows-terminal" if wsl else "ghostty")
    if stow_cfg.get("alacritty"):
        terminals.append("alacritty")
    if stow_cfg.get("wezterm"):
        terminals.append("wezterm")
    if terminals:
        print(f"🖥️  Terminals: {', '.join(terminals)}")


def cmd_uninstall(args: argparse.Namespace) -> None:
    if args.interactive:
        core.INTERACTIVE = True

    if not mf.exists():
        print("❌ No manifest found. Nothing to uninstall.")
        sys.exit(1)

    print("========================================")
    print("  🗑  Dotfiles Uninstall")
    print("========================================")

    manifest = mf.saved_version()
    if manifest is None:
        print("❌ Manifest file corrupt or unreadable. Cannot uninstall.")
        sys.exit(1)
    print(f"   System: {manifest['system']['os']} / {manifest['system']['arch']}")
    print(f"   Installed at: {manifest['created_at']}")
    print()

    if not args.force:
        print("⚠️  This will remove dotfiles symlinks, CLI tools, runtimes, and fonts.")
        try:
            confirm = input("  Are you sure? [y/N] ").strip().lower()
            if confirm not in ("y", "yes"):
                print("  Aborted.")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\n  Aborted.")
            sys.exit(0)

    conf = cfg.load()

    if args.just:
        core.STOW_PLAN = set(args.just)

    for label, fn in UNINSTALL_STEPS:
        if core.STOW_PLAN is not None and label != "Stow symlinks":
            print("   (skipped — --just mode)")
            continue
        if core.INTERACTIVE and not core.confirm(f"▶ {label}?"):
            continue
        banner(label)
        fn(conf, mode="uninstall")

    if not args.just:
        mf.delete()
    print("✅ Uninstall complete!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dotfiles management tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Install dotfiles")
    install_parser.add_argument(
        "-i", "--interactive", action="store_true", help="ask before each step"
    )
    install_parser.add_argument(
        "-f", "--force", action="store_true", help="run all steps even if config unchanged"
    )
    install_parser.add_argument(
        "--check",
        action="store_true",
        help="validate config and show plan without making changes",
    )
    install_parser.add_argument(
        "--just",
        nargs="+",
        metavar="PKG",
        help="only stow specified packages + deps + base",
    )

    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall dotfiles")
    uninstall_parser.add_argument(
        "-f", "--force", action="store_true", help="skip confirmation prompt"
    )
    uninstall_parser.add_argument(
        "-i", "--interactive", action="store_true", help="ask before each step"
    )
    uninstall_parser.add_argument(
        "--just",
        nargs="+",
        metavar="PKG",
        help="only unstow specified packages + restore their backups",
    )

    args = parser.parse_args()

    if args.command == "install":
        cmd_install(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)


if __name__ == "__main__":
    main()
