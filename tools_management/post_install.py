import json
import re
import shutil
import tempfile
from pathlib import Path

import core
import manifest as mf
from core import STOW_DIR, download, is_wsl, run, run_optional, safe_rmtree, which
from stow import stow_windows_terminal

TPM_DIR = Path.home() / ".tmux" / "plugins" / "tpm"

ZSH_PLUGINS: dict[str, str] = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting",
}

ZSH_PLUGIN_DIR = Path.home() / ".local" / "share" / "zsh-plugins"


def install_tpm() -> None:
    if not which("tmux"):
        return
    if TPM_DIR.is_dir():
        return
    print("📋 Installing tmux plugin manager (TPM)...")
    run(["git", "clone", "https://github.com/tmux-plugins/tpm", str(TPM_DIR)])


def _undo_tpm() -> None:
    if TPM_DIR.is_dir():
        safe_rmtree(TPM_DIR)
        print("   removed TPM (~/.tmux/plugins/tpm)")


def _undo_windows_terminal() -> None:
    if not is_wsl():
        return
    wt_glob = list(
        Path("/mnt/c/Users").glob(
            "*/AppData/Local/Packages/Microsoft.WindowsTerminal_*"
        )
    )
    if not wt_glob:
        return
    target = wt_glob[0] / "LocalState" / "settings.json"
    bak = target.with_suffix(".json.bak")
    if target.is_file():
        target.unlink()
        print("   removed Windows Terminal settings.json")
    if bak.is_file():
        bak.rename(target)
        print("   restored preexisting Windows Terminal settings.json")


def _install_zsh_plugin(name: str, repo: str) -> bool:
    target = ZSH_PLUGIN_DIR / name
    if target.is_dir():
        try:
            next(target.iterdir())
            return False
        except StopIteration:
            safe_rmtree(target)
    elif target.is_symlink():
        target.unlink()
    elif target.exists():
        target.unlink()
    ZSH_PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   cloning {name}...")
    run(["git", "clone", repo, str(target)])
    return True


def install_zsh_plugins() -> list[str]:
    installed = []
    for name, repo in ZSH_PLUGINS.items():
        if _install_zsh_plugin(name, repo):
            installed.append(name)
    return installed


def _undo_zsh_plugins(plugins: list[str]) -> None:
    for name in plugins:
        target = ZSH_PLUGIN_DIR / name
        if target.is_dir():
            safe_rmtree(target)
            print(f"   removed {ZSH_PLUGIN_DIR}/{name}")


WINDOWS_PATH_ZSH = Path.home() / ".config" / "zsh" / ".windows_path.zsh"

WINDOWS_PATH_SNIPPET = """\
# WSL: add Windows System32 to PATH so markdown-preview.nvim (and other tools)
# can use cmd.exe / start to open URLs in the Windows default browser.
if [[ -d /mnt/c/Windows/System32 ]]; then
  export PATH="/mnt/c/Windows/System32:$PATH"
fi
"""


def _ensure_wsl_windows_path() -> None:
    if not is_wsl():
        return
    sys32 = Path("/mnt/c/Windows/System32")
    if not sys32.is_dir():
        print("   ⚠  /mnt/c/Windows/System32 not found — cannot add Windows path")
        return
    WINDOWS_PATH_ZSH.parent.mkdir(parents=True, exist_ok=True)
    WINDOWS_PATH_ZSH.write_text(WINDOWS_PATH_SNIPPET)
    print(f"   🪟 Windows System32 path added to zsh config ({WINDOWS_PATH_ZSH})")


def _undo_wsl_windows_path() -> None:
    if WINDOWS_PATH_ZSH.is_file():
        WINDOWS_PATH_ZSH.unlink()
        print("   removed WSL Windows path config")


def _undo_post_install(_: dict) -> None:
    _undo_opencode_notifier()
    manifest = mf.saved_version()
    if not manifest:
        print("⚠️  No manifest found.")
        return
    post = manifest.get("post_install", {})
    if post.get("tpm_installed"):
        _undo_tpm()
    if post.get("windows_terminal_linked"):
        _undo_windows_terminal()
    if post.get("zsh_plugins_installed"):
        _undo_zsh_plugins(post["zsh_plugins_installed"])
    if post.get("wsl_windows_path"):
        _undo_wsl_windows_path()
    if is_wsl():
        _undo_ssh_agent()
    manifest["post_install"] = {
        "tpm_installed": False,
        "windows_terminal_linked": False,
        "zsh_plugins_installed": [],
        "wsl_windows_path": False,
    }
    mf.save(manifest)


def _full_font(base: str) -> str:
    """Full font name for most terminals (alacritty, wezterm, windows-terminal)."""
    return f"{base} Nerd Font Propo"


def _ghostty_font(base: str) -> str:
    """Font name for ghostty (uses 'Nerd Font' without 'Propo')."""
    return f"{base} Nerd Font"


def _resolve_primary_terminal(config: dict) -> str:
    """Return the first enabled terminal name."""
    stow_cfg = config.get("stow", {})
    if stow_cfg.get("ghostty_or_windowsTerminal", True):
        return "windows-terminal" if is_wsl() else "ghostty"
    if stow_cfg.get("alacritty", False):
        return "alacritty"
    if stow_cfg.get("wezterm", False):
        return "wezterm"
    return "ghostty"


def _write_notifier_config(config: dict) -> None:
    """Write opencode-notifier.json only when ghostty is the primary terminal."""
    notifier_path = Path.home() / ".config" / "opencode" / "opencode-notifier.json"
    primary = _resolve_primary_terminal(config)

    if primary != "ghostty":
        if notifier_path.exists():
            notifier_path.unlink()
            print("   ✓ removed stale opencode-notifier.json")
        return

    if notifier_path.is_symlink():
        notifier_path.unlink()

    notifier_path.parent.mkdir(parents=True, exist_ok=True)
    notifier_path.write_text(
        json.dumps({"notificationSystem": "ghostty"}, indent=2) + "\n"
    )
    print("   ✓ notificationSystem set to 'ghostty'")


def _undo_opencode_notifier() -> None:
    notifier_path = Path.home() / ".config" / "opencode" / "opencode-notifier.json"
    if notifier_path.is_file():
        notifier_path.unlink()
        print("   removed opencode-notifier.json")


def _ghostty_override_path() -> Path:
    return Path.home() / ".config" / "ghostty" / "local_config"


def _ensure_ghostty_override() -> None:
    """Ensure ~/.config/ghostty/local_config exists with machine-specific overrides.

    This file is gitignored and loaded after config (tracked), so values here
    take precedence. font-family and command are set by the installer later.
    """
    if is_wsl():
        return
    override_path = _ghostty_override_path()
    if override_path.is_file() or override_path.is_symlink():
        return

    override_path.parent.mkdir(parents=True, exist_ok=True)
    override_path.write_text(
        "# Ghostty machine-specific overrides (gitignored)\n"
        "# Loaded after config (tracked) \u2014 values here take precedence.\n"
        "# The installer manages font-family and command below. Add any\n"
        "# other override below.\n"
        "\n"
        '# font-family = "CodeNewRoman Nerd Font"\n'
        '# command = "/opt/homebrew/bin/tmux new-session -A -D -s main"\n'
        "\n"
    )
    print("   \u2713 ghostty: created ~/.config/ghostty/local_config")


def _set_or_add_line(path: Path, key: str, new_line: str) -> bool:
    """Replace key= line (commented or not) with new_line, or append if missing.
    Returns True if the line was found and updated, False if appended.
    """
    content = path.read_text()
    lines = content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("#").strip()
        if stripped.startswith(f"{key} "):
            lines[i] = new_line
            path.write_text("\n".join(lines))
            return True
        if stripped.startswith(f"{key}="):
            lines[i] = new_line
            path.write_text("\n".join(lines))
            return True
    lines.append(new_line)
    path.write_text("\n".join(lines))
    return False


def _update_ghostty_font(config: dict) -> None:
    """Set font-family in ghostty override file (machine-specific)."""
    stow_cfg = config.get("stow", {})
    if not stow_cfg.get("ghostty_or_windowsTerminal", True) or is_wsl():
        return
    base = config.get("terminal_font", "CodeNewRoman")
    if not base:
        return
    override_path = _ghostty_override_path()
    if not override_path.is_file():
        return
    font_name = _ghostty_font(base)
    new_line = f'font-family = "{font_name}"'
    _set_or_add_line(override_path, "font-family", new_line)
    print(f"   \u2713 ghostty: font-family set to '{font_name}'")


def _update_ghostty_command() -> None:
    """Set tmux command in ghostty override file."""
    override_path = _ghostty_override_path()
    if not override_path.is_file():
        return
    tmux_bin = which("tmux")
    if not tmux_bin:
        return
    if isinstance(tmux_bin, bool):
        tmux_bin = shutil.which("tmux") or "tmux"
    tmux_cmd = f'command = "{tmux_bin} new-session -A -D -s main"'
    _set_or_add_line(override_path, "command", tmux_cmd)
    print(f"   \u2713 ghostty: tmux command enabled ({tmux_bin})")


def _update_ghostty_window_decoration() -> None:
    """Set window-decoration = none on Linux (macOS uses macos-titlebar-style in config)."""
    import platform

    if platform.system() == "Darwin" or is_wsl():
        return
    override_path = _ghostty_override_path()
    if not override_path.is_file():
        return
    _set_or_add_line(override_path, "window-decoration", 'window-decoration = "none"')
    _set_or_add_line(override_path, "background-blur", "background-blur = false")
    print(
        "   \u2713 ghostty: window-decoration set to 'none', background-blur set to false"
    )


def _generate_terminal_font_overrides(config: dict) -> None:
    """Generate local override files for each enabled terminal with the configured font."""
    stow_cfg = config.get("stow", {})
    base = config.get("terminal_font", "CodeNewRoman")
    if not base:
        return

    # Ghostty: update font-family in existing override file
    _update_ghostty_font(config)

    targets: list[tuple[str, str, str]] = []

    if stow_cfg.get("alacritty", False):
        targets.append(
            (
                "alacritty",
                "local.toml",
                f'[font]\nnormal = {{ family = "{_full_font(base)}", style = "Regular" }}\nbuiltin_box_drawing = false\n',
            )
        )

    if stow_cfg.get("wezterm", False):
        targets.append(
            (
                "wezterm",
                "local.lua",
                f"""local wezterm = require("wezterm")
local config = wezterm.config_builder()
config.font = wezterm.font("{_full_font(base)}")
return config
""",
            )
        )

    for pkg_name, filename, content in targets:
        override_path = STOW_DIR / pkg_name / ".config" / pkg_name / filename
        override_path.parent.mkdir(parents=True, exist_ok=True)
        override_path.write_text(content)
        print(f"   ✓ {pkg_name}: generated {filename}")


def _windows_user_dir() -> Path | None:
    """Return Windows user home directory via /mnt/c/Users, or None."""
    users_dir = Path("/mnt/c/Users")
    if not users_dir.is_dir():
        return None
    skip_users = {"Default", "Public", "All Users", "Default User"}
    for u in users_dir.iterdir():
        if u.name in skip_users:
            continue
        if u.is_dir() and (u / "AppData").is_dir():
            return u
    return None


def _windows_font_dir() -> Path | None:
    win_user = _windows_user_dir()
    if win_user is None:
        return None
    return win_user / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"


def _windows_font_installed(font_name: str) -> bool:
    font_dir = _windows_font_dir()
    if font_dir is None or not font_dir.is_dir():
        return False
    for f in font_dir.iterdir():
        if font_name.replace(" ", "") in f.name and f.suffix.lower() in (
            ".ttf",
            ".otf",
        ):
            return True
    return False


def _install_windows_nerd_font(font_name: str) -> None:
    """Install a Nerd Font from WSL into Windows so Windows Terminal can use it."""
    if not core.COLD and _windows_font_installed(font_name):
        print(f"✅ {font_name} Nerd Font already installed on Windows")
        return

    nf_version = "3.4.0"
    url = f"https://github.com/ryanoasis/nerd-fonts/releases/download/v{nf_version}/{font_name}.zip"
    tmpdir = Path(tempfile.mkdtemp())

    try:
        archive = tmpdir / f"{font_name}.zip"
        download(url, archive)
        run(
            [
                "unzip",
                "-q",
                str(archive),
                "-d",
                str(tmpdir / font_name),
                "-x",
                "*.txt",
                "*.md",
                "LICENSE",
            ]
        )

        font_dir = _windows_font_dir()
        if font_dir is None:
            return
        font_dir.mkdir(parents=True, exist_ok=True)

        copied = 0
        for f in (tmpdir / font_name).glob("*"):
            if f.suffix.lower() in (".ttf", ".otf"):
                target = font_dir / f.name
                if target.exists():
                    print(f"   (skipped {f.name} — already exists)")
                    copied += 1
                    continue
                try:
                    shutil.copy2(f, target)
                    copied += 1
                except PermissionError:
                    print(f"   ⚠  Permission denied: {target}")
                    continue

        if copied:
            print(
                f"   Copied {copied} font files to Windows Fonts folder for '{font_name}'"
            )
            # Register fonts with Windows so they're recognized immediately
            run_optional(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"""
                $fontsDir = "$env:LOCALAPPDATA\\Microsoft\\Windows\\Fonts"
                $regPath = "HKCU:\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"
                if (-not (Test-Path $regPath)) {{
                    New-Item -Path $regPath -Force | Out-Null
                }}
                Get-ChildItem "$fontsDir\\*" -Include "*.ttf","*.otf" | Where-Object {{ $_.Name -like "*{font_name.replace(' ', '')}*" }} | ForEach-Object {{
                    $fontName = $_.BaseName
                    $regName = "$fontName (TrueType)"
                    Set-ItemProperty -Path $regPath -Name $regName -Value $_.FullName -Type String
                }}
                # Broadcast WM_FONTCHANGE so Windows apps pick it up immediately
                Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                public class FontUti {{
                    [DllImport("user32.dll")]
                    public static extern IntPtr SendMessageTimeout(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam, uint fuFlags, uint uTimeout, out IntPtr lpdwResult);
                }}
"@
                [void][FontUti]::SendMessageTimeout(-1, 0x001D, [IntPtr]::Zero, [IntPtr]::Zero, 2, 3000, [ref]0)
                """,
                ]
            )
            print(f"✅ {font_name} Nerd Font installed on Windows")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _disable_win_fullscreen_optimizations() -> None:
    """Disable Fullscreen Optimizations for known apps via registry."""
    result = run_optional(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            """
        $regPath = "HKCU:\\Software\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers"

        $wtExe = (Get-AppxPackage Microsoft.WindowsTerminal).InstallLocation + "\\WindowsTerminal.exe"
        Set-ItemProperty -Path $regPath -Name $wtExe -Value "DISABLEFULLSCREENOPTIMIZATION" -Type String
        Write-Output "  disabled for Windows Terminal"

        $zenExe = "C:\\Program Files\\Zen Browser\\zen.exe"
        if (Test-Path $zenExe) {
            Set-ItemProperty -Path $regPath -Name $zenExe -Value "DISABLEFULLSCREENOPTIMIZATION" -Type String
            Write-Output "  disabled for Zen Browser"
        }
        """,
        ]
    )
    if result is not None:
        print("   🖥️  Fullscreen optimizations disabled for known apps")


# Windows timezone ID → IANA timezone ID mapping
_WINDOWS_TO_IANA: dict[str, str] = {
    # South America (UTC-3)
    "Argentina Standard Time": "America/Argentina/Buenos_Aires",
    "E. South America Standard Time": "America/Sao_Paulo",
    "SA Eastern Standard Time": "America/Cayenne",
    "Paraguay Standard Time": "America/Asuncion",
    "Uruguay Standard Time": "America/Montevideo",
    "Montevideo Standard Time": "America/Montevideo",
    "Chile Standard Time": "America/Santiago",
    "Pacific SA Standard Time": "America/Caracas",
    "Venezuela Standard Time": "America/Caracas",
    "Bahia Standard Time": "America/Bahia",
    "Central Brazilian Standard Time": "America/Cuiaba",
    "Amazon Standard Time": "America/Manaus",
    # North America
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Mountain Standard Time": "America/Denver",
    "Pacific Standard Time": "America/Los_Angeles",
    "Alaskan Standard Time": "America/Anchorage",
    "Hawaiian Standard Time": "Pacific/Honolulu",
    "Atlantic Standard Time": "America/Halifax",
    "Newfoundland Standard Time": "America/St_Johns",
    # Europe
    "W. Europe Standard Time": "Europe/Madrid",
    "Central European Standard Time": "Europe/Paris",
    "Central Europe Standard Time": "Europe/Berlin",
    "E. Europe Standard Time": "Europe/Bucharest",
    "Eastern European Standard Time": "Europe/Bucharest",
    "GMT Standard Time": "Europe/London",
    "Turkey Standard Time": "Europe/Istanbul",
    "Moscow Standard Time": "Europe/Moscow",
    "FLE Standard Time": "Europe/Helsinki",
    # Asia
    "China Standard Time": "Asia/Shanghai",
    "India Standard Time": "Asia/Kolkata",
    "Japan Standard Time": "Asia/Tokyo",
    "Korea Standard Time": "Asia/Seoul",
    "Singapore Standard Time": "Asia/Singapore",
    "Taipei Standard Time": "Asia/Taipei",
    "W. Australia Standard Time": "Australia/Perth",
    "AUS Eastern Standard Time": "Australia/Sydney",
    "Central Australia Standard Time": "Australia/Adelaide",
    # General
    "Coordinated Universal Time": "Etc/UTC",
    "UTC": "Etc/UTC",
    "Morocco Standard Time": "Africa/Casablanca",
    "South Africa Standard Time": "Africa/Johannesburg",
}


def _parse_windows_utc_offset(win_tz: str) -> str | None:
    """Parse 'UTC-03', 'UTC+05:30' style IDs into IANA Etc/GMT zones."""
    m = re.search(r"UTC([+-])(\d{2})(?::(\d{2}))?", win_tz)
    if not m:
        return None
    sign = m.group(1)
    hours = int(m.group(2))
    mins = int(m.group(3)) if m.group(3) else 0
    if mins:
        return None
    # Etc/GMT inverts the sign: Etc/GMT+3 = UTC-3
    iana_hours = hours
    if sign == "+":
        iana_hours = -hours
    else:
        iana_hours = hours
    label = f"Etc/GMT{iana_hours:+d}" if iana_hours != 0 else "Etc/UTC"
    return label


def _map_windows_to_iana(win_tz: str) -> str | None:
    win_tz = win_tz.strip()
    if win_tz in _WINDOWS_TO_IANA:
        return _WINDOWS_TO_IANA[win_tz]
    # Try "UTC+/-XX" pattern
    result = _parse_windows_utc_offset(win_tz)
    if result:
        return result
    return None


def _get_windows_tz() -> str | None:
    commands = [
        ["powershell.exe", "-NoProfile", "-Command", "[System.TimeZoneInfo]::Local.Id"],
        [
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
            "-NoProfile",
            "-Command",
            "[System.TimeZoneInfo]::Local.Id",
        ],
        ["cmd.exe", "/c", "tzutil", "/g"],
        ["/mnt/c/Windows/System32/cmd.exe", "/c", "tzutil", "/g"],
    ]
    for cmd in commands:
        result = run_optional(cmd, capture_output=True, text=True)
        if result and result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


def _sync_wsl_timezone() -> None:
    if not is_wsl():
        return
    win_tz = _get_windows_tz()
    if not win_tz:
        print("   ⚠  Could not detect Windows timezone (is /mnt/c mounted?)")
        return
    print(f"   🕐 Windows timezone: {win_tz}")
    iana_tz = _map_windows_to_iana(win_tz)
    if not iana_tz:
        print(f"   ⚠  Unknown timezone '{win_tz}' — skipping")
        return
    current = run_optional(
        [
            "timedatectl",
            "show",
            "-p",
            "Timezone",
            "--value",
        ],
        capture_output=True,
        text=True,
    )
    current_tz = current.stdout.strip() if current else None
    if current_tz == iana_tz:
        print(f"   ✅ WSL timezone already set to {iana_tz}")
    else:
        print(f"   🕐 Setting WSL timezone to {iana_tz}...")
        run_optional(["sudo", "timedatectl", "set-timezone", iana_tz])


def _setup_ssh_agent() -> None:
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, exist_ok=True)

    config_path = ssh_dir / "config"
    config_text = config_path.read_text() if config_path.is_file() else ""
    if "AddKeysToAgent" not in config_text:
        with open(config_path, "a") as f:
            f.write("\nHost *\n  AddKeysToAgent yes\n")
        config_path.chmod(0o600)
        print("   🔑 Added AddKeysToAgent yes to ~/.ssh/config")
    else:
        print("   🔑 AddKeysToAgent already set in ~/.ssh/config")

    # Remove old systemd ssh-agent service if present
    unit_path = Path.home() / ".config" / "systemd" / "user" / "ssh-agent.service"
    if unit_path.is_file():
        run_optional(["systemctl", "--user", "disable", "--now", "ssh-agent.service"])
        unit_path.unlink()
        run_optional(["systemctl", "--user", "daemon-reload"])
        print("   🔑 Removed old systemd ssh-agent service")

    # Install keychain (manages ssh-agent across terminals; .zshrc uses mkdir lock
    # so only the first terminal prompts for passphrase)
    if not which("keychain"):
        run(["sudo", "apt", "install", "-y", "keychain"])
    else:
        print("   🔑 keychain already installed")

    public_key = ssh_dir / "id_ed25519.pub"
    if public_key.is_file():
        print(
            "   📢 Passphrase will be requested on first terminal — keychain caches it thereafter"
        )


def _undo_ssh_agent() -> None:
    # Remove systemd service if present
    run_optional(["systemctl", "--user", "disable", "--now", "ssh-agent.service"])
    unit_path = Path.home() / ".config" / "systemd" / "user" / "ssh-agent.service"
    if unit_path.is_file():
        unit_path.unlink()
    run_optional(["systemctl", "--user", "daemon-reload"])

    # Kill any keychain-managed agents
    run_optional(["keychain", "--stop", "all"])
    run_optional(["sudo", "apt", "remove", "-y", "keychain"])
    print("   🔑 SSH agent (keychain) removed")


def run_post_install(config: dict, mode: str = "install") -> None:
    if mode == "check":
        print("🔄 Post-install:")
        tpm_enabled = config.get("post_install", {}).get("tpm", True)
        if tpm_enabled:
            print(f"   {'✅' if TPM_DIR.is_dir() else '⬜'} TPM")
        stow_cfg = config.get("stow", {})
        wt_enabled = stow_cfg.get("ghostty_or_windowsTerminal", True)
        if wt_enabled and is_wsl():
            print("   ⬜ Windows Terminal sync")
        if is_wsl():
            wp_status = "✅" if WINDOWS_PATH_ZSH.is_file() else "⬜"
            print(f"   {wp_status} WSL Windows path config")
        print("   📦 Zsh plugins:")
        for name in ZSH_PLUGINS:
            target = ZSH_PLUGIN_DIR / name
            status = "✅" if target.is_dir() and any(target.iterdir()) else "⬜"
            print(f"      {status} {name}")
        notifier_path = Path.home() / ".config" / "opencode" / "opencode-notifier.json"
        if notifier_path.is_file():
            try:
                data = json.loads(notifier_path.read_text())
                ns = data.get("notificationSystem", "?")
                print(f"   🔔 opencode-notifier: notificationSystem={ns}")
            except Exception:
                print("   ⚠  opencode-notifier.json: invalid")
        else:
            print("   ⬜ opencode-notifier.json: not found")
        print()
        return

    print("🔄 Post-install...")

    if mode == "uninstall":
        _undo_post_install(config)
        return

    manifest = mf.load()
    stow_cfg = config.get("stow", {})
    terminal_font = config.get("terminal_font", "CodeNewRoman Nerd Font Propo")

    print("🐚 Ensuring ghostty override file...")
    _ensure_ghostty_override()

    print("🔤 Generating terminal font overrides...")
    _generate_terminal_font_overrides(config)

    print("⚡ Setting ghostty tmux command...")
    _update_ghostty_command()

    print("🪟 Setting ghostty window decorations...")
    _update_ghostty_window_decoration()

    print("🔔 Writing opencode-notifier config...")
    _write_notifier_config(config)

    if is_wsl() and stow_cfg.get("ghostty_or_windowsTerminal", True):
        print("🪟  Setting up Windows Terminal...")
        stow_windows_terminal(terminal_font)
        _disable_win_fullscreen_optimizations()
        manifest["post_install"]["windows_terminal_linked"] = True

    if is_wsl():
        print("🔤 Installing Nerd Font on Windows...")
        _install_windows_nerd_font(terminal_font)
        _sync_wsl_timezone()
        _setup_ssh_agent()
        _ensure_wsl_windows_path()
        manifest["post_install"]["wsl_windows_path"] = True

    if config.get("post_install", {}).get("tpm", True):
        install_tpm()
        manifest["post_install"]["tpm_installed"] = True

    print("📦 Zsh plugins...")
    installed = install_zsh_plugins()
    if installed:
        manifest.setdefault("post_install", {})["zsh_plugins_installed"] = installed
        print(f"   installed: {', '.join(installed)}")
    else:
        print("   all up to date")

    # Register ruff in Mason so mason-lspconfig doesn't reinstall via pip
    from core import BIN_DIR

    mason_pkgs = Path.home() / ".local" / "share" / "nvim" / "mason" / "packages"
    mason_bin = Path.home() / ".local" / "share" / "nvim" / "mason" / "bin"
    ruff_pkg = mason_pkgs / "ruff"
    if (BIN_DIR / "ruff").exists():
        ruff_pkg.mkdir(parents=True, exist_ok=True)
        (ruff_pkg / "mason-receipt.json").write_text(
            '{"id":"ruff","bin":["ruff"],"languages":["Python"],"spdx":"MIT"}'
        )
        mason_bin_ruff = mason_bin / "ruff"
        if mason_bin_ruff.is_symlink() or mason_bin_ruff.exists():
            mason_bin_ruff.unlink()
        mason_bin_ruff.symlink_to(BIN_DIR / "ruff")
        print("   📝 ruff registered in Mason")

    # Ensure tree-sitter CLI is available in PATH (Mason installs it internally)
    ts_dir = mason_pkgs / "tree-sitter-cli"
    if ts_dir.is_dir():
        ts_src = next(ts_dir.glob("tree-sitter-*"), None)
        ts_link = BIN_DIR / "tree-sitter"
        if ts_src and not ts_link.is_file():
            ts_link.symlink_to(ts_src)
            print("   🔗 tree-sitter CLI linked to ~/.local/bin")

    mf.save(manifest)
