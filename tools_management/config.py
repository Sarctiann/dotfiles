import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load() -> dict[str, Any]:
    """Load config.json from the install directory."""
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
