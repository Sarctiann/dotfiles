# AGENTS.md

## ⚠️ CRITICAL RULE: Neovim Window Focus (Read This Before Any MCP File Open)

When opening a file in Neovim via MCP, you MUST focus a normal file window first.
**If you skip this, the file opens in the AI terminal panel (unmodifiable, no line numbers).**

Use a SINGLE combined command to avoid a round-trip pause:

```
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype local bn = vim.api.nvim_buf_get_name(b) if bt == '' and bn ~= '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('edit <path>')")
```

Replace `<path>` with the absolute file path. The `using-neovim` skill has details and a standalone variant for LSP/quickfix operations.

---

## Language

- All interactive messages to the user must be in **Spanish**, brief and to the point.
- Everything persisted to disk (file names, code, comments, documentation, commit messages, plans, etc.)
  must be in **English**, unless the user explicitly requests otherwise.

## Git

- Never create a git commit unless the user explicitly asks you to.

## Response Style

- Keep responses concise. List file changes as bullet points without explanations or justifications,
  unless the user explicitly requests them.
- Do not override response rules defined in sub-directory `AGENTS.md` files or loaded Skills.

## Workflow

- Check for `AGENTS.md` files in sub-directories when working on files inside them, and follow those too.
- You may modify any `AGENTS.md` file to keep it aligned with the project's current rules and conventions.
- Before using any skill, assess whether the task actually requires it. If it does, use the skill without asking.
- If the user says "Do it without asking", skip all confirmation prompts and proceed autonomously based on
  your best understanding of their intent.

---

## ⚠️ CRITICAL RULE: File Storage Location

**ALL agent-generated files MUST be stored in the project's work profile directory,
NOT here (`~/.augment/`).**

This includes:

| Artifact               | Path                                          |
| ---------------------- | --------------------------------------------- |
| Plans                  | `<work-profile>/plans/`                       |
| Notes / scratch files  | `<work-profile>/`                             |
| Any other agent output | `<work-profile>/`                             |

### ❌ NEVER use

- `~/.augment/plans/`
- `~/.augment/` (any subdirectory)

### ✅ ALWAYS use

- The project's `.augment_work_profile` directory for plans and artifacts.

**Rationale**: `~/.augment/` is a system-level directory shared across all projects and
users. The project work profile is project-scoped, version-control-adjacent,
and visible to the team working on the project.

---

## Agentic Skills

**Before responding to any request, ALSO check `./skills/` for a matching skill.**
If a skill matches the request, follow it exactly — user-level skills take precedence over project-level skills.

## Directory Structure

```
~/.augment/
├── AGENTS.md          ← This file (rules for agents)
└── skills/            ← User-level skills (checked on every request)
    └── *.md
```

---

## Plan File Conventions

- **Naming**: `plan-<feature-or-ticket>-<YYYY-MM-DD>.md`
- **Example**: `plan-kaia-thread-cc15571-2026-05-04.md`
- Plans should include: feasibility verdict, architecture analysis, files to change,
  implementation steps as checkboxes.
- Mark steps `[x]` as they are completed during implementation.
