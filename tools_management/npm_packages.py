from core import run, run_optional, which
import manifest as mf


def _try_bun_install(package_name: str, binary: str) -> bool:
    if not which("bun"):
        return False
    print("   trying bun...")
    try:
        run(["bun", "install", "-g", package_name])
        if which(binary):
            return True
    except Exception:
        pass
    return False


def _try_npm_install(package_name: str, binary: str) -> bool:
    print("   trying npm...")
    result = run_optional(["npm", "install", "-g", package_name])
    if result is None:
        return False
    return which(binary)


def _install_global_tool(package_name: str, binary: str) -> bool:
    if which(binary):
        print(f"✅ {binary} already installed")
        return True

    print(f"📦 Installing {binary} ({package_name})...")
    if _try_bun_install(package_name, binary):
        print(f"   → {binary} installed via bun")
        return True
    if _try_npm_install(package_name, binary):
        print(f"   → {binary} installed via npm")
        return True

    print(f"⚠️  {binary} not found on PATH after install (tried bun, npm)")
    return False


def _try_bun_uninstall(package_name: str, binary: str) -> bool:
    if not which("bun"):
        return False
    try:
        run(["bun", "uninstall", "-g", package_name])
        if not which(binary):
            return True
    except Exception:
        pass
    return False


def _try_npm_uninstall(package_name: str, binary: str) -> bool:
    result = run_optional(["npm", "uninstall", "-g", package_name])
    if result is None:
        return False
    return not which(binary)


def _uninstall_global_tool(package_name: str, binary: str) -> bool:
    if not which(binary):
        print(f"   (not installed: {binary})")
        return False
    print(f"🗑  Removing {binary} ({package_name})...")
    if _try_bun_uninstall(package_name, binary):
        print(f"   → {binary} removed (via bun)")
        return True
    _try_npm_uninstall(package_name, binary)
    print(f"   → {binary} removed (via npm)")
    return True


def _preexisting_names(config: dict) -> list[str]:
    pkgs = config.get("npm_packages", {})
    preexisting = []
    for name, info in pkgs.items():
        if info and which(info["binary"]):
            preexisting.append(name)
    return preexisting


def _uninstall_npm_packages(config: dict) -> None:
    manifest = mf.saved_version()
    if not manifest:
        print("⚠️  No manifest found. Nothing to uninstall.")
        return
    to_remove = mf.get_uninstall_list(manifest, "npm_packages")
    if not to_remove:
        print("   (no npm packages to uninstall)")
        return
    print("🗑  Removing npm global packages...")
    pkgs = config.get("npm_packages", {})
    for name in to_remove:
        info = pkgs.get(name)
        if info is None:
            print(f"   (no config for {name}, skipping)")
            continue
        _uninstall_global_tool(info["package"], info["binary"])
    manifest["npm_packages"] = {"preexisting": [], "installed": []}
    mf.save(manifest)


def install_npm_packages(config: dict, mode: str = "install") -> None:
    pkgs = config.get("npm_packages", {})
    if not pkgs:
        return

    if mode == "uninstall":
        _uninstall_npm_packages(config)
        return

    print("📦 Installing npm global packages...")
    manifest = mf.load()
    mf.record_preexisting(manifest, "npm_packages", _preexisting_names(config))
    installed: list[str] = []
    for name, info in pkgs.items():
        if info is None:
            continue
        if _install_global_tool(info["package"], info["binary"]):
            installed.append(name)
    mf.record_installed(manifest, "npm_packages", installed)
    mf.save(manifest)
    print()
