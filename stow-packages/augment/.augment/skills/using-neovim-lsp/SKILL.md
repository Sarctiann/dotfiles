---
name: using-neovim-lsp
description: Protocol for using LSP features through the Neovim MCP server for read-only context (hover, diagnostics, definitions) — never for file-modifying operations like rename or format. Use when the user needs LSP info via Neovim.
---

# Using Neovim LSP via MCP

## Purpose

LSP through Neovim MCP is for **reading context** (hover info, diagnostics, checking which language server is active). Do NOT use MCP to perform file operations like renaming or formatting — use native tools instead.

**Requires:** Neovim MCP active. See `using-neovim` skill.

## Window Focus Step

LSP operations require being in a normal file window. **Always run this before any LSP
command** to ensure focus is on a file buffer, not the AI terminal panel.

The Lua code explicitly excludes Neo-tree (`nofile`), TUI terminals (`terminal`), and
any other special `buftype` — only windows with `buftype == ''` qualify:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end")
```

## Check LSP Status

`neovim_vim_status()` — returns "lspInfo" field.

If `lspInfo` is "LSP information unavailable", no LSP client is attached.

## Quick Reference (Read-Only Operations)

**Always run the Window Focus Step before these.**

| Operation | Command |
|-----------|---------|
| Go to definition | `neovim_vim_command(":lua vim.lsp.buf.definition()")` |
| Go to type definition | `neovim_vim_command(":lua vim.lsp.buf.type_definition()")` |
| Show hover info | `neovim_vim_command(":lua vim.lsp.buf.hover()")` |
| Buffer diagnostics → loclist | `neovim_vim_command(":lua vim.diagnostic.setloclist()")` |
| Show diagnostic at cursor | `neovim_vim_command(":lua vim.diagnostic.open_float()")` |
| List workspace symbols | `neovim_vim_command(":lua vim.lsp.buf.workspace_symbol('query')")` |
| List document symbols | `neovim_vim_command(":lua vim.lsp.buf.document_symbol()")` |

## Operations to AVOID via MCP

| Operation | Why | Native Alternative |
|-----------|-----|-------------------|
| **Rename symbol** | MCP applies changes invisibly | native grep + edit |
| **Format buffer** | Use the project's formatter | run formatter CLI |
| **Code actions** | Unreliable through MCP | use native tools |
| **Find references** | native grep is more thorough | native grep |
| **All diagnostics → quickfix** | Use lint/typecheck commands | run linter directly |

## No LSP Client — Fallback

If no LSP is attached: use native grep for search, native read/grep for code understanding.
