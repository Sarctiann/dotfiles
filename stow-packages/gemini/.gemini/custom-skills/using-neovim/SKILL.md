---
name: using-neovim
description: Use when the neovim MCP is available, or when the user mentions neovim, opening/closing/reading files in an editor, buffer navigation, text editing via editor, or any interaction with a text editor integrated session.
---

# Using Neovim MCP

## Purpose

Neovim MCP exists for **visualization and context sharing**, not for executing file operations.

- **Native tools** handle ALL file operations.
- **MCP tools** are used ONLY to show results in Neovim and read user context.

## Prerequisites

Neovim MCP must be connected. Gemini connects automatically via the configured `nvim` MCP server in settings.json. If connection fails, check that Neovim is running.

## Window Focus Step

**Always focus a normal file window before any operation that opens a file, runs an LSP command, or switches buffers.**

### Standalone (focus only)
Use before LSP commands, quickfix navigation, or buffer switches:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end")
```

### Combined Focus + Open (preferred for file opening)
**No round-trip pause.** Focuses a normal window and opens the file in a single MCP call:

#### Single file

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path>')")
```

#### Multiple files — `:badd` for all

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path-1> | badd <path-2> | badd <path-3>')")
```

## Tools Reference

| Tool | Purpose |
|------|---------|
| File operations | Use native tools (not MCP) |
| `neovim_vim_status` | Current buffer, cursor, LSP clients |
| `neovim_vim_buffer` | Read buffer the user has open |
| `neovim_vim_command` | Run Vim commands |
| `neovim_vim_grep` | Populate quickfix for navigation |
| `neovim_vim_window` | Split/vsplit management |
| `neovim_vim_health` | Connection health check |

## Deprecated Tools

Do NOT use these MCP tools:

- `neovim_vim_file_open` — use **Combined Focus + Open** instead (see above); standalone `vim_file_open` opens in the AI terminal panel

## Workflows

### "What is the user looking at?"

1. **Window Focus Step** (see above).
2. `neovim_vim_status` → active buffer, cursor, LSP clients
3. `neovim_vim_buffer` → read buffer content for context

### Apply edits and show results

1. Use native tools to edit files.
2. Open in Neovim with **Combined Focus + Open** (see above).
3. `neovim_vim_command(":checktime")` to reload buffers

### Project-wide search

1. Use native grep for the search
2. `neovim_vim_grep(<pattern>)` then `neovim_vim_command(":copen")`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using MCP to edit instead of native tools | Use native edit/write |
| Opening a file without the **Window Focus Step** | Always focus first — the file opens in the AI terminal otherwise |
| Opening a file as two MCP calls (focus + open) | Use **Combined Focus + Open** — one call, no pause |
| Not opening file after editing | Use **Combined Focus + Open** so user sees result |
| Using MCP for code navigation | Use native read/grep |
