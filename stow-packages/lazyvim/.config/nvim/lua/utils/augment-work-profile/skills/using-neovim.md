# Using Neovim MCP

## Purpose

Neovim MCP exists for **visualization and context sharing**, not for executing file operations.

- **Native tools** handle ALL file operations (use augment's native edit/write/grep/read tools).
- **MCP tools** are used ONLY to show results in Neovim and read user context.
- Do NOT use MCP to edit, search, or navigate files — native tools are faster and more reliable.

## Prerequisites

Neovim MCP must be connected first. If not connected, use the `connect-to-neovim` skill to establish a connection.

## File Opening Protocol (Strict — Follow Exactly)

**When you need to open one or more files in Neovim, follow these steps in order:**

### Step 1 — Find files
Use native tools (grep, glob, read) to locate which files to open. Collect their absolute paths.

### Step 2 — Verify MCP connection
Confirm the Neovim MCP is active. If not, use `connect-to-neovim` skill first.

### Step 3 — Focus a normal file window
**Always focus a window that contains a real file buffer.**
The Lua code below explicitly excludes:
- **Neo-tree** (and any `nofile`/`acwrite` buffers)
- **TUI/integration terminals** (and any other special `buftype`)
Only windows with `buftype == ''` qualify.

#### Standalone (focus only)
Use before LSP commands, quickfix navigation, or buffer switches:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end")
```

### Step 4 — Open files in editable mode

#### Single file — Combined Focus + Open (preferred)
**No round-trip pause.** Focuses a normal window and opens the file in a single MCP call:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path>')")
```

Replace `<path>` with the absolute file path.
#### Multiple files — `:badd` for all

**Always use this pattern for multiple files** — adds all files to the buffer list. The user navigates between them via bufferline. **No splits are created.**

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path-1> | badd <path-2> | badd <path-3>')")
```

For 2 files:
```
neovim_vim_command(":lua ... vim.cmd('badd <path-A> | badd <path-B>')")
```

If you already focused a normal window in a previous step:
```
neovim_vim_command(":badd <path-1> | badd <path-2>")
```

## Tools Reference

| Tool | Purpose |
|------|---------|
| File operations | Use native tools (not MCP) |
| `neovim_vim_status` | Current buffer, cursor, LSP clients |
| `neovim_vim_buffer` | Read buffer the user has open (for context) |
| `neovim_vim_command` | Run Vim commands (`:e`, `:copen`, `:checktime`, `:lua ...`) |
| `neovim_vim_grep` | Populate quickfix for user navigation |
| `neovim_vim_window` | Split/vsplit management for showing files |
| `neovim_vim_health` | Connection health check |

## Deprecated Tools

Do NOT use these MCP tools:

- `vim_file_open_neovim` / `neovim_vim_file_open` — use **Combined Focus + Open** instead (see above); standalone `vim_file_open` opens in the AI terminal panel

## Workflows

### "What is the user looking at?"

When the user says "this line", "this file", or "here" without specifying a path:

1. **Window Focus Step** (Step 3 above).
2. `neovim_vim_status` → returns active buffer filename, cursor position, LSP clients.
3. `neovim_vim_buffer(<filename>)` → read the buffer content if you need more context.

### Project-wide search (show results in quickfix)

1. Use native grep to find matches.
2. Populate quickfix: `neovim_vim_grep(<pattern>)` then `neovim_vim_command(":copen")`

### Apply edits and show results

1. Use native tools to edit files.
2. Open in Neovim with **Combined Focus + Open** (Step 4 above).
3. Reload changed buffers: `neovim_vim_command(":checktime")`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using MCP to edit instead of native tools | Use native edit/write |
| Opening a file without the **Window Focus Step** | Always focus first — the file opens in the AI terminal otherwise |
| Opening a file as two MCP calls (focus + open) | Use **Combined Focus + Open** — one call, no pause |
| Not opening the file after editing | Use **Combined Focus + Open** so the user sees the result |
| Creating splits for multiple files               | Use `:badd` for all files — no splits, user navigates via bufferline |
| Using MCP for code navigation | Use native read/grep |
