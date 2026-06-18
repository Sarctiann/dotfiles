# CLI Reference

## User-Facing Scripts

### `install.sh`

Entry point for installing dotfiles. Calls `1_setup.sh` (bootstrap) then `2_management.py install`.

```bash
./install.sh                        # Full install
./install.sh -i                     # Interactive (confirm each step)
./install.sh --just lazyvim         # Only steps needed by lazyvim + base steps
./install.sh --just lazyvim tmux    # Multiple packages + their deps
```

### `uninstall.sh`

Entry point for uninstalling dotfiles. Calls `1_uninstall.sh` then `2_management.py uninstall`.

```bash
./uninstall.sh                      # Full uninstall (with confirmation)
./uninstall.sh -f                   # Skip confirmation prompt
./uninstall.sh --just lazyvim       # Only unstow lazyvim + restore backups
```

## Pipeline Scripts

### `tools_management/1_setup.sh`

Bootstrap stage — ensures prerequisites before the Python pipeline runs.

| OS      | Actions |
|---------|---------|
| macOS   | Xcode CLT, Homebrew, `brew install python3 curl unzip stow` |
| Linux   | `apt/pacman/dnf install python3 curl unzip stow` |

**Note:** Called automatically by `install.sh`. Do not run directly.

### `tools_management/1_uninstall.sh`

Uninstall bootstrap — ensures python3 is available. Does not install/remove packages.

**Note:** Called automatically by `uninstall.sh`. Do not run directly.

### `tools_management/2_management.py`

The core pipeline orchestrator. Has two subcommands:

#### `install`

```bash
python3 tools_management/2_management.py install [options]
```

| Flag | Description |
|------|-------------|
| `-i`, `--interactive` | Ask before each pipeline step |
| `--just PKG [PKG ...]` | Only run steps needed by given stow packages + base steps (System packages, Fonts, Stow) |

**Config-driven behavior:**

- **Config change detection:** On re-install without `--just`, steps whose config hasn't changed since last install are skipped (compares hashes stored in manifest).
- **Step dependencies:** `config.json["step_deps"]` maps packages → required steps. Base steps always run.
- **Error handling:** Base steps abort on failure. Non-base steps print a warning and continue.

#### `uninstall`

```bash
python3 tools_management/2_management.py uninstall [options]
```

| Flag | Description |
|------|-------------|
| `-f`, `--force` | Skip confirmation prompt |
| `-i`, `--interactive` | Ask before each pipeline step |
| `--just PKG [PKG ...]` | Only unstow given packages + restore their backups. Skips all non-stow steps. |

## Pipeline Steps

Steps run in this order during `install`:

| # | Step | Module | Config key | Base |
|---|------|--------|-----------|------|
| 1 | System packages | `system_packages.py` | `system_packages` | ✓ |
| 2 | CLI tools | `cli_tools.py` / `gh_releases.py` | `cli_tools` | |
| 3 | Fonts | `fonts.py` | `fonts` | ✓ |
| 4 | Stow symlinks | `stow.py` | `stow` | ✓ |
| 5 | Runtimes | `runtimes.py` | `runtimes` | |
| 6 | NPM packages | `npm_packages.py` | `npm_packages` | |
| 7 | Post-install | `post_install.py` | `post_install` | |
| 8 | Verification | `verify.py` | `verify` | |

Uninstall runs in reverse order (8 → 1), except Verfication which runs last.

## Manifest

Written to:
- `~/.local/share/dotfiles/manifest.json` (primary — persists across machines)
- `<repo-root>/dotfiles-manifest.json` (convenience copy in repo)

Tracks installed CLI tools, runtimes, fonts, stow packages with backups, and a config snapshot (SHA-256 hashes per step).

## Config

`config.json` at repo root. All pipeline behavior is driven from this file:

| Section | Purpose |
|---------|---------|
| `system_packages` | OS package manager packages (brew/apt/pacman/dnf) |
| `conditional_system_packages` | Packages only installed when certain stow packages are in the plan |
| `base_steps` | Step labels that always run (cannot be skipped) |
| `cli_tools` | Tools downloaded from GitHub releases |
| `fonts` | Nerd Font variants to install |
| `runtimes` | Language runtimes / version managers to install |
| `npm_packages` | Global npm packages |
| `stow` | Stow config (terminal choice, package deps) |
| `post_install` | Post-install hooks (TPM, zsh plugins, Windows Terminal) |
| `verify` | Commands to check after install (essential/optional) |
| `step_deps` | Maps stow packages → required pipeline steps |
