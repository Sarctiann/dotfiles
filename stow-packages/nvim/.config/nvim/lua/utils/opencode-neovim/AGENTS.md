# Neovim Integration Rules

This file only adds rules for OpenCode sessions launched from Neovim. Global user rules live in the parent `AGENTS.md`.

## Role of Neovim MCP

Neovim MCP exists for **visualization and context sharing**, NOT for executing file operations.

### Use MCP only for:
- **Showing results** — after native edits, open the file so the user sees it
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
