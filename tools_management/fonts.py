import shutil
import tempfile
from pathlib import Path

from core import detect_os, download, run, run_optional, which
import manifest as mf

NF_VERSION = "3.4.0"


def _fonts_dir() -> Path:
    match detect_os():
        case "macos":
            return Path.home() / "Library" / "Fonts"
        case "linux":
            return Path.home() / ".local" / "share" / "fonts"
        case _:
            raise OSError("Unsupported OS")


def _font_installed(font_name: str, target: Path) -> bool:
    if not target.is_dir():
        return False
    for f in target.iterdir():
        if font_name.replace(" ", "") in f.name and f.suffix.lower() in (
            ".ttf",
            ".otf",
        ):
            return True
    return False


def install_nerd_font(font_name: str) -> bool:
    target = _fonts_dir()
    if _font_installed(font_name, target):
        print(f"✅ {font_name} Nerd Font already installed")
        return True

    url = f"https://github.com/ryanoasis/nerd-fonts/releases/download/v{NF_VERSION}/{font_name}.zip"
    print(f"📥 Downloading {font_name} Nerd Font v{NF_VERSION}...")

    tmpdir = Path(tempfile.mkdtemp())
    archive = tmpdir / f"{font_name}.zip"

    try:
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

        target.mkdir(parents=True, exist_ok=True)
        count = 0
        for f in (tmpdir / font_name).glob("*.ttf"):
            shutil.copy2(f, target / f.name)
            count += 1
        print(f"   Copied {count} .ttf files")
        print(f"✅ {font_name} Nerd Font installed")
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def update_cache() -> None:
    if detect_os() == "linux" and which("fc-cache"):
        print("🔄 Updating font cache...")
        run_optional(["fc-cache", "-fv", str(_fonts_dir())])


def _uninstall_fonts(_: dict) -> None:
    manifest = mf.saved_version()
    if not manifest:
        print("⚠️  No manifest found. Nothing to uninstall.")
        return
    to_remove = mf.get_uninstall_list(manifest, "fonts")
    if not to_remove:
        print("   (no fonts to uninstall)")
        return
    target = _fonts_dir()
    if not target.is_dir():
        print("   (fonts directory not found)")
        manifest["fonts"] = {"preexisting": [], "installed": []}
        mf.save(manifest)
        return
    print("🗑  Removing fonts...")
    for name in to_remove:
        removed = 0
        for f in target.iterdir():
            if name.replace(" ", "") in f.name and f.suffix.lower() in (".ttf", ".otf"):
                f.unlink()
                removed += 1
        print(f"   removed {removed} file(s) for {name}")
    manifest["fonts"] = {"preexisting": [], "installed": []}
    mf.save(manifest)


def install_fonts(config: dict, mode: str = "install") -> None:
    if mode == "uninstall":
        _uninstall_fonts(config)
        return
    fonts = config.get("fonts", [])
    if not fonts:
        return
    manifest = mf.load()
    installed = []
    for name in fonts:
        if install_nerd_font(name):
            installed.append(name)
    mf.record_installed(manifest, "fonts", installed)
    mf.save(manifest)
    update_cache()
    print()
