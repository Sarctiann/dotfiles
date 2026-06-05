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

## Tools Reference

| Tool | Purpose |
|------|---------|
| File operations | Use native tools (not MCP) |
| `neovim_vim_status` | Current buffer, cursor, LSP clients |
| `neovim_vim_buffer` | Read buffer the user has open |
| `neovim_vim_file_open` | Open a file in Neovim (show results) |
| `neovim_vim_command` | Run Vim commands |
| `neovim_vim_grep` | Populate quickfix for navigation |
| `neovim_vim_window` | Split/vsplit management |
| `neovim_vim_health` | Connection health check |

## Workflows

### "What is the user looking at?"

1. `neovim_vim_status` → active buffer, cursor, LSP clients
2. `neovim_vim_buffer` → read buffer content for context

### Project-wide search

1. Use native grep for the search
2. `neovim_vim_grep(<pattern>)` then `neovim_vim_command(":copen")`

### Apply edits and show results

1. Use native tools to edit files
2. `neovim_vim_file_open(<path>)` to show the result
3. `neovim_vim_command(":checktime")` to reload buffers

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using MCP to edit instead of native tools | Use native edit/write |
| Not opening file after editing | `neovim_vim_file_open` so user sees result |
| Using MCP for code navigation | Use native read/grep |
