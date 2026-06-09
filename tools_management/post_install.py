import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import manifest as mf
from core import download, is_wsl, run, run_optional, safe_rmtree, which
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


def _undo_post_install(_: dict) -> None:
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
    manifest["post_install"] = {
        "tpm_installed": False,
        "windows_terminal_linked": False,
        "zsh_plugins_installed": [],
    }
    mf.save(manifest)


def _install_windows_nerd_font(font_name: str) -> None:
    """Install a Nerd Font from WSL into Windows so Windows Terminal can use it."""
    nf_version = "3.4.0"
    url = f"https://github.com/ryanoasis/nerd-fonts/releases/download/v{nf_version}/{font_name}.zip"
    tmpdir = Path(tempfile.mkdtemp())

    try:
        archive = tmpdir / f"{font_name}.zip"
        download(url, archive)
        run(["unzip", "-q", str(archive), "-d", str(tmpdir / font_name), "-x", "*.txt", "*.md", "LICENSE"])

        # Find Windows user profile via /mnt/c/Users
        users_dir = Path("/mnt/c/Users")
        if not users_dir.is_dir():
            return
        skip_users = {"Default", "Public", "All Users", "Default User"}
        win_user = None
        for u in users_dir.iterdir():
            if u.name in skip_users:
                continue
            if u.is_dir() and (u / "AppData").is_dir():
                win_user = u.name
                break
        if not win_user:
            return

        font_dir = users_dir / win_user / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
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
            print(f"   Copied {copied} font files to Windows Fonts folder for '{font_name}'")
            # Register fonts with Windows so they're recognized immediately
            run_optional([
                "powershell.exe", "-NoProfile", "-Command",
                f'''
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
                '''
            ])
            print(f"✅ {font_name} Nerd Font installed on Windows")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _disable_win_fullscreen_optimizations() -> None:
    """Disable Fullscreen Optimizations for known apps via registry."""
    result = run_optional([
        "powershell.exe", "-NoProfile", "-Command",
        '''
        $regPath = "HKCU:\\Software\\Microsoft\\Windows NT\\CurrentVersion\\AppCompatFlags\\Layers"

        $wtExe = (Get-AppxPackage Microsoft.WindowsTerminal).InstallLocation + "\\WindowsTerminal.exe"
        Set-ItemProperty -Path $regPath -Name $wtExe -Value "DISABLEFULLSCREENOPTIMIZATION" -Type String
        Write-Output "  disabled for Windows Terminal"

        $zenExe = "C:\\Program Files\\Zen Browser\\zen.exe"
        if (Test-Path $zenExe) {
            Set-ItemProperty -Path $regPath -Name $zenExe -Value "DISABLEFULLSCREENOPTIMIZATION" -Type String
            Write-Output "  disabled for Zen Browser"
        }
        '''
    ])
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


def _sync_wsl_timezone() -> None:
    if not is_wsl():
        return
    result = run_optional([
        "powershell.exe", "-NoProfile", "-Command",
        "[System.TimeZoneInfo]::Local.Id",
    ], capture_output=True, text=True)
    if result is None or not result.stdout.strip():
        print("   ⚠  Could not detect Windows timezone")
        return
    win_tz = result.stdout.strip()
    print(f"   🕐 Windows timezone: {win_tz}")
    iana_tz = _map_windows_to_iana(win_tz)
    if not iana_tz:
        print(f"   ⚠  Unknown timezone '{win_tz}' — skipping")
        return
    current = run_optional([
        "timedatectl", "show", "-p", "Timezone", "--value",
    ], capture_output=True, text=True)
    current_tz = current.stdout.strip() if current else None
    if current_tz == iana_tz:
        print(f"   ✅ WSL timezone already set to {iana_tz}")
    else:
        print(f"   🕐 Setting WSL timezone to {iana_tz}...")
        run_optional(["sudo", "timedatectl", "set-timezone", iana_tz])
    # Sync clock from Windows RTC
    run_optional(["sudo", "hwclock", "-s"])


def run_post_install(config: dict, mode: str = "install") -> None:
    if mode == "check":
        print("🔄 Post-install:")
        tpm_enabled = config.get("post_install", {}).get("tpm", True)
        if tpm_enabled:
            print(f"   {'✅' if TPM_DIR.is_dir() else '⬜'} TPM")
        if config.get("post_install", {}).get("windows_terminal", True) and is_wsl():
            print("   ⬜ Windows Terminal symlink")
        print("   📦 Zsh plugins:")
        for name in ZSH_PLUGINS:
            target = ZSH_PLUGIN_DIR / name
            status = "✅" if target.is_dir() and any(target.iterdir()) else "⬜"
            print(f"      {status} {name}")
        print()
        return

    print("🔄 Post-install...")

    if mode == "uninstall":
        _undo_post_install(config)
        return

    manifest = mf.load()

    if is_wsl() and config.get("post_install", {}).get("windows_terminal", True):
        print("🪟  Setting up Windows Terminal...")
        stow_windows_terminal()
        _disable_win_fullscreen_optimizations()
        manifest["post_install"]["windows_terminal_linked"] = True

    if is_wsl():
        print("🔤 Installing Nerd Fonts on Windows...")
        for name in config.get("fonts", []):
            _install_windows_nerd_font(name)
        _sync_wsl_timezone()

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
        (ruff_pkg / "mason-receipt.json").write_text('{"id":"ruff","bin":["ruff"],"languages":["Python"],"spdx":"MIT"}')
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
