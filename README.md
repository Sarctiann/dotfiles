# dotfiles

Configuration files managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Quick start

```bash
git clone <repo-url> ~/dotfiles
cd ~/dotfiles
./install.sh
```

- Edit `config.json` to toggle steps or change terminal
- Use `./install.sh -i` to confirm each step interactively
- Use `./install.sh --just nvim` for a minimal install (only what nvim needs)

## Usage

### Install

```bash
./install.sh [options]
```

| Argument               | Description                                                                         |
| ---------------------- | ----------------------------------------------------------------------------------- |
| `-i`, `--interactive`  | Confirm each step before running                                                    |
| `--check`              | Validate config and show plan without making changes                                |
| `--just PKG [PKG ...]` | Only stow specified packages + dependencies + base. Skips unrelated pipeline steps. |

Examples:

```bash
# Full install (default)
./install.sh

# Confirm each step
./install.sh -i

# Minimal: only stow nvim + its deps (opencode, fonts, runtimes)
./install.sh --just nvim

# Single terminal package
./install.sh --just ghostty

# Dry-run check (validate config, no changes)
./install.sh --check
```

### Uninstall

```bash
./uninstall.sh [options]
```

| Argument              | Description                      |
| --------------------- | -------------------------------- |
| `-f`, `--force`       | Skip confirmation prompt         |
| `-i`, `--interactive` | Confirm each step before running |
| `--just PKG [PKG ...]`| Only unstow specified packages + restore their backups |

Example:

```bash
./uninstall.sh -f
```

## Prerequisites

**macOS**: Xcode Command Line Tools (installed automatically if missing).

**Linux**: `git` (to clone) + either `curl` or `wget`. Everything else is bootstrapped.

**WSL2**:

1. Install WSL2 + Ubuntu 24.04 from Microsoft Store
2. Open Ubuntu terminal — `git` is all you need prepackaged

> **GitHub API rate limit**: The installer hits the GitHub API ~15 times for release assets.
> Set `GITHUB_PERSONAL_ACCESS_TOKEN` in your environment to raise the limit from 60/h to 5000/h:
>
> ```bash
> export GITHUB_PERSONAL_ACCESS_TOKEN=$(gh auth token)   # if gh is authenticated
> ```
>
> Falls back to `GITHUB_TOKEN` or `GH_TOKEN` for compatibility.

## Stack

```
┌─────────────────────────────────────────┐
│  Terminal: Ghostty (macOS/Linux)        │
│            Windows Terminal (WSL)       │
├─────────────────────────────────────────┤
│  Multiplexer: tmux + TPM                │
├─────────────────────────────────────────┤
│  Shell: zsh + custom plugins            │
├─────────────────────────────────────────┤
│  Editor: Neovim + LazyVim               │
│  (LSPs, formatters via Mason)           │
├─────────────────────────────────────────┤
│  Tools: ripgrep, fd, bat, fzf,          │
│  lazygit, lazydocker, lazysql,          │
│  yazi, gh, zig, uv, bun, rust, nvm,     │
│  auggie, gemini-cli                     │
├─────────────────────────────────────────┤
│  AI: OpenCode + custom agents,          │
│  Auggie, Gemini CLI,                    │
│  Neovim MCP integration                 │
└─────────────────────────────────────────┘
```

## Terminal strategy

| OS          | Terminal             | Stow package                                                 |
| ----------- | -------------------- | ------------------------------------------------------------ |
| macOS       | Ghostty              | `ghostty/`                                                   |
| Linux       | Ghostty              | `ghostty/`                                                   |
| macOS/Linux | Alacritty or Wezterm | configure via `config.json` `stow.terminal` |
| WSL         | Windows Terminal     | `windows-terminal/` (symlinked via post_install)             |

Shell (zsh), editor (nvim), multiplexer (tmux), fonts (CodeNewRoman + NerdFontsSymbolsOnly), and Git are shared across all three.

## Structure

```
dotfiles/
├── install.sh              ← entry point (delegates to tools_management/1_setup.sh)
├── uninstall.sh            ← entry point (delegates to tools_management/1_uninstall.sh)
├── stow-packages/          ← stow packages (one per program)
│   ├── nvim/               ← LazyVim config + plugins + opencode-neovim integration
│   ├── zsh/                ← .zshrc, aliases, env
│   ├── tmux/               ← .tmux.conf + TPM
│   ├── ghostty/            ← Ghostty config + GLSL shaders
│   ├── alacritty/          ← Alacritty config
│   ├── wezterm/            ← Wezterm config
│   ├── windows-terminal/   ← Windows Terminal settings.json (WSL)
│   ├── opencode/           ← OpenCode config (agents, skills, themes, quota, notifier)
│   ├── bat/                ← bat theme (.config/bat/config)
│   ├── local-bin/          ← local scripts
│   ├── mojo/               ← Mojo + Pixi config
│   └── ...
├── testing/                ← container-based test suite
│   ├── test_pipeline.py   ← CLI orchestrator (linux/wsl/mac)
│   ├── test_containers/    ← Dockerfiles + pipeline script
│   └── TESTING.md          ← testing documentation
├── tools_management/       ← two-stage bootstrap + uninstall
│   ├── 1_setup.sh          ← Stage 1: bash bootstrap (python3 + base pkgs)
│   ├── 1_uninstall.sh      ← Stage 1: bash bootstrap (python3)
│   ├── 2_management.py     ← Stage 2: Python orchestrator (install/uninstall)
│   ├── config.json         ← declarative config (what to install)
│   ├── config.py           ← config loader
│   ├── core.py             ← OS/arch/WSL detection + utilities
│   ├── system_packages.py  ← Homebrew/apt/pacman/dnf
│   ├── gh_releases.py      ← GitHub release binary installer
│   ├── fonts.py            ← Nerd Font installer
│   ├── stow.py             ← symlink management
│   ├── manifest.py         ← tracks installed vs pre-existing for safe uninstall
│   ├── cli_tools.py        ← CLI tools aggregator
│   ├── npm_packages.py     ← npm global packages (auggie, gemini-cli)
│   ├── runtimes.py         ← nvm/bun/rust/opencode/uv
│   ├── post_install.py     ← TPM, Windows Terminal
│   └── verify.py           ← post-install verification
└── README.md
```

## How it works

The install runs in two stages:

**Stage 1** (`tools_management/1_setup.sh`) — minimal bash bootstrap:

1. **macOS**: Xcode Command Line Tools → Homebrew → `brew install python@3 curl unzip stow`
2. **Linux/WSL**: ensures `python3 curl unzip stow` via apt/pacman/dnf

Stage 1 handles the absolute minimum to get Python running. `stow`, `curl`, and `unzip` are installed here and not duplicated in Stage 2.
3. Hands off to Stage 2

**Stage 2** (`tools_management/2_management.py`) — Python orchestrator:

1.  **System packages** — brew/apt/pacman packages (tmux, git)
2.  **CLI tools** — neovim, ripgrep, fd, bat, lazygit, lazydocker, lazysql, gh, fzf, yazi, zig
3.  **Fonts** — installs CodeNewRoman and NerdFontsSymbolsOnly Nerd Fonts
4.  **Stow** — creates symlinks for all stow packages
5.  **Runtimes** — nvm + Node LTS, Bun, Rust (rustup), OpenCode, uv
6.  **NPM packages** — auggie, gemini-cli (via bun, fallback npm)
7.  **Post-install** — TPM, Windows Terminal symlink (WSL)
8.  **Verify** — checks essential commands are in PATH

All steps can be toggled on/off via `config.json`. Run with `-i` for interactive mode (confirms each step before proceeding). Use `--just PKG` to run only the steps needed by one or more stow packages (skips unrelated phases).

## Stow Packages

The core of this project. Each folder under `stow-packages/` mirrors part of `$HOME`:

```
stow-packages/nvim/.config/nvim/init.lua  →  $HOME/.config/nvim/init.lua
stow-packages/zsh/.zshrc                  →  $HOME/.zshrc
```

When `stow` runs, it creates symlinks from `$HOME` into the repo. Removing the symlink later is safe — the repo is the source of truth.

### Dependency resolution

Packages can declare dependencies in `config.json → stow.deps`. When you use `--just PKG`, the system computes a transitive closure:

```
--just ghostty → ghostty + tmux + zsh + nvim + opencode + mojo + local-bin
```

The resolver handles circular deps (nvim ↔ opencode) gracefully.

### Terminal selection

Only one terminal package is active at a time, set via `config.json → stow.terminal`:

| Value               | Alternative                                   |
| ------------------- | --------------------------------------------- |
| `ghostty` (default) | Stows ghostty/, skips alacritty/ and wezterm/ |
| `alacritty`         | Stows alacritty/, skips the others            |
| `wezterm`           | Stows wezterm/, skips the others              |

On WSL, all three are skipped — Windows Terminal is handled separately by `post_install.py`.

### Base packages

`stow.base` (default: `["local-bin"]`) always gets stowed regardless of `--just`.

### Base steps (always run)

Regardless of `--just`, these steps always execute:

- **System packages** — tmux, git
- **Fonts** — Nerd Fonts (CodeNewRoman, NerdFontsSymbolsOnly)
- **Stow** — symlink creation

### Conditional steps (skipped if not needed)

| Pipeline step | Needed by              |
| ------------- | ---------------------- |
| CLI tools     | nvim, bat              |
| NPM packages  | nvim, zsh              |
| Runtimes      | nvim, opencode, zsh    |
| Post-install  | tmux, windows-terminal |

### Backup and restore

Before stow overwrites an existing file, `stow.py` copies it to `~/.local/share/dotfiles/backups/`. On uninstall, backups are restored and symlinks removed.

### Stowignore

`.stowignore` contains glob patterns for files stow should never touch:

```
**/.gitkeep
.DS_Store
**/.playwright-mcp
```

## Adding a new stow package

1. Create a directory: `stow-packages/my-app/.config/my-app/config`
2. Add files with paths relative to `$HOME`
3. If it needs other packages, add deps to `config.json → stow.deps`:

   ```json
   "my-app": ["nvim"]
   ```

4. If it needs specific pipeline steps (CLI tools, runtimes, etc.), update `should_skip_step()` in `2_management.py`
5. Run `./install.sh` — the new package is auto-discovered

## Manual stow commands

```bash
# Stow a single package (create symlinks)
stow -R -t $HOME nvim

# Remove symlinks for a package
stow -D -t $HOME nvim
```

## Uninstall

```bash
./uninstall.sh              # removes symlinks, restores backups, removes tools
./uninstall.sh -f           # skip confirmation prompt
./uninstall.sh -i           # confirm before each step
```

What gets removed:

- **Stow symlinks** — deleted, original files restored from backup
- **CLI tools** — only those installed by the script (not pre-existing ones)
- **NPM packages** — auggie, gemini-cli (only if not pre-existing)
- **Runtimes** — nvm, Bun, Rust, OpenCode, uv (only if not pre-existing)
- **Fonts** — CodeNewRoman and NerdFontsSymbolsOnly font files
- **Post-install** — TPM, Windows Terminal symlink (WSL)

System packages (stow, tmux, git via brew/apt) are **not** removed.

## Testing

The install/uninstall pipeline is tested inside Docker containers for Linux and WSL,
plus a read-only check for macOS.

```bash
# Test all platforms (parallel Docker + local mac)
./testing/test_pipeline.py

# Test a single platform
./testing/test_pipeline.py linux
./testing/test_pipeline.py wsl
./testing/test_pipeline.py mac

# Dry-run check directly (no containers needed)
./install.sh --check
```

See [`testing/TESTING.md`](testing/TESTING.md) for details.

## Neovim (LazyVim)

- Distribution: [LazyVim](https://www.lazyvim.org/)
- Completion: blink.cmp with emoji support
- Picker: snacks.nvim (dashboard, files, grep)
- AI integration: OpenCode CLI + custom Neovim utils (server management, tunnel, session browser)
- Plugin extras: copilot, formatting (black, prettier), language support (Python, Rust, TypeScript, Zig, Docker, SQL, TOML, YAML, Markdown, Tailwind, Ruby, Mojo, V)
- Custom plugins: cli-integration.nvim, cursor-agent.nvim, blamer.nvim

## Tmux

- `tmux-help` — show keymaps in shell (runs `bat` on help file)
- `prefix + H` — show keymaps in a new tmux window
- Keymaps auto-display on new session creation

### Bindings

| Keys              | Action                      |
| ----------------- | --------------------------- |
| `Ctrl+Alt+w`      | Create window               |
| `Alt+w`           | Kill window / session       |
| `Alt+,` / `Alt+.` | Previous / next window      |
| `Alt+1..9`        | Select window 1-9           |
| `Ctrl+Alt+s`      | Create session              |
| `Alt+s`           | Kill current session        |
| `Ctrl+Alt+r`      | Rename session              |
| `Alt+Shift+←/→`   | Previous / next session     |
| `Ctrl+b Ctrl+s`   | Save session (resurrect)    |
| `Ctrl+b Ctrl+r`   | Restore session (resurrect) |

## OpenCode

- Config sourced from [Sarctiann/opencode-config](https://github.com/Sarctiann/opencode-config)
- Custom agents: x-teach, z-forge, z-logic, z-nexus, z-pilot, z-spark, z-ultra, x--free
- MCP servers: Playwright, Augment Context Engine, Neovim
- Plugins: opencode-quota (toast + TUI), opencode-notifier, superpowers
- Skills: agent-model-audit, agent-sync-neovim
- Theme: custom tokyonight

## Supported OS

- macOS (Homebrew)
- Linux (apt, pacman, dnf)
- WSL2 (apt)
