import shutil
from pathlib import Path

import manifest as mf
from core import is_wsl, which, run
from stow import stow_windows_terminal

TPM_DIR = Path.home() / ".tmux" / "plugins" / "tpm"

ZSH_PLUGINS: dict[str, str] = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting",
}

ZSH_PLUGIN_DIR = Path.home() / ".zsh"


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


def _install_zsh_plugin(name: str, repo: str) -> bool:
    target = ZSH_PLUGIN_DIR / name
    if target.is_dir():
        try:
            next(target.iterdir())
            return False
        except StopIteration:
            shutil.rmtree(target)
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
            shutil.rmtree(target)
            print(f"   removed ~/.zsh/{name}")


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

    print("📦 Zsh plugins...")
    installed = install_zsh_plugins()
    if installed:
        manifest.setdefault("post_install", {})["zsh_plugins_installed"] = installed
        print(f"   installed: {', '.join(installed)}")
    else:
        print("   all up to date")

    mf.save(manifest)
