---
name: using-neovim
description: Use when the neovim MCP is available, or when the user mentions neovim, opening/closing/reading files in an editor, buffer navigation, text editing via editor, or any interaction with a text editor integrated session.
---

# Using Neovim MCP

## Purpose

Neovim MCP exists for **visualization and context sharing**, not for executing file operations.

- **Native tools** (`edit`, `write`, `grep`, `read`, `glob`) handle ALL file operations.
- **MCP tools** are used ONLY to show results in Neovim and read user context.
- Do NOT use MCP to edit, search, or navigate files — native tools are faster and more reliable.

## Window Focus Step

**Always focus a normal file window before any operation that opens a file, runs an LSP command, or switches buffers.**

### Standalone (focus only)
Use before LSP commands, quickfix navigation, or buffer switches:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype local bn = vim.api.nvim_buf_get_name(b) if bt == '' and bn ~= '' then vim.api.nvim_set_current_win(w) break end end")
```

### Combined Focus + Open (preferred for file opening)
**No round-trip pause.** Focuses a normal window and opens the file in a single MCP call:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype local bn = vim.api.nvim_buf_get_name(b) if bt == '' and bn ~= '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('edit <path>')")
```

## Tools Reference

| Tool | MCP Name | Purpose |
|------|----------|---------|
| File operations | — | Use native `edit`/`write`/`grep`/`read`/`glob` |
| `vim_status` | `neovim_vim_status` | Current buffer, cursor, LSP clients |
| `vim_buffer` | `neovim_vim_buffer` | Read buffer the user has open (for context) |
| `vim_command` | `neovim_vim_command` | Run Vim commands (`:e`, `:copen`, `:checktime`, `:lua ...`) |
| `vim_grep` | `neovim_vim_grep` | Populate quickfix for user navigation |
| `vim_window` | `neovim_vim_window` | Split/vsplit management for showing files |
| `vim_health` | `neovim_vim_health` | Connection health check |

## Deprecated Tools

Do NOT use these MCP tools — native alternatives are superior:

- `neovim_vim_edit` — use native `edit`/`write`
- `neovim_vim_buffer_save` — use native `write`
- `neovim_vim_search` / `neovim_vim_search_replace` — use native `grep`/`edit`
- `neovim_vim_mark` / `neovim_vim_visual` — broken (MCP server bug)
- `neovim_vim_file_open` — use **Combined Focus + Open** instead (see above); standalone `vim_file_open` opens in the AI terminal panel

## Workflows

### Edit a file

1. Use native `edit`/`write` to modify the file on disk.
2. Run the formatter (if configured).
3. Open in Neovim with **Combined Focus + Open** (see above).

### "What is the user looking at?"

When the user says "this line", "this file", or "here" without specifying a path:

1. **Window Focus Step** (see above).
2. `neovim_vim_status` → returns active buffer filename, cursor position, LSP clients.
3. `neovim_vim_buffer(<filename>)` → read the buffer content if you need more context.
4. Respond.

### Project-wide search (show results in quickfix)

1. Use native `grep` to find matches.
2. Optionally populate quickfix so the user can navigate results:
   - `neovim_vim_grep(<pattern>)`
   - `neovim_vim_command(":copen")`
3. Apply edits with native tools.

### Reload buffers after native edits

- Current buffer only: `neovim_vim_command(":e")`
- All changed buffers: `neovim_vim_command(":checktime")`

### Open related files side by side

1. Open each file with **Combined Focus + Open** (see above).
2. `neovim_vim_window("split")` or `neovim_vim_window("vsplit")` to arrange.

## LSP Integration

`neovim_vim_status` returns attached LSP clients via the `lspInfo` field. LSP commands
require being in a file window — always run the **Window Focus Step** before them.
See the `using-neovim-lsp` skill for details.

## Quickfix List

Populate quickfix when you want the user to navigate multi-file results:

```
neovim_vim_grep(<pattern>)
neovim_vim_command(":copen")
```

Quickfix navigation commands (`:cn`, `:cp`, `:cfirst`) follow the focused window —
**Window Focus Step** before navigating. See the `using-quickfix` skill for details.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `neovim_vim_edit` instead of native tools | Use native `edit`/`write` |
| Using `neovim_vim_search` for buffer search | Use native `grep`/`read` |
| Using `neovim_vim_search_replace` | Use native `edit` |
| Opening a file without the **Window Focus Step** | Always run it first — the file opens in the AI terminal otherwise |
| Not opening the file after editing | Use **Combined Focus + Open** so the user sees the result |
| Using MCP for code navigation | Use native `read`/`grep`/`glob` |
