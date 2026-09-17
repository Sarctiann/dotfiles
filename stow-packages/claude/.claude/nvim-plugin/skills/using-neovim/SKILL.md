---
name: using-neovim
description: Protocol for using the Neovim MCP server for visualization and context sharing only — file operations must use native tools. Use when opening files in Neovim, checking what the user is looking at, or sharing edit results via Neovim.
---

# Skill: Using Neovim MCP

<!-- Ported from Augment's using-neovim skill. Tool names below assume the
     standard Claude Code MCP naming convention (mcp__<server>__<tool>) for
     the "nvim" server configured via --mcp-config. Verify the exact tool
     names once connected (list available tools) and adjust if nvim-mcp-server
     exposes a different naming scheme than Augment's nvim-mcp did. -->

## Purpose

Neovim MCP exists for **visualization and context sharing**, not for executing file operations.

- **Native tools** handle ALL file operations (Edit, Write, Grep, Read, Glob).
- **MCP tools** are used ONLY to show results in Neovim and read user context.
- Do NOT use MCP to edit, search, or navigate files — native tools are faster and more reliable.

## Prerequisites

The Neovim MCP server ("nvim") is connected automatically for the session via `--mcp-config` when Claude is launched from the Neovim integration. No separate connection step is needed.

## File Opening Protocol (Strict — Follow Exactly)

**When you need to open one or more files in Neovim, follow these steps in order:**

### Step 1 — Find files

Use native tools (Grep, Glob, Read) to locate which files to open. Collect their absolute paths.

### Step 2 — Focus a normal file window

**Always focus a window that contains a real file buffer.**
The Lua code below explicitly excludes:

- **Neo-tree** (and any `nofile`/`acwrite` buffers)
- **TUI/integration terminals** (and any other special `buftype`)
Only windows with `buftype == ''` qualify.

#### Standalone (focus only)

Use before LSP commands, quickfix navigation, or buffer switches:

```
mcp__nvim__vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end")
```

### Step 3 — Open files in editable mode

#### Single file — Combined Focus + Open (preferred)

**No round-trip pause.** Focuses a normal window and opens the file in a single MCP call:

```
mcp__nvim__vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path>')")
```

Replace `<path>` with the absolute file path.

#### Multiple files — `:badd` for all

**Always use this pattern for multiple files** — adds all files to the buffer list. The user navigates between them via bufferline. **No splits are created.**

```
mcp__nvim__vim_command(":lua ... vim.cmd('badd <path-1> | badd <path-2> | badd <path-3>')")
```

If you already focused a normal window in a previous step:

```
mcp__nvim__vim_command(":badd <path-1> | badd <path-2>")
```

## Tools Reference

| Tool                       | Purpose                                                     |
| -------------------------- | ------------------------------------------------------------ |
| File operations            | Use native tools (not MCP)                                  |
| `mcp__nvim__vim_status`    | Current buffer, cursor, LSP clients                         |
| `mcp__nvim__vim_buffer`    | Read buffer the user has open (for context)                 |
| `mcp__nvim__vim_command`   | Run Vim commands (`:e`, `:copen`, `:checktime`, `:lua ...`) |
| `mcp__nvim__vim_grep`      | Populate quickfix for user navigation                       |
| `mcp__nvim__vim_window`    | Split/vsplit management for showing files                   |
| `mcp__nvim__vim_health`    | Connection health check                                     |

## Workflows

### "What is the user looking at?"

When the user says "this line", "this file", or "here" without specifying a path:

1. **Window Focus Step** (Step 2 above).
2. `mcp__nvim__vim_status` → returns active buffer filename, cursor position, LSP clients.
3. `mcp__nvim__vim_buffer(<filename>)` → read the buffer content if you need more context.

### Project-wide search (show results in quickfix)

1. Use native Grep to find matches.
2. Populate quickfix: `mcp__nvim__vim_grep(<pattern>)` then `mcp__nvim__vim_command(":copen")`

### Apply edits and show results

1. Use native tools to edit files.
2. Open in Neovim with **Combined Focus + Open** (Step 3 above).
3. Reload changed buffers: `mcp__nvim__vim_command(":checktime")`

## Common Mistakes

| Mistake                                          | Fix                                                                   |
| ------------------------------------------------ | ---------------------------------------------------------------------- |
| Using MCP to edit instead of native tools        | Use native Edit/Write                                                 |
| Opening a file without the **Window Focus Step** | Always focus first — the file opens in the AI terminal otherwise      |
| Opening a file as two MCP calls (focus + open)   | Use **Combined Focus + Open** — one call, no pause                    |
| Not opening the file after editing               | Use **Combined Focus + Open** so the user sees the result             |
| Creating splits for multiple files               | Use `:badd` for all files — no splits, user navigates via bufferline |
| Using MCP for code navigation                    | Use native Read/Grep                                                  |
