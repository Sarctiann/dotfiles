# Neovim Skills — Multi-Client Synchronization Spec

## Purpose

Three core skills (`using-neovim`, `using-neovim-lsp`, `using-quickfix`) provide AI
agents with the protocol for interacting with Neovim via MCP. These skills are
**ported identically** to three AI clients (OpenCode, Augment, Gemini CLI), each of
which has its own mechanism for discovering and loading them.

This document specifies:
- The Neovim procedures that every skill version **must** preserve
- The directory structure and loading mechanism per client
- What must stay in sync and what can differ
- How deployment is managed

---

## 1. Source of Truth

**Location:** `lua/utils/opencode-neovim/skills/<name>/SKILL.md`

This is the canonical version. Every change here **must** be replicated to all clients.

```
lua/utils/opencode-neovim/
├── AGENTS.md                            ← Multi-client sync rules
├── README.md
├── opencode_nvim_mcps.jsonc             ← MCP server + agent permissions
├── commands/                            ← OpenCode slash-commands
│   ├── nvim-context.md
│   ├── nvim-find.md
│   ├── nvim-refs.md
│   └── nvim-open-related.md
└── skills/                              ← SOURCE OF TRUTH
    ├── using-neovim/SKILL.md
    ├── using-neovim-lsp/SKILL.md
    └── using-quickfix/SKILL.md
```

---

## 2. Neovim Procedures — Must Preserve in ALL Clients

Every skill port **must** contain these procedures verbatim.

### 2.1 Window Focus Step

**Why:** Without it, files open in the AI terminal panel (unmodifiable, no line numbers).

**Standalone variant** (before LSP commands, quickfix navigation, buffer switches):

```lua
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end")
```

**Combined Focus + Open** (no round-trip pause — preferred for file opening):

Single file:
```lua
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path>')")
```

Multiple files (`:badd` for all):
```lua
neovim_vim_command(":lua for _, w in ipairs(vim.api.nvim_list_wins()) do local b = vim.api.nvim_win_get_buf(w) local bt = vim.bo[b].buftype if bt == '' then vim.api.nvim_set_current_win(w) break end end vim.cmd('badd <path-1> | badd <path-2> | badd <path-3>')")
```

### 2.2 Tools Reference

| Purpose | MCP Tool | Notes |
|---------|----------|-------|
| Current state | `neovim_vim_status` | Buffer, cursor, LSP clients |
| Read buffer | `neovim_vim_buffer` | User's open file |
| Run commands | `neovim_vim_command` | `:e`, `:copen`, `:checktime`, `:lua ...` |
| Quickfix search | `neovim_vim_grep` | Populate quickfix for navigation |
| Window mgmt | `neovim_vim_window` | split/vsplit |

### 2.3 Deprecated Tools — Never Use

- `neovim_vim_edit` → use native `edit`/`write`
- `neovim_vim_buffer_save` → use native `write`
- `neovim_vim_search` / `neovim_vim_search_replace` → use native `grep`/`edit`
- `neovim_vim_mark` / `neovim_vim_visual` (broken — MCP server bug)
- `neovim_vim_file_open` → use **Combined Focus + Open**

### 2.4 Key Workflows

- **"What is the user looking at?"** → Window Focus Step → `vim_status` → `vim_buffer`
- **Project-wide search** → native `grep` → `vim_grep` + `:copen` (show results)
- **Multi-file edits** → identify files → open with Combined Focus + Open → edit → `:checktime`
- **Reload buffers** → `:e` (current) / `:checktime` (all changed)

### 2.5 LSP Rules (using-neovim-lsp)

- Use ONLY for reading context (hover, definition, diagnostics, status)
- NEVER use for: rename (`grep`+`edit`), format (project formatter), find references (native `grep`)
- Always run Window Focus Step before any LSP command

### 2.6 Quickfix Rules (using-quickfix)

- Populate quickfix **after** doing work with native tools (visualization aid, not work mechanism)
- Always run Window Focus Step before navigating (`:cn`, `:cp`, `:cfirst`)
- Prefer quickfix over location list for agent-driven operations

---

## 3. Client-Specific Structures

### 3.1 OpenCode

| Aspect | Detail |
|--------|--------|
| **Skill format** | `skills/<name>/SKILL.md` (with YAML frontmatter `name`+`description`) |
| **Discovery** | OpenCode reads `skills/<name>/SKILL.md` from `OPENCODE_CONFIG_DIR` |
| **Config** | `opencode_nvim_mcps.jsonc` — MCP server def + agent skill permissions |
| **Agent rules** | `AGENTS.md` — multi-client sync rules, MCP usage policy |
| **Commands** | `commands/*.md` — slash-commands for context, find, refs, open-related |
| **Lua utils** | `opencode_utils.lua` — server lifecycle, session mgmt, tunnel |
| **MCP server** | `mcp-neovim-server` via npx, configured in opencode.jsonc |
| **Loading path** | `~/.config/opencode/` (stow-managed) + `OPENCODE_CONFIG_DIR` env var (points to Neovim dir) |

### 3.2 Augment (User-Level)

| Aspect | Detail |
|--------|--------|
| **Skill format** | `skills/<name>/SKILL.md` (with YAML frontmatter? depends on Augment version) |
| **Discovery** | Augment scans `skills/` on session start; skills appear in the skill picker |
| **Connect skill** | `editor-neovim/SKILL.md` — connects Neovim MCP (autodiscovery, `$NVIM`, fallback) |
| **Agent rules** | `AGENTS.md` — File Opening Protocol, language rules, work-profile redirection |
| **MCP server** | `mcp-neovim-server` via npx, configured in `~/.augment/settings.json` |
| **Loading path** | `~/.augment/` — deployed via stow from `stow-packages/augment/.augment/` |

**Note:** Augment user-level `AGENTS.md` redirects ALL agent-generated files to the
project's work profile. The user-level dir is only for system config and skills.

### 3.3 Augment (Work-Profile)

| Aspect | Detail |
|--------|--------|
| **Skill format** | `skills/<name>.md` (flat file, no subdirectory — differs from user-level) |
| **Discovery** | Augment reads `skills/*.md` from the work-profile cache dir |
| **Connect skill** | `connect-to-neovim.md` — Augment-specific connection protocol |
| **Agent rules** | `AGENTS.md` — same Neovim protocol + project-specific rules |
| **Deployment** | `augment_utils.lua:deploy_work_profile_config()` copies from Neovim source on every `auggie open` |
| **Loading path** | `<project>/.augment_work_profile/` — deployed by `augment_utils.lua` |

**Key difference from user-level:** Work-profile skills are `.md` flat files (not
`<name>/SKILL.md` subdirectories). The `connect-to-neovim.md` skill name also differs
from the user-level `editor-neovim`.

### 3.4 Gemini CLI

| Aspect | Detail |
|--------|--------|
| **Skill format** | `custom-skills/<name>/SKILL.md` (with YAML frontmatter, same as OpenCode) |
| **Discovery** | Gemini loads custom skills from `~/.gemini/custom-skills/<name>/SKILL.md` at session start |
| **Agent rules** | `GEMINI.md` (in `~/.gemini/`) |
| **MCP server** | `nvim-mcp-server` via npx, configured in `~/.gemini/settings.json` |
| **Loading path** | `~/.gemini/custom-skills/` — deployed via stow from `stow-packages/gemini/.gemini/` |
| **Lua utils** | `gemini_utils.lua` — session management (delete, list/resume) |

---

## 4. Synchronization Rules

### 4.1 What Must Be Identical Across All Clients

The following content **must** be word-for-word identical in every skill port:

- The **Window Focus Step** (both standalone and combined variants) — exact Lua code
- The **Tools Reference** table (tool names and purposes)
- The **Deprecated Tools** list
- The **Key Workflows** (what-is-user-looking-at, project-search, multi-file-edit, reload)
- The **LSP rules** (read-only operations, what to avoid via MCP)
- The **Quickfix rules** (populate after native work, window focus before navigate)
- The **Common Mistakes** tables

### 4.2 What Differs Per Client

| Element | OpenCode | Augment (user) | Augment (work) | Gemini |
|---------|----------|----------------|----------------|--------|
| **Skill file format** | `<name>/SKILL.md` | `<name>/SKILL.md` | `<name>.md` (flat) | `<name>/SKILL.md` |
| **Prerequisites section** | "When MCP is Active" | "If not connected, use `editor-neovim` skill" | "If not connected, use `connect-to-neovim` skill" | "Gemini connects automatically via configured MCP" |
| **Connect-to-Neovim skill** | N/A (MCP auto-starts) | `editor-neovim` | `connect-to-neovim` | N/A (auto-connect) |
| **Native tool names** | `edit`/`write`/`grep`/`read`/`glob` | "augment's native edit/write/grep/read tools" | "augment's native..." | "Native tools" |
| **Command/slash commands** | `commands/*.md` | N/A | N/A | N/A |
| **Agent permissions** | `opencode.jsonc` | N/A | N/A | N/A |

### 4.3 The Syncing Rule

**Any change to a skill in `lua/utils/opencode-neovim/skills/` MUST be replicated to:**

1. `~/.augment/skills/<name>/SKILL.md` (stow-managed, user-level Augment)
2. `<work-profile>/skills/<name>.md` (deployed via `augment_utils.lua`)
3. `~/.gemini/custom-skills/<name>/SKILL.md` (stow-managed, Gemini)

The content is identical except for:
- The **prerequisites section** (client-specific connection instructions)
- References to the **connect-to-neovim skill** name (different per Augment profile)
- **Native tool names** (generic "native tools" vs "augment's native tools")

---

## 5. Deployment Mechanisms

### 5.1 Stow (OpenCode + Augment user-level + Gemini)

```
stow-packages/opencode/.config/opencode/  →  ~/.config/opencode/
stow-packages/augment/.augment/            →  ~/.augment/
stow-packages/gemini/.gemini/              →  ~/.gemini/
```

Run `stow` from the repo root to deploy. Stow is the **single source of truth** for
these locations — never edit files in the target directly, always edit in `stow-packages/`.

### 5.2 Lua-based deploy (Augment work-profile)

`augment_utils.lua:deploy_work_profile_config()` runs automatically when Augment opens.
It copies from `lua/utils/augment-work-profile/` to the work-profile cache directory.

```
Source: lua/utils/augment-work-profile/
        ├── AGENTS.md
        └── skills/
            ├── using-neovim.md
            ├── using-neovim-lsp.md
            ├── using-quickfix.md
            └── connect-to-neovim.md

Target: <project>/.augment_work_profile/
        ├── AGENTS.md
        └── skills/
            ├── using-neovim.md
            ├── using-neovim-lsp.md
            ├── using-quickfix.md
            └── connect-to-neovim.md
```

### 5.3 Agent-based deploy (OpenCode commands)

The Neovim config dir (`lua/utils/opencode-neovim/`) is included via the `OPENCODE_CONFIG_DIR`
environment variable, set by `opencode_utils.lua` when the server starts. This makes
OpenCode discover the skills and commands in that directory automatically.

---

## 6. Change Checklist

When modifying any Neovim skill, follow this checklist:

- [ ] Edit the **source of truth** in `lua/utils/opencode-neovim/skills/<name>/SKILL.md`
- [ ] Replicate to `stow-packages/augment/.augment/skills/<name>/SKILL.md` (user-level)
- [ ] Replicate to `lua/utils/augment-work-profile/skills/<name>.md` (work-profile, flat file)
- [ ] Replicate to `stow-packages/gemini/.gemini/custom-skills/<name>/SKILL.md`
- [ ] Run `stow` to deploy changes that live under `stow-packages/`
- [ ] Verify: did any client-specific section change (prerequisites, tool names)?
- [ ] Verify: does the new content still preserve all Neovim procedures from §2?

---

## 7. File Inventory

| File | Purpose | Deploy Method |
|------|---------|--------------|
| `lua/utils/opencode-neovim/skills/<name>/SKILL.md` | Source of truth | `OPENCODE_CONFIG_DIR` env var |
| `lua/utils/opencode-neovim/opencode_nvim_mcps.jsonc` | MCP + agent permissions | `OPENCODE_CONFIG_DIR` env var |
| `lua/utils/opencode-neovim/commands/*.md` | OpenCode slash-commands | `OPENCODE_CONFIG_DIR` env var |
| `lua/utils/opencode-neovim/AGENTS.md` | OpenCode agent rules | `OPENCODE_CONFIG_DIR` env var |
| `lua/utils/augment-work-profile/skills/<name>.md` | Augment work-profile skills | `augment_utils.lua` |
| `lua/utils/augment-work-profile/AGENTS.md` | Work-profile agent rules | `augment_utils.lua` |
| `stow-packages/augment/.augment/skills/<name>/SKILL.md` | Augment user-level skills | `stow` |
| `stow-packages/augment/.augment/AGENTS.md` | Augment user-level rules | `stow` |
| `stow-packages/gemini/.gemini/custom-skills/<name>/SKILL.md` | Gemini custom skills | `stow` |
| `stow-packages/opencode/.config/opencode/AGENTS.md` | OpenCode global rules | `stow` |
