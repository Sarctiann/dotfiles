#!/usr/bin/env python3
"""Watches Claude Code session transcripts and rings the terminal bell of that Claude when it needs you.

Replacement for the Stop / Notification hooks, which the work org policy (allowManagedHooksOnly) disables, and
for Claude's own terminal_bell, which waits ~60s after a turn ends. It runs outside Claude Code (started once per
boot from .zshrc) and only reads session transcripts of every config dir: ~/.claude,
$COMPANY_DIR/.claude_work_profile (nvim picks one per project) and $CLAUDE_CONFIG_DIR.

The bell is written to the terminal of every claude running in the session's cwd, as if Claude rang it: an nvim
:terminal passes it on (belloff without "term"), tmux marks the window in the status bar and its alert-bell hook
forwards it to other sessions, and Windows Terminal plays the sound. Everything stays inside WSL: launching
powershell.exe from WSL raised malware alerts with the company's IT security.

Signals (inferred from the transcript format, may break on Claude Code updates):
  - assistant message with stop_reason "end_turn"          -> Claude finished
  - AskUserQuestion / ExitPlanMode tool_use                -> Claude asks something (immediately)
  - any other tool_use without tool_result after DELAY s (SLOW_DELAY for slow tools),
    and no process spawned by that session's claude since -> Claude waits for a permission
"""
import glob
import json
import os
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

CLK_TCK = os.sysconf("SC_CLK_TCK")
with open("/proc/stat") as f:
    BOOT_TIME = next(int(l.split()[1]) for l in f if l.startswith("btime"))


def ring(cwd):
    """Rings the bell in the terminal of every claude running in `cwd` (the transcript doesn't say which one)."""
    ttys = set()
    for pid, (_, _, comm, pcwd) in procs().items():
        if comm == "claude" and pcwd == cwd:
            try:
                tty = os.readlink(f"/proc/{pid}/fd/0")
            except OSError:
                continue
            if tty.startswith("/dev/pts/"):
                ttys.add(tty)
    for tty in ttys:
        try:
            with open(tty, "w") as t:
                t.write("\a")
        except OSError:
            pass


def procs():
    """pid -> (ppid, start_wall_time, comm, cwd)"""
    out = {}
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            with open(f"/proc/{p}/stat") as f:
                stat = f.read()
            comm = stat[stat.index("(") + 1:stat.rindex(")")]
            fields = stat[stat.rindex(")") + 2:].split()
            ppid, start = int(fields[1]), int(fields[19])
            try:
                cwd = os.readlink(f"/proc/{p}/cwd")
            except OSError:
                cwd = ""
            out[int(p)] = (ppid, BOOT_TIME + start / CLK_TCK, comm, cwd)
        except (OSError, ValueError):
            continue
    return out


def tool_is_running(cwd, since):
    """True if a claude process in `cwd` has a descendant started after `since`."""
    ps = procs()
    children = {}
    for pid, (ppid, *_) in ps.items():
        children.setdefault(ppid, []).append(pid)
    roots = [pid for pid, (_, _, comm, pcwd) in ps.items() if comm == "claude" and pcwd == cwd]
    stack = list(roots)
    while stack:
        for c in children.get(stack.pop(), []):
            if ps[c][1] >= since:
                return True
            stack.append(c)
    return False


class Session:
    def __init__(self, path):
        self.path = path
        self.offset = os.path.getsize(path)  # don't replay history
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
        cwd = d.get("cwd") or ""
        if d.get("type") == "assistant":
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_use":
                    name = block.get("name", "")
                    if name in ASK_TOOLS:
                        ring(cwd)
                    elif name not in SKIP_TOOLS:
                        self.pending[block.get("id")] = (name, time.time(), cwd)
            if msg.get("stop_reason") == "end_turn" and msg.get("id") not in self.done_msgs:
                self.done_msgs.add(msg.get("id"))
                self.pending.clear()
                ring(cwd)
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
            if not tool_is_running(cwd, seen - 3):
                ring(cwd)


def main():
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
            if path not in sessions:
                sessions[path] = Session(path)
            sessions[path].read()
        for s in sessions.values():
            s.check_pending()
        time.sleep(POLL)


if __name__ == "__main__":
    main()
