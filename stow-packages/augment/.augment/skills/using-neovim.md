# Using Neovim MCP

## Purpose

Neovim MCP exists for **visualization and context sharing**, not for executing file operations.

- **Native tools** handle ALL file operations (use augment's native edit/write/grep/read tools).
- **MCP tools** are used ONLY to show results in Neovim and read user context.
- Do NOT use MCP to edit, search, or navigate files — native tools are faster and more reliable.

## Prerequisites

Neovim MCP must be connected first. If not connected, use the `editor-neovim` skill to establish a connection.

## Window Focus Step

**Always run this BEFORE any operation that opens a file, runs an LSP command, or switches buffers.**
It ensures the action happens in a normal file window, not the AI terminal panel:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype local bn = vim.api.nvim_buf_get_name(b) if bt == '' and bn ~= '' then vim.api.nvim_set_current_win(w) break end end")
```

## Tools Reference

| Tool | Purpose |
|------|---------|
| File operations | Use native tools (not MCP) |
| `neovim_vim_status` | Current buffer, cursor, LSP clients |
| `neovim_vim_buffer` | Read buffer the user has open (for context) |
| `neovim_vim_file_open` | Open a file in Neovim (show results) |
| `neovim_vim_command` | Run Vim commands (`:e`, `:copen`, `:checktime`, `:lua ...`) |
| `neovim_vim_grep` | Populate quickfix for user navigation |
| `neovim_vim_window` | Split/vsplit management for showing files |
| `neovim_vim_health` | Connection health check |

## Workflows

### "What is the user looking at?"

When the user says "this line", "this file", or "here" without specifying a path:

1. **Window Focus Step** (see above).
2. `neovim_vim_status` → returns active buffer filename, cursor position, LSP clients.
3. `neovim_vim_buffer(<filename>)` → read the buffer content if you need more context.

### Project-wide search (show results in quickfix)

1. Use native grep to find matches.
2. Populate quickfix: `neovim_vim_grep(<pattern>)` then `neovim_vim_command(":copen")`

### Apply edits and show results

1. Use native tools to edit files.
2. **Window Focus Step** (see above).
3. Open in Neovim: `neovim_vim_file_open(<path>)`
4. Reload changed buffers: `neovim_vim_command(":checktime")`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using MCP to edit instead of native tools | Use native edit/write |
| Opening a file without the **Window Focus Step** | Always run it first — the file opens in the AI terminal otherwise |
| Not opening the file after editing | Call `neovim_vim_file_open` so the user sees the result |
| Using MCP for code navigation | Use native read/grep |
