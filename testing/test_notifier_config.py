"""Tests for the WSL opencode-notifier configuration and wrapper."""

import contextlib
import io
import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools_management"))

import post_install  # noqa: E402

WRAPPER = REPO_ROOT / "stow-packages/local-bin/.local/bin/opencode-notify-wsl"


class WslNotifierConfigTest(unittest.TestCase):
    def test_wsl_windows_terminal_configures_the_bell_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wrapper = home / ".local/bin/opencode-notify-wsl"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("#!/usr/bin/env bash\n")

            with (
                patch.dict(os.environ, {"HOME": tmp}),
                patch.object(post_install, "is_wsl", return_value=True),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                post_install._write_notifier_config(
                    {"stow": {"ghostty_or_windowsTerminal": True}}
                )

            config_path = home / ".config/opencode/opencode-notifier.json"
            self.assertTrue(config_path.is_file())
            config = json.loads(config_path.read_text())

        self.assertFalse(config["notification"])
        self.assertFalse(config["sound"])
        self.assertFalse(config["bell"])
        self.assertTrue(config["command"]["enabled"])
        self.assertEqual(config["command"]["path"], str(wrapper))
        self.assertEqual(config["command"]["args"], ["{message}", "{projectName}"])
        self.assertFalse(config["events"]["subagent_complete"])
        self.assertFalse(config["events"]["user_cancelled"])
        self.assertFalse(config["events"]["session_started"])
        self.assertFalse(config["events"]["user_message"])
        self.assertFalse(config["events"]["client_connected"])
        self.assertNotIn("notificationSystem", config)


class WslNotifierWrapperTest(unittest.TestCase):
    def test_wrapper_rings_the_bell_in_the_callers_terminal(self) -> None:
        master, slave = pty.openpty()
        try:
            result = subprocess.run(
                [str(WRAPPER), "Session finished", "cauce"],
                stdin=slave,
                capture_output=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            ready, _, _ = select.select([master], [], [], 2)
            self.assertTrue(ready, "nothing was written to the terminal")
            self.assertIn(b"\x07", os.read(master, 64))
        finally:
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()
