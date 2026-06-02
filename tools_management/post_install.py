import shutil
from pathlib import Path

import manifest as mf
from core import is_wsl, which, run
from stow import stow_windows_terminal

TPM_DIR = Path.home() / ".tmux" / "plugins" / "tpm"


def install_tpm() -> None:
    if not which("tmux"):
        return
    if TPM_DIR.is_dir():
        return
    print("📋 Installing tmux plugin manager (TPM)...")
    run(["git", "clone", "https://github.com/tmux-plugins/tpm", str(TPM_DIR)])


def _undo_tpm() -> None:
    if TPM_DIR.is_dir():
        shutil.rmtree(TPM_DIR)
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
    if target.is_symlink():
        target.unlink()
        print("   removed Windows Terminal symlink")
    if bak.is_file():
        bak.rename(target)
        print("   restored preexisting Windows Terminal settings.json")


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
    manifest["post_install"] = {
        "tpm_installed": False,
        "windows_terminal_linked": False,
    }
    mf.save(manifest)


def run_post_install(config: dict, mode: str = "install") -> None:
    print("🔄 Post-install...")

    if mode == "uninstall":
        _undo_post_install(config)
        return

    manifest = mf.load()

    if is_wsl() and config.get("post_install", {}).get("windows_terminal", True):
        print("🪟  Linking Windows Terminal config...")
        stow_windows_terminal()
        manifest["post_install"]["windows_terminal_linked"] = True

    if config.get("post_install", {}).get("tpm", True):
        install_tpm()
        manifest["post_install"]["tpm_installed"] = True

    mf.save(manifest)
