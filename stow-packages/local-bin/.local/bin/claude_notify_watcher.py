#!/usr/bin/env python3
"""Watches Claude Code session transcripts and notifies through agent-notify when that Claude needs you.

Replacement for the Stop / Notification hooks, which the work org policy (allowManagedHooksOnly) disables, and
for Claude's own terminal_bell, which waits ~60s after a turn ends. It runs outside Claude Code (started once per
login from .zshrc; a lock keeps a single instance) and only reads session transcripts of every config dir:
~/.claude, $COMPANY_DIR/.claude_work_profile (nvim picks one per project) and $CLAUDE_CONFIG_DIR.

For the claude that writes the session (it keeps <tmp>/claude-<uid>/<project>/<session id>/ open; else every
claude in the cwd the session started in) it runs
`agent-notify emit --source claude --pid PID`, which rings that claude's tmux pane; agent-notify decides whether
you are already watching it. Works on Linux, WSL and macOS (ps / lsof, no /proc).

Signals (inferred from the transcript format, may break on Claude Code updates):
  - assistant message with stop_reason "end_turn"          -> done
  - AskUserQuestion / ExitPlanMode tool_use                -> ask (immediately)
  - any other tool_use without tool_result after DELAY s (SLOW_DELAY for slow tools),
    and no process spawned by that session's claude since -> permission
"""
import fcntl
import glob
import importlib.machinery
import importlib.util
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time


def config_dirs():
    dirs = [os.path.expanduser("~/.claude"), os.environ.get("CLAUDE_CONFIG_DIR", "")]
    company = os.environ.get("COMPANY_DIR", "")
    if company:
        dirs.append(os.path.join(os.path.expanduser(company), ".claude_work_profile"))
    return sorted({os.path.realpath(d) for d in dirs if d and os.path.isdir(d)})


CONFIG_DIRS = config_dirs()
# Auto-approved tools without a child process finish in <0.2s (p95), so 2s separates them from a permission
# prompt. Slow tools that also spawn no process (MCP, web, ToolSearch) need a longer wait.
DELAY = float(os.environ.get("CLAUDE_NOTIFY_DELAY", "2"))
SLOW_DELAY = float(os.environ.get("CLAUDE_NOTIFY_SLOW_DELAY", "6"))
SLOW_TOOLS = {"WebFetch", "WebSearch", "ToolSearch"}
POLL = 0.5
ACTIVE_WINDOW = 15 * 60  # only follow transcripts modified in the last 15 min
ASK_TOOLS = {"AskUserQuestion", "ExitPlanMode"}
SKIP_TOOLS = {"Agent", "Task", "Workflow"}  # long-running by nature, no child process to detect
AGENT_NOTIFY = os.path.join(os.path.dirname(os.path.realpath(__file__)), "agent-notify")


def etime_seconds(etime):
    """ps etime ([[dd-]hh:]mm:ss) -> seconds"""
    days, _, rest = etime.rpartition("-")
    secs = 0
    for part in rest.split(":"):
        secs = secs * 60 + int(part)
    return secs + int(days or 0) * 86400


def procs():
    """pid -> (ppid, start_wall_time, command basename)"""
    now = time.time()
    out = {}
    try:
        lines = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,etime=,comm="], capture_output=True, text=True,
                               timeout=5).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        return out
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            out[int(parts[0])] = (int(parts[1]), now - etime_seconds(parts[2]), os.path.basename(parts[3]))
        except ValueError:
            continue
    return out


def cwd_of(pid):
    if platform.system() != "Darwin":
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            return ""
    try:
        out = subprocess.run(["lsof", "-a", "-d", "cwd", "-p", str(pid), "-Fn"], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    return next((l[1:] for l in out.splitlines() if l.startswith("n")), "")


def claudes_in(cwd, ps):
    return [pid for pid, (_, _, comm) in ps.items() if comm == "claude" and cwd_of(pid) == cwd]


def open_files(pid):
    if platform.system() != "Darwin":
        try:
            fds = os.listdir(f"/proc/{pid}/fd")
        except OSError:
            return []
        files = []
        for fd in fds:  # claude opens and closes files all the time: skip the ones gone since listdir
            try:
                files.append(os.readlink(f"/proc/{pid}/fd/{fd}"))
            except OSError:
                continue
        return files
    try:
        out = subprocess.run(["lsof", "-p", str(pid), "-Fn"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [l[1:] for l in out.splitlines() if l.startswith("n")]


def claudes_of(session_id, cwd, ps):
    """The claude that writes this session: it keeps <tmp>/claude-<uid>/<project>/<session id>/tasks open.

    Falls back to every claude in the session's starting cwd (several sessions may share it) when none does.
    """
    marker = f"/{session_id}/"
    own = [pid for pid, (_, _, comm) in ps.items()
           if comm == "claude" and any(marker in f + "/" for f in open_files(pid))]
    return own or claudes_in(cwd, ps)


def load_agent_notify():
    """agent-notify as a module (it has no .py extension), for its log(): one log, one rotation."""
    try:
        loader = importlib.machinery.SourceFileLoader("agent_notify", AGENT_NOTIFY)
        spec = importlib.util.spec_from_loader("agent_notify", loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    except (OSError, SyntaxError, ImportError):
        return None


_agent_notify = load_agent_notify()


def log(msg):
    """Logs to agent-notify's log (~/.local/state/agent-notify.log)."""
    if _agent_notify:
        _agent_notify.log(msg)


def notify(session_id, cwd, event):
    pids = claudes_of(session_id, cwd, procs())
    log(f"watcher: claude {event} session {session_id[:8]} ({cwd}) -> pids {pids}")
    for pid in pids:
        try:
            subprocess.run([AGENT_NOTIFY, "emit", "--source", "claude", "--event", event, "--pid", str(pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.SubprocessError) as e:
            log(f"watcher: agent-notify failed: {e}")


def tool_is_running(session_id, cwd, since):
    """True if the session's claude has a descendant started after `since`."""
    ps = procs()
    children = {}
    for pid, (ppid, *_) in ps.items():
        children.setdefault(ppid, []).append(pid)
    stack = claudes_of(session_id, cwd, ps)
    while stack:
        for c in children.get(stack.pop(), []):
            if ps[c][1] >= since:
                return True
            stack.append(c)
    return False


def start_cwd(path):
    """The cwd the session started in, which is the claude process' cwd.

    Every transcript entry carries the session's *current* cwd, which follows `cd` in Bash commands, while the
    process stays where it started.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    cwd = json.loads(line).get("cwd")
                except (ValueError, AttributeError):
                    continue
                if cwd:
                    return cwd
    except OSError:
        pass
    return ""


class Session:
    def __init__(self, path):
        self.path = path
        self.session_id = os.path.splitext(os.path.basename(path))[0]
        self.offset = os.path.getsize(path)  # don't replay history
        self.start_cwd = start_cwd(path)
        self.buf = ""
        self.pending = {}  # tool_use_id -> (name, seen_at, cwd)
        self.done_msgs = set()

    def read(self):
        try:
            size = os.path.getsize(self.path)
        except OSError:
            return
        if size < self.offset:
            self.offset = 0
        if size == self.offset:
            return
        with open(self.path, encoding="utf-8", errors="replace") as f:
            f.seek(self.offset)
            self.buf += f.read()
            self.offset = f.tell()
        *lines, self.buf = self.buf.split("\n")
        for line in lines:
            try:
                self.handle(json.loads(line))
            except (ValueError, AttributeError):
                continue

    def handle(self, d):
        if d.get("isSidechain"):
            return
        msg = d.get("message") or {}
        content = msg.get("content")
        if not self.start_cwd:
            self.start_cwd = d.get("cwd") or ""
        cwd = self.start_cwd
        if d.get("type") == "assistant":
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name in ASK_TOOLS:
                        notify(self.session_id, cwd, "ask")
                    elif name not in SKIP_TOOLS:
                        self.pending[block.get("id")] = (name, time.time(), cwd)
            if msg.get("stop_reason") == "end_turn" and msg.get("id") not in self.done_msgs:
                self.done_msgs.add(msg.get("id"))
                self.pending.clear()
                notify(self.session_id, cwd, "done")
        elif d.get("type") == "user":
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    self.pending.pop(block.get("tool_use_id"), None)

    def check_pending(self):
        now = time.time()
        for tid, (name, seen, cwd) in list(self.pending.items()):
            slow = name in SLOW_TOOLS or name.startswith("mcp__")
            if now - seen < (SLOW_DELAY if slow else DELAY):
                continue
            del self.pending[tid]  # decide once per tool call
            if not tool_is_running(self.session_id, cwd, seen - 3):
                notify(self.session_id, cwd, "permission")


def single_instance():
    """Holds an exclusive lock for the life of the process; exits if another watcher has it."""
    lock = open(os.path.join(tempfile.gettempdir(), f"claude-notify-watcher-{os.getuid()}.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)
    return lock


def main():
    signal.signal(signal.SIGHUP, signal.SIG_IGN)  # outlive the terminal that started it
    _lock = single_instance()
    log(f"watcher: started, watching {CONFIG_DIRS}")
    sessions = {}
    while True:
        now = time.time()
        paths = [p for d in CONFIG_DIRS for p in glob.glob(os.path.join(d, "projects", "*", "*.jsonl"))]
        for path in paths:
            try:
                if now - os.path.getmtime(path) > ACTIVE_WINDOW:
                    sessions.pop(path, None)
                    continue
            except OSError:
                continue
            try:
                if path not in sessions:
                    sessions[path] = Session(path)
                sessions[path].read()
            except Exception as e:  # never let one transcript stop the watcher
                log(f"watcher: {path}: {e!r}")
        for s in sessions.values():
            try:
                s.check_pending()
            except Exception as e:
                log(f"watcher: {s.path}: {e!r}")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
