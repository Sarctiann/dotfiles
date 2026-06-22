import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

DOTFILES_DIR = Path(__file__).resolve().parent.parent
STOW_DIR = DOTFILES_DIR / "stow-packages"
BIN_DIR = Path.home() / ".local" / "bin"
CREDENTIALS_SAVE_DIR = (
    Path.home() / ".local" / "share" / "dotfiles" / "saved-credentials"
)

os.environ.setdefault("PATH", "")
if str(BIN_DIR) not in os.environ["PATH"]:
    os.environ["PATH"] = f"{BIN_DIR}:{os.environ['PATH']}"

INTERACTIVE = False
STOW_PLAN: set[str] | None = None
COLD = False


def confirm(prompt: str, default: bool = True) -> bool:
    if not INTERACTIVE:
        return True
    hint = " [Y/n]" if default else " [y/N]"
    while True:
        r = input(f"  {prompt}{hint} ").strip().lower()
        if not r:
            return default
        if r in ("y", "yes"):
            return True
        if r in ("n", "no"):
            return False


def detect_os() -> str:
    """Returns 'macos', 'linux', or 'unknown'."""
    match platform.system().lower():
        case "darwin":
            return "macos"
        case "linux":
            return "linux"
        case _:
            return "unknown"


def detect_arch() -> str:
    """Returns normalized architecture: 'arm64', 'x86_64', or raw value."""
    match platform.machine().lower():
        case "arm64" | "aarch64":
            return "arm64"
        case "x86_64":
            return "x86_64"
        case m:
            return m


def gh_arch() -> str:
    """GitHub CLI convention: amd64 for x86_64, arm64 for arm64."""
    return "amd64" if detect_arch() == "x86_64" else "arm64"


def rz_arch() -> str:
    """ripgrep/fd/bat convention: aarch64 for arm64, x86_64 otherwise."""
    return "aarch64" if detect_arch() == "arm64" else detect_arch()


def is_wsl() -> bool:
    """Detect if running under WSL."""
    if os.environ.get("DOTFILES_WSL") == "1":
        return True
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text()
        return "microsoft" in release.lower()
    except (FileNotFoundError, OSError):
        return False


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, print it, raise on error."""
    print(f"   $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def run_optional(cmd: list[str], **kwargs) -> subprocess.CompletedProcess | None:
    """Run a command, print it, return None on failure instead of raising."""
    try:
        print(f"   $ {' '.join(cmd)}")
        return subprocess.run(cmd, check=True, **kwargs)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def download(url: str, dest: Path) -> None:
    """Download a URL to a file path, with retries on transient errors."""
    print(f"   ⬇  {url.split('/')[-1]}")
    for attempt in range(1, 4):
        try:
            with urlopen(url) as resp:
                dest.write_bytes(resp.read())
            return
        except (URLError, ConnectionError, OSError):
            if attempt == 3:
                raise
            time.sleep(2 * attempt)


def which(name: str) -> bool:
    """Check if a command is available on PATH or in BIN_DIR."""
    if subprocess.run(["which", name], capture_output=True).returncode == 0:
        return True
    return (BIN_DIR / name).is_file()


def safe_rmtree(path: Path) -> None:
    """Delete a directory tree, but preserve any .credentials files first."""
    if not path.exists():
        return
    if path.is_file():
        path.unlink()
        return
    creds = sorted(path.rglob(".credentials"))
    saved = 0
    for f in creds:
        rel = f.relative_to(path)
        dest = CREDENTIALS_SAVE_DIR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        saved += 1
    if saved:
        print(f"  ⚠️  preserved {saved} .credentials file(s) to {CREDENTIALS_SAVE_DIR}")
    shutil.rmtree(path)
