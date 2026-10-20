import json
import shutil
import sys
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
SAMPLE_PATH = CONFIG_PATH.with_name("config.sample.json")


def _create_from_sample() -> None:
    """config.json is machine-local and gitignored; seed it from the tracked sample."""
    if not SAMPLE_PATH.is_file():
        print(f"❌ Neither {CONFIG_PATH.name} nor {SAMPLE_PATH.name} found.")
        sys.exit(1)

    print(f"⚠️  {CONFIG_PATH.name} not found.")
    print(f"   It is machine-local (gitignored). {SAMPLE_PATH.name} has the defaults,")
    print("   with optional runtimes such as ruby disabled.")

    if sys.stdin.isatty():
        while True:
            answer = input(f"  Create {CONFIG_PATH.name} from {SAMPLE_PATH.name} and continue? [Y/n] ")
            answer = answer.strip().lower()
            if answer in ("", "y", "yes"):
                break
            if answer in ("n", "no"):
                print(f"  Aborted. Copy {SAMPLE_PATH.name} to {CONFIG_PATH.name} and edit it.")
                sys.exit(1)
    else:
        print("   (no terminal to ask — continuing with the sample)")

    shutil.copyfile(SAMPLE_PATH, CONFIG_PATH)
    print(f"   ✓ created {CONFIG_PATH.name} — edit it to enable optional runtimes\n")


def load() -> dict[str, Any]:
    """Load config.json from the install directory, seeding it from the sample if missing."""
    if not CONFIG_PATH.is_file():
        _create_from_sample()
    with open(CONFIG_PATH) as f:
        return json.load(f)


def cli_tool_enabled(config: dict, name: str) -> bool:
    """Check if a CLI tool is enabled in config."""
    tools = config.get("cli_tools", {})
    entry = tools.get(name)
    return entry is not None


def runtime_enabled(config: dict, name: str) -> bool:
    """Check if a runtime is enabled."""
    return config.get("runtimes", {}).get(name, True)


def post_install_enabled(config: dict, name: str) -> bool:
    """Check if a post-install step is enabled."""
    return config.get("post_install", {}).get(name, True)


def npm_package_enabled(config: dict, name: str) -> bool:
    """Check if an npm package is enabled in config."""
    pkgs = config.get("npm_packages", {})
    return pkgs.get(name) is not None
