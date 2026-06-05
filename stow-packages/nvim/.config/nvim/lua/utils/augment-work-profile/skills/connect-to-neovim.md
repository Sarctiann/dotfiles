# Skill: Connect to Neovim MCP

## Triggers

Execute this skill when any of the following occur:
- User asks to connect to Neovim or verify the Neovim connection
- `get_targets_nvim` returns "No Neovim targets found"
- A Neovim MCP tool call fails with a connection error
- User mentions working inside a Neovim terminal and wants MCP active
- Session start while running inside a Neovim embedded terminal

---

## Step 1 — Try automatic discovery

Call `get_targets_nvim`. If it returns a socket path, connect with `connect_nvim` and skip to Step 4.

---

## Step 2 — Read the $NVIM environment variable

When Augment runs inside a Neovim embedded terminal, the `$NVIM` env var contains the
exact socket path for that Neovim instance. This is the preferred socket to connect to.

```bash
echo "NVIM=$NVIM"
```

If `$NVIM` is non-empty, use that path directly with `connect_nvim`. Skip to Step 4.

---

## Step 3 — Fallback: find sockets manually

If `$NVIM` is empty (Augment is NOT running inside Neovim), search for active sockets:

```bash
find /var/folders -name "nvim.*" -type s 2>/dev/null | head -20
```

Pick the most recently modified socket. If multiple exist, prefer the one whose
directory name matches a known Neovim session. Connect with `connect_nvim`.

---

## Step 4 — Verify the connection

After connecting, the `connect_nvim` tool returns a `connection_id`. Cache it mentally
for the session. The connection is valid for the duration of the conversation.

**Preferred instance**: always prefer the socket from `$NVIM` — that is the Neovim
instance the user is actively working in.

---

## Step 5 — Report to user

Tell the user which socket was used and the connection_id, e.g.:

```
✅ Conectado a Neovim — connection_id: <id>
   Socket: $NVIM → <path>
```

---

## Hard Rules

- **Always prefer `$NVIM`** over other discovered sockets — it points to the instance
  where the user's terminal lives.
- Never use `connect_nvim` more than once per socket per session unless a tool call fails.
- If no socket is found at all, tell the user to open Neovim first or set `$NVIM`.
- Do NOT use the Neovim MCP for file editing — use native tools (view, str-replace-editor,
  launch-process). MCP is for visualization only (open files, run vim commands, read context).

---

## MCP Tools Available After Connection

| Tool | Purpose |
|------|---------|
| `get_targets_nvim` | Auto-discover sockets |
| `connect_nvim` | Connect via unix socket path |
| `connect_tcp_nvim` | Connect via TCP address |

Once connected, the nvim MCP exposes tools for reading buffers, running Vim commands,
opening files, and populating the quickfix list. See the `using-neovim` skill in
`~/.config/nvim/lua/utils/opencode-neovim/skills/` for usage patterns.
