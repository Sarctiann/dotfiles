"""Tests for agent-notify, the Claude transcript watcher and the opencode-notifier configuration."""

import contextlib
import fcntl
import io
import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import termios
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools_management"))

import post_install  # noqa: E402  # pyright: ignore[reportMissingImports]  (path added above)

BIN = REPO_ROOT / "stow-packages/local-bin/.local/bin"
AGENT_NOTIFY = BIN / "agent-notify"

# Answers tmux's list-panes / list-clients / display / show from files, keeps "set -p ... @agent_last VALUE" for
# later "show" calls (like tmux would) and logs every call.
FAKE_TMUX = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os, sys
    d = os.environ["FAKE_TMUX_DIR"]
    with open(os.path.join(d, "calls.log"), "a") as log:
        log.write(" ".join(sys.argv[1:]) + "\\n")
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name == "set" and "@agent_last" in sys.argv:
        with open(os.path.join(d, "show"), "w") as f:
            f.write(sys.argv[sys.argv.index("@agent_last") + 1] + "\\n")
    if name in ("list-panes", "list-clients", "display", "show") and os.path.exists(os.path.join(d, name)):
        sys.stdout.write(open(os.path.join(d, name)).read())
    """
)


def read_pty(master, timeout=1.0) -> bytes:
    out = b""
    while select.select([master], [], [], timeout)[0]:
        out += os.read(master, 1024)
        timeout = 0.2
    return out


class FakeTmux:
    def __init__(self, tmp: Path):
        self.dir = tmp
        (tmp / "bin").mkdir()
        tmux = tmp / "bin/tmux"
        tmux.write_text(FAKE_TMUX)
        tmux.chmod(0o755)
        self.env = {
            **os.environ,
            "FAKE_TMUX_DIR": str(tmp),
            "XDG_STATE_HOME": str(tmp),
            "PATH": f"{tmp / 'bin'}:{os.environ['PATH']}",
        }

    def answer(self, name: str, rows: list[list[str]]) -> None:
        (self.dir / name).write_text("".join("\t".join(r) + "\n" for r in rows))

    def calls(self) -> str:
        log = self.dir / "calls.log"
        return log.read_text() if log.exists() else ""


def own_terminal(slave: int):
    def setup() -> None:
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

    return setup


class EmitTest(unittest.TestCase):
    """`agent-notify emit` notifies every tmux client unless you are watching that agent."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmux = FakeTmux(Path(self._tmp.name))
        self.agent_master, self.agent_slave = pty.openpty()  # the agent's terminal (a tmux pane)
        self.client_master, self.client_slave = pty.openpty()  # the terminal tmux runs in
        self.tmux.answer("list-panes", [[os.ttyname(self.agent_slave), "%1"]])
        self.agents: list[subprocess.Popen] = []
        self.extra_fds: list[int] = []
        self.agent = self.start_agent(self.agent_slave)

    def tearDown(self) -> None:
        for agent in self.agents:
            agent.kill()
            agent.wait()
        for fd in (self.agent_master, self.agent_slave, self.client_master, self.client_slave, *self.extra_fds):
            os.close(fd)
        self._tmp.cleanup()

    def start_agent(self, slave: int, env=None) -> subprocess.Popen:
        """A stand-in agent process whose controlling terminal is `slave`."""
        agent = subprocess.Popen(
            ["sleep", "60"], stdin=slave, env={**os.environ, **(env or {})}, preexec_fn=own_terminal(slave),
        )
        self.agents.append(agent)
        return agent

    def new_pty(self) -> tuple[int, int]:
        master, slave = pty.openpty()
        self.extra_fds += [master, slave]
        return master, slave

    def emit(self, pane_active="1", client_flags="attached,focused,UTF-8", client_window="@3",
             term="xterm-256color", event="done", agent=None, env=None):
        self.tmux.answer("display", [["@3", pane_active, "work:3"]])
        self.tmux.answer("list-clients", [[os.ttyname(self.client_slave), term, client_flags, client_window, "work"]])
        result = subprocess.run(
            [str(AGENT_NOTIFY), "emit", "--source", "claude", "--event", event,
             "--pid", str((agent or self.agent).pid)],
            env={**self.tmux.env, **(env or {})}, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return read_pty(self.client_master, 0.5)

    def test_watching_the_agent_notifies_nothing(self) -> None:
        self.assertEqual(self.emit(), b"")
        self.assertNotIn("@agent_alert", self.tmux.calls())

    def test_unfocused_terminal_rings_and_marks_the_window(self) -> None:
        self.assertEqual(self.emit(client_flags="attached,UTF-8"), b"\x07")
        self.assertIn("set -w -t @3 @agent_alert 1", self.tmux.calls())

    def test_other_window_on_screen_rings(self) -> None:
        self.assertEqual(self.emit(client_window="@1"), b"\x07")

    def test_inactive_pane_of_the_window_on_screen_rings(self) -> None:
        self.assertEqual(self.emit(pane_active="0"), b"\x07")

    def test_ghostty_gets_an_osc9_notification(self) -> None:
        out = self.emit(client_window="@1", term="xterm-ghostty")
        self.assertEqual(out, b"\x1b]9;claude \xc2\xb7 work:3: done\x1b\\\x07")

    def test_same_event_of_the_same_agent_notifies_once(self) -> None:
        self.assertEqual(self.emit(client_window="@1", event="permission"), b"\x07")
        self.assertEqual(self.emit(client_window="@1", event="permission"), b"")
        self.assertEqual(self.emit(client_window="@1", event="done"), b"\x07")

    def test_agents_sharing_a_pane_dont_hide_each_other(self) -> None:
        """Two Neovim :terminals (two ptys) shown in the same tmux pane."""
        _, other_slave = self.new_pty()
        other = self.start_agent(other_slave)
        self.tmux.answer("list-panes", [[os.ttyname(self.agent_slave), "%1"], [os.ttyname(other_slave), "%1"]])
        self.assertEqual(self.emit(client_window="@1"), b"\x07")
        self.assertEqual(self.emit(client_window="@1", agent=other), b"\x07")
        self.assertEqual(self.emit(client_window="@1"), b"")

    def test_agent_terminal_is_never_rung_inside_tmux(self) -> None:
        self.emit(client_flags="attached,UTF-8")
        self.assertEqual(read_pty(self.agent_master, 0.2), b"")

    def test_outside_tmux_rings_the_agents_terminal(self) -> None:
        self.tmux.answer("list-panes", [])
        self.emit(env={"TERM": "xterm-256color"})
        self.assertEqual(read_pty(self.agent_master), b"\x07")

    def test_outside_tmux_uses_the_agent_terminals_term(self) -> None:
        """The watcher daemon's own TERM says nothing about the terminal the agent runs in."""
        self.tmux.answer("list-panes", [])
        master, slave = self.new_pty()
        ghostty_agent = self.start_agent(slave, env={"TERM": "xterm-ghostty"})
        self.emit(agent=ghostty_agent, env={"TERM": "tmux-256color"})
        self.assertEqual(read_pty(master), b"\x1b]9;claude: done\x1b\\\x07")


class AlertHookTest(unittest.TestCase):
    """`agent-notify alert` (native bells) rings the clients on other sessions; tmux rang the others."""

    def test_rings_only_clients_on_other_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmux = FakeTmux(Path(tmp))
            same_m, same_s = pty.openpty()
            other_m, other_s = pty.openpty()
            try:
                tmux.answer("display", [["work"]])
                tmux.answer("list-clients", [
                    [os.ttyname(same_s), "xterm-256color", "attached,focused", "@3", "work"],
                    [os.ttyname(other_s), "xterm-256color", "attached,focused", "@9", "home"],
                ])
                result = subprocess.run([str(AGENT_NOTIFY), "alert", "@3"], env=tmux.env, capture_output=True,
                                        timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(read_pty(same_m, 0.3), b"")
                self.assertEqual(read_pty(other_m, 0.5), b"\x07")
            finally:
                for fd in (same_m, same_s, other_m, other_s):
                    os.close(fd)


class WatcherTest(unittest.TestCase):
    def test_parses_ps_elapsed_time(self) -> None:
        watcher: dict = {"__name__": "watcher", "__file__": str(BIN / "claude_notify_watcher.py")}
        exec(compile((BIN / "claude_notify_watcher.py").read_text(), "watcher", "exec"), watcher)
        etime_seconds = watcher["etime_seconds"]
        self.assertEqual(etime_seconds("05:03"), 303)
        self.assertEqual(etime_seconds("02:00:01"), 7201)
        self.assertEqual(etime_seconds("1-00:00:10"), 86410)

    def test_finds_the_open_session_directory(self) -> None:
        watcher: dict = {"__name__": "watcher", "__file__": str(BIN / "claude_notify_watcher.py")}
        exec(compile((BIN / "claude_notify_watcher.py").read_text(), "watcher", "exec"), watcher)
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "0a8c0f10-e323-441c-ada5-d0fa4fdf4e7a" / "tasks"
            session.mkdir(parents=True)
            fd = os.open(session, os.O_RDONLY)
            try:
                self.assertIn(str(session), watcher["open_files"](os.getpid()))
            finally:
                os.close(fd)
            self.assertTrue(callable(watcher["log"]))
            self.assertIsNotNone(watcher["_agent_notify"], "the watcher couldn't load agent-notify")


class NotifierConfigTest(unittest.TestCase):
    def write_config(self) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"HOME": tmp}), contextlib.redirect_stdout(io.StringIO()):
                post_install._write_notifier_config()
            path = Path(tmp) / ".config/opencode/opencode-notifier.json"
            self.assertTrue(path.is_file())
            config = json.loads(path.read_text())
            self.assertEqual(config["command"]["path"], str(Path(tmp) / ".local/bin/agent-notify"))
            return config

    def test_opencode_notifies_through_agent_notify(self) -> None:
        config = self.write_config()
        self.assertFalse(config["notification"])
        self.assertFalse(config["sound"])
        self.assertFalse(config["bell"])
        self.assertFalse(config["suppressWhenFocused"], "agent-notify, not the plugin, decides if you're watching")
        self.assertTrue(config["command"]["enabled"])
        self.assertEqual(
            config["command"]["args"],
            ["emit", "--source", "opencode", "--event", "{event}", "--message", "{message}"],
        )
        self.assertFalse(config["events"]["session_started"])
        self.assertNotIn("notificationSystem", config)

if __name__ == "__main__":
    unittest.main()
