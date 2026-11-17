"""Tests for the WSL opencode-notifier configuration and wrapper."""

import contextlib
import io
import json
import os
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
PS1 = (
    REPO_ROOT
    / "stow-packages/local-bin/.local/share/opencode-notifier/opencode-notify.ps1"
)


class WslNotifierConfigTest(unittest.TestCase):
    def test_wsl_windows_terminal_configures_a_powershell_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            wrapper = home / ".local/bin/opencode-notify-wsl"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("#!/usr/bin/env bash\n")

            ps1 = home / ".local/share/opencode-notifier/opencode-notify.ps1"
            ps1.parent.mkdir(parents=True)
            ps1.write_text("param()\n")

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
        self.assertFalse(config["command"]["enabled"])
        self.assertEqual(config["command"]["path"], str(wrapper))
        self.assertEqual(config["command"]["args"], ["{message}", "{projectName}"])
        self.assertFalse(config["events"]["subagent_complete"])
        self.assertFalse(config["events"]["user_cancelled"])
        self.assertFalse(config["events"]["session_started"])
        self.assertFalse(config["events"]["user_message"])
        self.assertFalse(config["events"]["client_connected"])
        self.assertNotIn("notificationSystem", config)


@unittest.skip("opencode-notify-wsl is disabled (exits at once) after IT security alerts")
class WslNotifierWrapperTest(unittest.TestCase):
    def test_wrapper_invokes_powershell_with_the_toast_script(self) -> None:
        self.assertTrue(WRAPPER.is_file(), f"missing wrapper: {WRAPPER}")
        self.assertTrue(PS1.is_file(), f"missing PowerShell script: {PS1}")

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            script = home / ".local/share/opencode-notifier/opencode-notify.ps1"
            script.parent.mkdir(parents=True)
            script.write_text("param()\n")

            bin_dir = home / "bin"
            bin_dir.mkdir()
            recorded = home / "recorded-args"
            fake_powershell = bin_dir / "powershell.exe"
            fake_powershell.write_text(
                "#!/usr/bin/env bash\n" 'printf "%s\\n" "$@" > "$HOME/recorded-args"\n'
            )
            fake_powershell.chmod(0o755)
            fake_wslpath = bin_dir / "wslpath"
            fake_wslpath.write_text(
                "#!/usr/bin/env bash\n" 'echo "C:\\\\fake\\\\opencode-notify.ps1"\n'
            )
            fake_wslpath.chmod(0o755)

            env = {
                **os.environ,
                "HOME": tmp,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "OPENCODE_NOTIFY_POWERSHELL": str(fake_powershell),
                "OPENCODE_NOTIFY_STYLE": "toast",
            }
            result = subprocess.run(
                [str(WRAPPER), "Session finished", "cauce"],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            args = recorded.read_text().splitlines()

        self.assertEqual(
            args,
            [
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "C:\\fake\\opencode-notify.ps1",
                "-Title",
                "OpenCode (cauce)",
                "-Message",
                "Session finished",
            ],
        )

    def test_wrapper_defaults_to_the_windows_terminal_popup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recorded = Path(tmp) / "recorded-args"
            fake_wt_notify = Path(tmp) / "wt-notify"
            fake_wt_notify.write_text(
                f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{recorded}"\n'
            )
            fake_wt_notify.chmod(0o755)
            env = {**os.environ, "OPENCODE_NOTIFY_WT_NOTIFY": str(fake_wt_notify)}
            env.pop("OPENCODE_NOTIFY_STYLE", None)
            result = subprocess.run(
                [str(WRAPPER), "Session finished", "cauce"],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            args = recorded.read_text().splitlines()

        self.assertEqual(args, ["OpenCode (cauce)", "Session finished", "#5C9CF5"])


if __name__ == "__main__":
    unittest.main()
