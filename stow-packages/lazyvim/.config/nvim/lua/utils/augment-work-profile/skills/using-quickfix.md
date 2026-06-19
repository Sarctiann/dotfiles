# Using Quickfix List

## Purpose

The quickfix list lets the user navigate multi-file results with `:cn` / `:cp` / `:copen`. Populate it only **after** doing the actual work with native tools — it's a visualization aid, not a work mechanism.

**Requires:** Neovim MCP active. See `using-neovim` skill.

## Window Focus Step

Quickfix navigation commands (`:cn`, `:cp`, `:cfirst`) open files in the focused window.
**Always run this before navigating** to ensure files open in the main window, not the
AI terminal.

The Lua code explicitly excludes Neo-tree (`nofile`), TUI terminals (`terminal`), and
any other special `buftype` — only windows with `buftype == ''` and a non-empty filename
qualify:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype local bn = vim.api.nvim_buf_get_name(b) if bt == '' and bn ~= '' then vim.api.nvim_set_current_win(w) break end end")
```

## When to Use

- After a project-wide search via native grep — show results so user can browse
- After collecting references — populate quickfix for navigation
- Before multi-file edits — show scope so the user can review

## Core Pattern

### 1. Do the actual search with native tools

Use native grep to find matches.

### 2. Populate quickfix for user navigation

```
neovim_vim_grep(<pattern>)
neovim_vim_command(":copen")
```

### 3. Navigate programmatically

```
neovim_vim_command(":cfirst")   // jump to first match
neovim_vim_command(":cn")       // next match
neovim_vim_command(":cp")       // previous match
```

### 4. Read quickfix entries programmatically

```
neovim_vim_command(":lua print(vim.fn.json_encode(vim.fn.getqflist()))")
```

## Multi-File Edit Workflow

1. Use native grep/glob to identify which files to edit.
2. `neovim_vim_grep(<pattern>)` + `:copen` to show the scope.
3. Apply edits with native tools.
4. Reload buffers: `neovim_vim_command(":checktime")`.
5. `neovim_vim_command(":cclose")` when done.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using vim_grep as primary search tool | Use native grep — vim_grep is only for showing results |
| Making multi-file edits without showing scope first | Populate quickfix before editing |
| Forgetting to open quickfix after populating | Always call `neovim_vim_command(":copen")` |
| Quickfix navigation without **Window Focus Step** | Files open in the AI terminal instead of the main window |
