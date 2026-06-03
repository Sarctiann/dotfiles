import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from core import BIN_DIR, detect_os, detect_arch, download, gh_arch, run, rz_arch, which

GH_API = "https://api.github.com"
_MAX_RETRIES = 3
_RETRY_DELAY = 2


def _asset_pattern(tool_name: str, os_name: str, arch: str) -> str | None:
    patterns = {
        "neovim": f"^nvim-{os_name}-{arch}\\.tar\\.gz$",
        "ripgrep": {
            "macos": f"^ripgrep-.*-{rz_arch()}-apple-darwin\\.tar\\.gz$",
            "linux": f"^ripgrep-.*-{rz_arch()}-unknown-linux-gnu\\.tar\\.gz$",
        },
        "fd": {
            "macos": f"^fd-.*-{rz_arch()}-apple-darwin\\.tar\\.gz$",
            "linux": f"^fd-.*-{rz_arch()}-unknown-linux-musl\\.tar\\.gz$",
        },
        "bat": {
            "macos": f"^bat-.*-{rz_arch()}-apple-darwin\\.tar\\.gz$",
            "linux": f"^bat-.*-{rz_arch()}-unknown-linux-musl\\.tar\\.gz$",
        },
        "lazygit": {
            "macos": f"^lazygit_.*_darwin_{arch}\\.tar\\.gz$",
            "linux": f"^lazygit_.*_linux_{arch}\\.tar\\.gz$",
        },
        "lazydocker": {
            "macos": f"^lazydocker_.*_Darwin_{arch}\\.tar\\.gz$",
            "linux": f"^lazydocker_.*_Linux_{arch}\\.tar\\.gz$",
        },
        "lazysql": {
            "macos": f"^lazysql_Darwin_{arch}\\.tar\\.gz$",
            "linux": f"^lazysql_Linux_{arch}\\.tar\\.gz$",
        },
        "gh": {
            "macos": f"^gh_.*_macOS_{gh_arch()}\\.zip$",
            "linux": f"^gh_.*_linux_{gh_arch()}\\.tar\\.gz$",
        },
        "fzf": {
            "macos": f"^fzf-.*-darwin_{gh_arch()}\\.tar\\.gz$",
            "linux": f"^fzf-.*-linux_{gh_arch()}\\.tar\\.gz$",
        },
        "yazi": {
            "macos": f"^yazi-{rz_arch()}-apple-darwin\\.zip$",
            "linux": f"^yazi-{rz_arch()}-unknown-linux-(gnu|musl)\\.zip$",
        },
    }
    entry = patterns.get(tool_name)
    if entry is None:
        return None
    if isinstance(entry, str):
        return entry
    return entry.get(os_name)


def _latest_asset_url(repo: str, pattern: str) -> str | None:
    url = f"{GH_API}/repos/{repo}/releases/latest"
    headers = {"User-Agent": "dotfiles-install/1.0"}
    token = (
        os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
    )
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    data = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read())
            break
        except (URLError, ConnectionError, OSError) as e:
            if attempt == _MAX_RETRIES:
                print(
                    f"⚠  Failed to fetch {repo} releases after {_MAX_RETRIES} attempts: {e}"
                )
                return None
            time.sleep(_RETRY_DELAY * attempt)

    if data is None:
        return None

    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(("checksums.txt", ".zsync")):
            continue
        if re.search(pattern, name):
            return asset["browser_download_url"]
    return None


def _find_binary(dir_path: Path, binary_name: str) -> Path | None:
    for path in dir_path.rglob(binary_name):
        if path.is_file():
            return path
    return None


def install_release_binary(repo: str, binary: str, pattern: str) -> bool:
    if which(binary):
        print(f"✅ {binary} already installed")
        return True

    print(f"📥 Installing {binary} from {repo}")

    url = _latest_asset_url(repo, pattern)
    if not url:
        print(f"⚠️  No release asset matched pattern '{pattern}' for {repo}")
        return False

    tmpdir = Path(tempfile.mkdtemp())
    filename = url.split("/")[-1]
    archive = tmpdir / filename

    try:
        download(url, archive)

        if archive.name.endswith(".tar.gz"):
            run(["tar", "-xzf", str(archive), "-C", str(tmpdir)])
        elif archive.name.endswith(".tar.xz"):
            run(["tar", "-xJf", str(archive), "-C", str(tmpdir)])
        elif archive.name.endswith(".zip"):
            run(["unzip", "-q", str(archive), "-d", str(tmpdir)])
        else:
            print(f"⚠️  Unsupported archive format: {filename}")
            return False

        found = _find_binary(tmpdir, binary)
        if not found:
            print(f"⚠️  Could not find '{binary}' inside {filename}")
            return False

        BIN_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(found, BIN_DIR / binary)
        (BIN_DIR / binary).chmod(0o755)
        print(f"   → {BIN_DIR / binary}")
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def remove_binary(binary_name: str) -> bool:
    target = BIN_DIR / binary_name
    if target.exists():
        target.unlink()
        print(f"   removed {BIN_DIR / binary_name}")
        return True
    print(f"   (not found: {BIN_DIR / binary_name})")
    return False


def install_cli_tool(tool_name: str, info: dict) -> bool:
    os_name = detect_os()
    arch = detect_arch()
    pattern = info.get("asset_pattern")
    if pattern is None:
        pattern = _asset_pattern(tool_name, os_name, arch)
    if not pattern:
        print(f"⚠️  No asset pattern for {tool_name} on {os_name}/{arch}")
        return False
    return install_release_binary(info["repo"], info["binary"], pattern)
