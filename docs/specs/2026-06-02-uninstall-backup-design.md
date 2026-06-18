# Uninstall + Stow Backup System

Date: 2026-06-02

## Motivation

The install system currently has no way to undo what it does. `stow -R` overwrites existing files without backup, and once a CLI tool or runtime is installed, there's no record of what was installed or what pre-existed. This spec adds:

1. A **manifest** that records what the installer did vs what the user already had
2. **Pre-stow backups** of existing files before symlinking
3. An **uninstall** command that reverses all install actions safely

## Architecture

### File layout

```
dotfiles/
├── install.sh              ← new: exec tools_management/1_setup.sh "$@"
├── uninstall.sh            ← new: exec tools_management/1_uninstall.sh "$@"
└── tools_management/
    ├── 1_setup.sh          ← unchanged (was install/1_setup.sh)
    ├── 1_uninstall.sh      ← new: bootstrap, exec 2_management.py uninstall
    ├── 2_management.py     ← renamed from 2_install.py, subcommand-based
    ├── manifest.py         ← new: create/read/validate/save manifest
    ├── config.json         ← unchanged
    ├── config.py           ← unchanged
    ├── core.py             ← unchanged
    ├── stow.py             ← modified: backup + restore
    ├── cli_tools.py        ← modified: mode-aware (install/uninstall)
    ├── runtimes.py         ← modified: mode-aware
    ├── fonts.py            ← modified: mode-aware
    ├── gh_releases.py      ← modified: add remove_binary()
    ├── post_install.py     ← modified: mode-aware
    ├── system_packages.py  ← unchanged
    └── verify.py           ← unchanged
```

- `install/` directory moves to `tools_management/` to reflect its broader role.
- `install.sh` and `uninstall.sh` at the repo root are thin shell wrappers that delegate.

### Entry points

```bash
./install.sh [--just PKG...] [-i]   → 1_setup.sh → 2_management.py install
./uninstall.sh [-f]                 → 1_uninstall.sh → 2_management.py uninstall
```

### CLI interface

```
# Install (same as today + manifest tracking)
python3 tools_management/2_management.py install [--just PKG...] [-i]

# Uninstall with confirmation
python3 tools_management/2_management.py uninstall   # prompts before destructive steps
python3 tools_management/2_management.py uninstall -f # force, skip confirmations
```

### `install.sh`

```bash
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/tools_management/1_setup.sh" "$@"
```

### `uninstall.sh`

```bash
#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/tools_management/1_uninstall.sh" "$@"
```

### `1_uninstall.sh`

Same bootstrap logic as `1_setup.sh` (Xcode CLI tools, Homebrew, python3) but then:

```bash
exec python3 "$SCRIPT_DIR/2_management.py" uninstall "$@"
```

## Manifest

### Storage

Two locations, written simultaneously after every successful install:

| Priority  | Path                                    | Purpose                               |
| --------- | --------------------------------------- | ------------------------------------- |
| Primary   | `~/.local/share/dotfiles/manifest.json` | Survives repo deletion                |
| Secondary | `tools_management/manifest.json`        | Versioned with repo, acts as fallback |

`load()` tries the runtime path first; if missing, falls back to the repo path.

### Format

```json
{
  "version": 1,
  "created_at": "2026-06-02T12:00:00",
  "updated_at": "2026-06-02T12:00:00",
  "system": {
    "os": "macos",
    "arch": "arm64"
  },
  "cli_tools": {
    "preexisting": ["gh", "fzf"],
    "installed": [
      "nvim",
      "rg",
      "fd",
      "bat",
      "lazygit",
      "lazydocker",
      "lazysql",
      "yazi"
    ]
  },
  "runtimes": {
    "preexisting": ["nvm"],
    "installed": ["bun", "rust", "opencode"]
  },
  "fonts": {
    "installed": ["CodeNewRoman", "NerdFontsSymbolsOnly"]
  },
  "stow": {
    "packages": ["zsh", "lazyvim", "tmux", "ghostty", "local-bin"],
    "backups": {
      ".config/nvim/init.lua": "/Users/sebas/.local/share/dotfiles/backups/lazyvim/init.lua",
      ".zshrc": "/Users/sebas/.local/share/dotfiles/backups/zsh/.zshrc"
    }
  },
  "post_install": {
    "tpm_installed": true,
    "windows_terminal_linked": false
  }
}
```

- `preexisting`: tools that were on the system before install (skipped during uninstall).
- `installed`: tools the installer added (target of uninstall).
- `stow.backups` keys are paths relative to `$HOME`. Values are absolute paths to backup copies.
- `updated_at` changes on re-install; `created_at` stays on first install.

### `manifest.py` API

```python
def create() -> dict
    """Return a blank manifest with version, timestamps, and empty sections."""

def record_preexisting(manifest: dict, section: str, names: list[str]) -> None
    """Mark items as preexisting (found before install)."""

def record_installed(manifest: dict, section: str, names: list[str]) -> None
    """Mark items as newly installed."""

def get_uninstall_list(manifest: dict, section: str) -> list[str]
    """Return only the 'installed' items for a section (excluding preexisting)."""

def save(manifest: dict) -> None
    """Write manifest to both runtime path (~/.local/share/dotfiles/) and repo path."""

def load() -> dict
    """Read from runtime path; fallback to repo path; return blank dict if neither exists."""

def exists() -> bool
    """Check if a manifest exists at either location."""

def delete() -> None
    """Remove manifest from both locations."""
```

## Stow Backup Mechanism

### Flow during install — `stow.py`

Before `stow -R`, each stow package is inspected:

1. List all files in `stow-packages/<pkg>/` recursively
2. For each file, compute its target path: `$HOME / <relative-path-under-pkg>`
   - Example: `stow-packages/lazyvim/.config/nvim/init.lua` → `~/.config/nvim/init.lua`
3. If the target exists and is NOT already a symlink pointing to our stow dir:
   - Copy to `~/.local/share/dotfiles/backups/<pkg>/<relative-path>`
   - Record in manifest: `stow.backups["<relative-path>"] = "<backup-abs-path>"`
4. Run `stow -R` (creates/updates symlinks)

This runs before every stow operation. On re-install, it re-checks: if the target is now our symlink, skip backup.

### Flow during uninstall — `stow.py`

1. For each package in `stow.packages`:
   - `stow -D <pkg>` (remove symlinks)
2. For each entry in `stow.backups`:
   - Copy the file from backup path back to its original location
   - This restores the exact file that existed before first install
3. Remove backup directories if empty
4. Clear `stow.backups` from the manifest (but keep the manifest for reference)

### Interaction with re-install

If the user runs install twice, the second run:

- Already has symlinks from the first run → no new backups needed
- May have updated packages → `stow -R` updates symlinks as usual
- If a package was added → backup only its targets

## Uninstall — Per-module behaviour

### `cli_tools.py`

- `install`: same as today, but before installing each tool, check `which(binary)` → if found, mark as `preexisting`
- `uninstall`: iterate `get_uninstall_list(manifest, "cli_tools")`, call `remove_binary(binary)` for each

### `gh_releases.py` — new function

```python
def remove_binary(binary_name: str) -> bool:
    """Remove a binary from BIN_DIR (~/.local/bin/)."""
    target = BIN_DIR / binary_name
    if target.exists():
        target.unlink()
        return True
    return False
```

### `runtimes.py`

Each runtime that was installed gets reversed. If a runtime binary is not found (already removed), the step warns and continues.

| Runtime  | Uninstall action                                          |
| -------- | --------------------------------------------------------- |
| nvm      | `rm -rf ~/.nvm`, clean PATH lines from `.zshrc`/`.bashrc` |
| bun      | `rm -rf ~/.bun`, clean PATH lines from `.zshrc`/`.bashrc` |
| rust     | `rustup self uninstall -y`                                |
| opencode | `rm -f $(which opencode)`, `rm -rf ~/.config/opencode`    |

All runtimes have a supported uninstall path. If a runtime is not found during uninstall (already removed), the step warns and continues.

### `fonts.py`

During install, record which `.ttf` files were copied. During uninstall, delete them from the font directory.

```python
def remove_font(font_name: str) -> None:
    """Remove all .ttf/.otf files matching font_name from the font directory."""
```

### `post_install.py`

- **TPM**: `rm -rf ~/.tmux/plugins/tpm`
- **Windows Terminal**: remove the symlink (not the original file — already backed up by Windows Terminal itself)

### `system_packages.py`

Not touched during uninstall. System packages (stow, tmux, git, etc.) are too risky to auto-remove.

## Steps

### Install steps

Same as today, plus manifest tracking:

1. System packages — no manifest changes
2. CLI tools — record preexisting, then record installed
3. Fonts — record installed font names and files
4. Stow symlinks — backup → stow → record in manifest
5. Runtimes — record preexisting, then record installed
6. Post-install — record what was done
7. Verification — unchanged, then save manifest

### Uninstall steps

Reverse order from install, except system packages:

1. Post-install — undo TPM / Windows Terminal
2. Runtimes — remove what was installed (skip preexisting)
3. Stow symlinks — `stow -D` + restore backups
4. Fonts — remove installed font files
5. CLI tools — remove from BIN_DIR (skip preexisting)
6. Save/clear manifest

## Edge cases

| Case                                   | Behaviour                                                    |
| -------------------------------------- | ------------------------------------------------------------ |
| No manifest found                      | Uninstall aborts: "No manifest found. Nothing to uninstall." |
| Backup file missing during restore     | Warn and skip, don't abort                                   |
| Re-install after partial uninstall     | Works: manifest still exists, stow re-checks targets         |
| User deleted a symlink manually        | `stow -D` may fail for that package; continue with others    |
| Runtime binary not found for uninstall | Warn and continue (already gone)                             |
| Force flag (-f)                        | Skips all confirmation prompts                               |
| Interactive uninstall                  | Confirms before each step (same pattern as install -i)       |
| WSL                                    | Same logic, no special handling needed                       |

## Files changed / added

| File                               | Change                                              |
| ---------------------------------- | --------------------------------------------------- |
| `install.sh`                       | New — thin shell wrapper                            |
| `uninstall.sh`                     | New — thin shell wrapper                            |
| `tools_management/1_uninstall.sh`  | New — bootstrap + exec                              |
| `tools_management/2_management.py` | Renamed from `2_install.py`, subcommand parser      |
| `tools_management/manifest.py`     | New — manifest CRUD                                 |
| `tools_management/stow.py`         | Modified — backup before stow, restore on uninstall |
| `tools_management/cli_tools.py`    | Modified — mode parameter                           |
| `tools_management/runtimes.py`     | Modified — mode parameter, uninstall logic          |
| `tools_management/fonts.py`        | Modified — mode parameter, uninstall logic          |
| `tools_management/gh_releases.py`  | Modified — add `remove_binary()`                    |
| `tools_management/post_install.py` | Modified — mode parameter, undo logic               |

## Non-goals

- No uninstall of system packages (brew/apt/pacman/dnf)
- No configuration backup beyond what stow touches (e.g., no `~/.ssh/` backup)
- No partial uninstall (e.g., `--just` equivalent for uninstall) — future work
- No automatic scheduling or periodic backups
