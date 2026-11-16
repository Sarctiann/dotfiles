#!/usr/bin/env python3
"""Watches Claude Code session transcripts and fires Windows toasts via claude-notify-wsl.

Replacement for the Stop / Notification hooks, which the work org policy (allowManagedHooksOnly) disables.
It runs outside Claude Code (started once per boot from .zshrc) and only reads session transcripts of every
config dir: ~/.claude, $COMPANY_DIR/.claude_work_profile (nvim picks one per project) and $CLAUDE_CONFIG_DIR.

Signals (inferred from the transcript format, may break on Claude Code updates):
  - assistant message with stop_reason "end_turn"          -> "Claude terminó"
  - AskUserQuestion / ExitPlanMode tool_use                -> "Claude te espera" (immediately)
  - any other tool_use without tool_result after DELAY s,
    and no process spawned by that session's claude since -> "Claude necesita permiso"
"""
import glob
import json
import os
import subprocess
import time

def config_dirs():
    dirs = [os.path.expanduser("~/.claude"), os.environ.get("CLAUDE_CONFIG_DIR", "")]
    company = os.environ.get("COMPANY_DIR", "")
    if company:
        dirs.append(os.path.join(os.path.expanduser(company), ".claude_work_profile"))
    return sorted({os.path.realpath(d) for d in dirs if d and os.path.isdir(d)})


CONFIG_DIRS = config_dirs()
NOTIFY = os.path.join(os.path.dirname(os.path.realpath(__file__)), "claude-notify-wsl")
DELAY = float(os.environ.get("CLAUDE_NOTIFY_DELAY", "6"))
POLL = 1.0
ACTIVE_WINDOW = 15 * 60  # only follow transcripts modified in the last 15 min
ASK_TOOLS = {"AskUserQuestion", "ExitPlanMode"}
SKIP_TOOLS = {"Agent", "Task", "Workflow"}  # long-running by nature, no child process to detect

CLK_TCK = os.sysconf("SC_CLK_TCK")
with open("/proc/stat") as f:
    BOOT_TIME = next(int(l.split()[1]) for l in f if l.startswith("btime"))


def notify(event, cwd, ntype="", message=""):
    payload = {"hook_event_name": event, "cwd": cwd, "notification_type": ntype, "message": message}
    env = dict(os.environ, CLAUDE_NOTIFY_VISIBLE=tmux_visibility(cwd))
    try:
        subprocess.run([NOTIFY], input=json.dumps(payload), text=True, timeout=10, env=env)
    except Exception:
        pass


def tmux(*args):
    try:
        return subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=3).stdout.splitlines()
    except Exception:
        return []


def tmux_visibility(cwd):
    """"1" if every claude in `cwd` runs in a tmux pane on screen, "0" if one is hidden, "" if not in tmux."""
    ps = procs()
    claudes = [pid for pid, (_, _, comm, pcwd) in ps.items() if comm == "claude" and pcwd == cwd]
    if not claudes:
        return ""
    shown_sessions = set(tmux("list-clients", "-F", "#{client_session}"))
    panes = {}
    for line in tmux("list-panes", "-a", "-F", "#{pane_pid} #{pane_active} #{window_active} #{session_name}"):
        pid, pane_active, window_active, session = line.split(" ", 3)
        panes[int(pid)] = pane_active == "1" and window_active == "1" and session in shown_sessions
    result = ""
    for pid in claudes:
        while pid > 1 and pid not in panes:
            pid = ps.get(pid, (0,))[0]
        if pid in panes:
            if not panes[pid]:
                return "0"
            result = "1"
    return result


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
    for pid, (ppid, *_rest) in ps.items():
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
        self.pending = {}  # tool_use_id -> (name, seen_at, cwd, summary)
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
                        notify("Notification", cwd, "elicitation_dialog", "Tiene una pregunta para vos")
                    elif name not in SKIP_TOOLS:
                        self.pending[block.get("id")] = (name, time.time(), cwd, summary(block))
            if msg.get("stop_reason") == "end_turn" and msg.get("id") not in self.done_msgs:
                self.done_msgs.add(msg.get("id"))
                self.pending.clear()
                notify("Stop", cwd)
        elif d.get("type") == "user":
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    self.pending.pop(block.get("tool_use_id"), None)

    def check_pending(self):
        now = time.time()
        for tid, (name, seen, cwd, summ) in list(self.pending.items()):
            if now - seen < DELAY:
                continue
            del self.pending[tid]  # decide once per tool call
            if not tool_is_running(cwd, seen - 3):
                notify("Notification", cwd, "permission_prompt", f"Permiso para {name}{summ}")


def summary(block):
    inp = block.get("input") or {}
    text = inp.get("description") or inp.get("file_path") or inp.get("command") or ""
    text = " ".join(str(text).split())
    return f": {text[:80]}" if text else ""


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
