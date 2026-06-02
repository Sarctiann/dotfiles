---
name: agent-sync-neovim
description: Use when synchronizing Neovim MCP permissions with agent definitions in opencode.jsonc. Trigger keywords: "sync agents", "sync neovim agents", "update agent definitions", "propagate agent changes", "sync agent configs".
---

# Agent Sync Neovim

Update the Neovim MCP permissions file (`opencode_nvim_mcps.jsonc`) to match the current agent definitions in `opencode.jsonc`.

## Scope

| Path | Access |
| ----- | ------ |
| `~/.config/opencode/opencode.jsonc` | read-only — source of agent names |
| `~/.config/nvim/lua/utils/opencode-neovim/opencode_nvim_mcps.jsonc` | read/write — sync target |

## Workflow

### 1. Read Current State

Read `opencode.jsonc` to identify all agent names and their permissions.

### 2. Update Neovim MCP Permissions

Edit `~/.config/nvim/lua/utils/opencode-neovim/opencode_nvim_mcps.jsonc` so its agent permissions match the definitions in `opencode.jsonc`.

### 3. Verify Consistency

- Every agent in `opencode.jsonc` has a matching permission entry in `opencode_nvim_mcps.jsonc`
- No stale agent entries remain in `opencode_nvim_mcps.jsonc`
- The file remains valid JSONC

### 4. Report Changes

Summarize what was updated.

## Notes

- Do not modify `opencode.jsonc` or `agents/*.md`
- Remind the user to restart Neovim after updating the integration files
