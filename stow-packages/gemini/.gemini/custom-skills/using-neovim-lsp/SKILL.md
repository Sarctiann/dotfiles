---
name: using-neovim-lsp
description: Use when navigating code symbols, finding definitions or references, renaming symbols, reading diagnostics, or any operation that benefits from the active LSP client in Neovim.
---

# Using Neovim LSP via MCP

## Purpose

LSP through Neovim MCP is for **reading context** (hover info, diagnostics, checking which language server is active). Do NOT use MCP for file operations.

**Requires:** Neovim MCP active. See `using-neovim` skill.

## Window Focus Step

LSP operations require being in a normal file window. **Always run this before any LSP
command** to ensure focus is on a file buffer, not the AI terminal panel:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype local bn = vim.api.nvim_buf_get_name(b) if bt == '' and bn ~= '' then vim.api.nvim_set_current_win(w) break end end")
```

## Quick Reference (Read-Only)

**Always run the Window Focus Step before these.**

| Operation | Command |
|-----------|---------|
| Go to definition | `neovim_vim_command(":lua vim.lsp.buf.definition()")` |
| Show hover info | `neovim_vim_command(":lua vim.lsp.buf.hover()")` |
| Buffer diagnostics → loclist | `neovim_vim_command(":lua vim.diagnostic.setloclist()")` |
| List workspace symbols | `neovim_vim_command(":lua vim.lsp.buf.workspace_symbol('query')")` |

## Operations to AVOID via MCP

| Operation | Native Alternative |
|-----------|-------------------|
| Rename symbol | native grep + edit |
| Format buffer | run formatter CLI |
| Find references | native grep (more thorough) |

## No LSP Client — Fallback

If `neovim_vim_status` returns `lspInfo: "LSP information unavailable"`: use native grep for search, native read/grep for code understanding.
