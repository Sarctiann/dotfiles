# Neovim Integration Rules

This file only adds rules for OpenCode sessions launched from Neovim. Global user rules live in the parent `AGENTS.md`.

## Role of Neovim MCP

Neovim MCP exists for **visualization and context sharing**, NOT for executing file operations.

### Use MCP only for:
- **Showing results** — after native edits, use **Combined Focus + Open** so the user sees it
- **Reading user context** — call `neovim_vim_status` when the user says "this line" / "this file" without specifying paths
- **Populating quickfix** — `neovim_vim_grep` + `:copen` after project-wide work so the user can navigate results

### Do NOT use MCP for:
- File editing (use native `edit`/`write`)
- Searching or replacing text (use native `grep`/`edit`)
- Renaming symbols (use native `grep` + `edit`)
- Navigating code (use native `read`/`grep`/glob)
- Window focus switching (removed — impractical and error-prone)

## When MCP is Active

Invoke the `using-neovim` skill for detailed guidance on visualization patterns.

## Deprecated MCP Tools

- `neovim_vim_edit` — use native `edit`/`write`
- `neovim_vim_buffer_save` — use native `write`
- `neovim_vim_search` / `neovim_vim_search_replace` — use native `grep`/`edit`
- `neovim_vim_mark` / `neovim_vim_visual` — broken (MCP server bug)
- `neovim_vim_file_open` — use **Combined Focus + Open** instead (opens in the AI terminal panel otherwise)

---

## ⚠️ CRITICAL RULE: Neovim Window Focus

When opening a file in Neovim via MCP, you MUST focus a normal file window first.
**If you skip this, the file opens in the AI terminal panel (unmodifiable, no line numbers).**

Use a SINGLE combined command to avoid a round-trip pause:

### Single file

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path>')")
```

Replace `<path>` with the absolute file path.

### Multiple files — `:badd` for all

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path-1> | badd <path-2> | badd <path-3>')")
```

The `using-neovim` skill has details and a standalone variant for LSP/quickfix operations.

## Multi-Client Synchronization

The three skills in `./skills/` (`using-neovim`, `using-neovim-lsp`, `using-quickfix`) are
**ported to three clients** and MUST be kept in sync:

| Client | Location |
|--------|----------|
| **OpenCode** (native) | `./skills/<name>/SKILL.md` |
| **Augment** (user-level) | `~/.augment/skills/<name>.md` (stow-managed) |
| **Augment** (work-profile) | `<work-profile>/skills/<name>.md` (neovim-deployed) |
| **Gemini CLI** | `~/.gemini/custom-skills/<name>/SKILL.md` (stow-managed) |

**Rule**: Any change to a skill in `./skills/` MUST be replicated to all three augment
locations and the gemini custom-skills directory. The content is identical except for
client-specific details (prerequisites section, connection instructions).
