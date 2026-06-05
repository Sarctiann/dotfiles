---
name: using-quickfix
description: Use when doing project-wide search, collecting LSP references or diagnostics, navigating multi-file results, or any workflow that benefits from the Neovim quickfix or location list.
---

# Using Quickfix List

## Purpose

The quickfix list lets the user navigate multi-file results. Populate it **after** doing the actual work with native tools.

**Requires:** Neovim MCP active. See `using-neovim` skill.

## Window Focus Step

Quickfix navigation commands (`:cn`, `:cp`, `:cfirst`) open files in the focused window.
**Always run this before navigating** to ensure files open in the main window, not the
AI terminal:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype local bn = vim.api.nvim_buf_get_name(b) if bt == '' and bn ~= '' then vim.api.nvim_set_current_win(w) break end end")
```

## When to Use

- After project-wide search via native grep — show results
- After collecting references — populate for navigation
- Before multi-file edits — show scope for review

## Core Pattern

### 1. Search with native tools

Use native grep to find matches.

### 2. Populate quickfix

```
neovim_vim_grep(<pattern>)
neovim_vim_command(":copen")
```

### 3. Navigate

```
neovim_vim_command(":cfirst")
neovim_vim_command(":cn")
neovim_vim_command(":cp")
```

### 4. Read entries programmatically

```
neovim_vim_command(":lua print(vim.fn.json_encode(vim.fn.getqflist()))")
```

## Multi-File Edit Workflow

1. Native grep/glob to find files
2. `neovim_vim_grep` + `:copen` to show scope
3. Apply edits with native tools
4. `neovim_vim_command(":checktime")` to reload
5. `neovim_vim_command(":cclose")` when done

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using vim_grep as primary search | Use native grep |
| Forgetting to open quickfix | Always call `:copen` after populating |
| Quickfix navigation without **Window Focus Step** | Files open in the AI terminal instead of the main window |
