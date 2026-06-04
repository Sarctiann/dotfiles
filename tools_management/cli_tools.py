from gh_releases import install_cli_tool, remove_binary
from core import which
import manifest as mf


def _preexisting_names(config: dict) -> list[str]:
    tools = config.get("cli_tools", {})
    preexisting = []
    for name, info in tools.items():
        if info is None:
            continue
        if which(info["binary"]):
            preexisting.append(name)
    return preexisting


def _uninstall_cli_tools(config: dict) -> None:
    manifest = mf.saved_version()
    if not manifest:
        print("⚠️  No manifest found. Nothing to uninstall.")
        return
    to_remove = mf.get_uninstall_list(manifest, "cli_tools")
    if not to_remove:
        print("   (no CLI tools to uninstall)")
        return
    print("🗑  Removing CLI tools...")
    tools = config.get("cli_tools", {})
    for name in to_remove:
        info = tools.get(name)
        if info is None:
            print(f"   (no config for {name}, skipping)")
            continue
        print(f"   → {name} ({info['binary']})")
        remove_binary(info["binary"])
    manifest["cli_tools"] = {"preexisting": [], "installed": []}
    mf.save(manifest)


def install_cli_tools(config: dict, mode: str = "install") -> None:
    tools = config.get("cli_tools", {})
    if not tools:
        return

    if mode == "uninstall":
        _uninstall_cli_tools(config)
        return

    if mode == "check":
        print("🛠  CLI tools:")
        for name, info in tools.items():
            if info is None:
                continue
            status = "✅" if which(info["binary"]) else "⬜"
            print(f"   {status} {name} ({info['binary']})")
        print()
        return

    print("🛠  Installing CLI tools from GitHub releases...")
    manifest = mf.load()
    mf.record_preexisting(manifest, "cli_tools", _preexisting_names(config))
    any_failed = False
    installed: list[str] = []
    for name, info in tools.items():
        if info is None:
            continue
        if not install_cli_tool(name, info):
            any_failed = True
        else:
            installed.append(name)
    mf.record_installed(manifest, "cli_tools", installed)
    mf.save(manifest)
    if any_failed:
        print("⚠️  Some tools failed to install (see above)")
    print()
