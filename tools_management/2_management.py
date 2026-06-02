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
    ("Runtimes", install_runtimes),
    ("Post-install", run_post_install),
    ("Verification", verify),
]

UNINSTALL_STEPS = [
    ("Post-install", run_post_install),
    ("Runtimes", install_runtimes),
    ("Stow symlinks", stow_packages),
    ("Fonts", install_fonts),
    ("CLI tools", install_cli_tools),
    ("Verification", verify),
]


def print_summary(conf: dict) -> None:
    print()
    print("  The following will be installed:")
    tools = list(conf.get("cli_tools", {}).keys())
    print(f"  • CLI tools: {', '.join(tools)}")
    runtimes = [k for k, v in conf.get("runtimes", {}).items() if v]
    if runtimes:
        print(f"  • Runtimes: {', '.join(runtimes)}")
    if conf.get("fonts"):
        print(f"  • Fonts: {', '.join(conf['fonts'])}")
    print()


def should_skip_step(label: str, plan: set[str], _: dict) -> bool:
    match label:
        case "System packages":
            return False
        case "CLI tools":
            needs_cli_tool = {"nvim", "bat"}
            return not needs_cli_tool & plan
        case "Fonts":
            font_users = {"ghostty", "alacritty", "wezterm", "tmux", "nvim"}
            return not font_users & plan
        case "Stow symlinks":
            return False
        case "Runtimes":
            runtime_users = {"nvim", "opencode", "zsh"}
            return not runtime_users & plan
        case "Post-install":
            post_users = {"tmux", "windows-terminal"}
            return not post_users & plan
        case "Verification":
            return True
        case _:
            return False


def cmd_install(args: argparse.Namespace) -> None:
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

    for label, fn in INSTALL_STEPS:
        if core.STOW_PLAN is not None and should_skip_step(label, core.STOW_PLAN, conf):
            print(f"   (skipped — not needed by {', '.join(args.just)})")
            continue
        if core.INTERACTIVE and not core.confirm(f"▶ {label}?"):
            continue
        banner(label)
        fn(conf, mode="install")

    print("✅ Done!")
    print("   - Open Neovim so Lazy can install plugins")
    print("   - In tmux, press Prefix + I to install TPM plugins")
    print()
    if wsl:
        print("📌 WSL: Install CodeNewRoman Nerd Font on Windows manually")
        print("   https://www.nerdfonts.com/font-downloads")
    stow_dirs = sorted(
        p.name for p in DOTFILES_DIR.joinpath("stow-packages").iterdir() if p.is_dir()
    )
    print(f"📦 Stow packages active: {', '.join(stow_dirs)}")
    print(f"🖥️  Terminal: {conf.get('stow', {}).get('terminal', 'ghostty')}")


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

    for label, fn in UNINSTALL_STEPS:
        if core.INTERACTIVE and not core.confirm(f"▶ {label}?"):
            continue
        banner(label)
        fn(conf, mode="uninstall")

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

    args = parser.parse_args()

    if args.command == "install":
        cmd_install(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)


if __name__ == "__main__":
    main()
