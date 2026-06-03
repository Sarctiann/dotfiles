import json
import os
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

from core import run, which
import manifest as mf


def _latest_github_release(repo: str) -> str | None:
    token = (
        os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )
    headers = {"User-Agent": "dotfiles-install/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = Request(
            f"https://api.github.com/repos/{repo}/releases/latest", headers=headers
        )
        with urlopen(req) as resp:
            data = json.loads(resp.read())
        return data["tag_name"].lstrip("v")
    except Exception:
        return None


def install_nvm() -> None:
    if Path.home().joinpath(".nvm").is_dir():
        print("✅ nvm already installed")
        return
    print("📋 Installing nvm...")
    run(
        [
            "bash",
            "-c",
            "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash",
        ]
    )
    nvm_dir = Path.home() / ".nvm"
    nvm_sh = nvm_dir / "nvm.sh"
    if nvm_sh.exists():
        import os

        os.environ["NVM_DIR"] = str(nvm_dir)
        run(
            [
                "bash",
                "-c",
                f"source {nvm_sh} --no-use && nvm install --lts && nvm alias default 'lts/*'",
            ]
        )


def install_opencode() -> None:
    if which("opencode"):
        print("✅ opencode already installed")
        return
    print("📋 Installing opencode...")
    version = _latest_github_release("anomalyco/opencode")
    env = os.environ.copy()
    if version:
        env["VERSION"] = version
    run(
        ["bash", "-c", "curl -fsSL https://opencode.ai/install | bash"],
        env=env,
    )


def install_bun() -> None:
    if which("bun"):
        print("✅ bun already installed")
        return
    print("📋 Installing Bun...")
    run(["bash", "-c", "curl -fsSL https://bun.sh/install | bash"])


def install_rust() -> None:
    if which("cargo"):
        print("✅ rust/cargo already installed")
        return
    print("📋 Installing Rust via rustup...")
    run(
        [
            "curl",
            "--proto",
            "=https",
            "--tlsv1.2",
            "-sSf",
            "https://sh.rustup.rs",
            "-o",
            "/tmp/rustup.sh",
        ]
    )
    run(["sh", "/tmp/rustup.sh", "-y"])


def _uninstall_nvm() -> None:
    nvm_dir = Path.home() / ".nvm"
    if nvm_dir.is_dir():
        shutil.rmtree(nvm_dir)
        print("   removed ~/.nvm")
    _clean_path_from_rc("NVM_DIR")
    _clean_path_from_rc(".nvm")


def _uninstall_bun() -> None:
    bun_dir = Path.home() / ".bun"
    if bun_dir.is_dir():
        shutil.rmtree(bun_dir)
        print("   removed ~/.bun")
    _clean_path_from_rc(".bun")


def _uninstall_rust() -> None:
    if which("rustup"):
        run(["rustup", "self", "uninstall", "-y"])
    else:
        rust_dir = Path.home() / ".rustup"
        if rust_dir.is_dir():
            shutil.rmtree(rust_dir)
            print("   removed ~/.rustup")
        cargo_dir = Path.home() / ".cargo"
        if cargo_dir.is_dir():
            shutil.rmtree(cargo_dir)
            print("   removed ~/.cargo")


def _uninstall_opencode() -> None:
    from core import BIN_DIR

    opencode_bin = BIN_DIR / "opencode"
    if opencode_bin.exists():
        opencode_bin.unlink()
        print(f"   removed {opencode_bin}")
    config_dir = Path.home() / ".config" / "opencode"
    if config_dir.is_symlink():
        config_dir.unlink()
        print("   removed ~/.config/opencode (symlink)")
    elif config_dir.is_dir():
        shutil.rmtree(config_dir)
        print("   removed ~/.config/opencode")


def _clean_path_from_rc(marker: str) -> None:
    for rc in [Path.home() / ".zshrc", Path.home() / ".bashrc"]:
        if rc.exists():
            lines = rc.read_text().splitlines()
            cleaned = [
                line
                for line in lines
                if not (
                    marker in line
                    and (
                        "export" in line
                        or "PATH" in line
                        or "source" in line
                        or "\\." in line
                        or "nvm use" in line
                    )
                )
            ]
            rc.write_text("\n".join(cleaned) + "\n")


def _preexisting_names() -> list[str]:
    preexisting = []
    if Path.home().joinpath(".nvm").is_dir():
        preexisting.append("nvm")
    if which("bun"):
        preexisting.append("bun")
    if which("cargo"):
        preexisting.append("rust")
    if which("opencode"):
        preexisting.append("opencode")
    return preexisting


INSTALLERS = {
    "nvm": install_nvm,
    "opencode": install_opencode,
    "bun": install_bun,
    "rust": install_rust,
}


UNINSTALLERS = {
    "nvm": _uninstall_nvm,
    "bun": _uninstall_bun,
    "rust": _uninstall_rust,
    "opencode": _uninstall_opencode,
}


def install_runtimes(config: dict, mode: str = "install") -> None:
    if mode == "uninstall":
        _uninstall_runtimes(config)
        return

    runtimes = config.get("runtimes", {})
    if not runtimes:
        return

    print("📋 Installing runtimes...")
    manifest = mf.load()
    mf.record_preexisting(manifest, "runtimes", _preexisting_names())
    installed = []
    for name, enabled in runtimes.items():
        if not enabled:
            continue
        fn = INSTALLERS.get(name)
        if fn:
            fn()
            installed.append(name)
    mf.record_installed(manifest, "runtimes", installed)
    mf.save(manifest)
    print()


def _uninstall_runtimes(_: dict) -> None:
    manifest = mf.saved_version()
    if not manifest:
        print("⚠️  No manifest found. Nothing to uninstall.")
        return
    to_remove = mf.get_uninstall_list(manifest, "runtimes")
    if not to_remove:
        print("   (no runtimes to uninstall)")
        return
    print("🗑  Removing runtimes...")
    for name in to_remove:
        fn = UNINSTALLERS.get(name)
        if fn:
            print(f"   → {name}")
            fn()
        else:
            print(f"   ⚠  No uninstaller for {name}, skipping")
    manifest["runtimes"] = {"preexisting": [], "installed": []}
    mf.save(manifest)
