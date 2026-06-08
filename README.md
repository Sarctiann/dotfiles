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

| Argument               | Description                                            |
| ---------------------- | ------------------------------------------------------ |
| `-f`, `--force`        | Skip confirmation prompt                               |
| `-i`, `--interactive`  | Confirm each step before running                       |
| `--just PKG [PKG ...]` | Only unstow specified packages + restore their backups |

Example:

```bash
./uninstall.sh -f
```

## Prerequisites

<details>
<summary><b>macOS</b></summary>

| Component                   | Notes                                              |
| --------------------------- | -------------------------------------------------- |
| macOS 14+ (Sonoma)          | Recommended, but 13+ should work                   |
| Xcode Command Line Tools    | Installed automatically if missing by `install.sh` |
| [Homebrew](https://brew.sh) | Installed automatically if missing by `install.sh` |

The script (`1_setup.sh`) handles everything: Xcode CLT → Homebrew → `python@3 curl unzip stow`.

No manual steps needed — just clone and run.

</details>

<details>
<summary><b>Linux (apt / pacman / dnf)</b></summary>

| Component        | Notes                                              |
| ---------------- | -------------------------------------------------- |
| `git`            | To clone the repo (usually pre-installed)          |
| `curl` or `wget` | For downloading release assets                     |
| `sudo`           | Required for `apt`/`pacman`/`dnf` during bootstrap |

Everything else (`python3 curl unzip stow`) is installed automatically by `install.sh` via your distro's package manager.

> Distros tested: Ubuntu 24.04 (apt), Arch (pacman), Fedora (dnf). Others may work but are untested.

</details>

<details>
<summary><b>Windows (WSL2)</b></summary>

Since `install.sh` is a bash script, it needs a Linux environment. The supported path is **WSL2 + Ubuntu 24.04 + Windows Terminal**.

### Automated setup

Copy-paste the entire block below into **PowerShell as Administrator**. It handles all Windows prerequisites and prints the final commands to clone and install inside WSL.

```powershell
#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host "=== Setting up WSL2 + Windows Terminal for dotfiles ===" -ForegroundColor Cyan
Write-Host "(Safe to re-run — completed steps are skipped)" -ForegroundColor Gray
Write-Host ""

# --- 1. Enable WSL + VM features ---
Write-Host "[1/4] Enabling Windows Subsystem for Linux..." -ForegroundColor Yellow
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# --- 2. Check if restart is needed (dism returns 3010) ---
Write-Host "[2/4] Checking if restart is required..." -ForegroundColor Yellow
if ($LASTEXITCODE -eq 3010 -or (Test-Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\PendingFileRenameOperations")) {
    Write-Host "  -> Restart required. Reboot now, then re-run this script." -ForegroundColor Red
    Write-Host "     Already completed steps will be skipped automatically." -ForegroundColor Yellow
    pause
    exit
}

# --- 3. Install Ubuntu 24.04 ---
$ubuntuInstalled = wsl -l -v 2>$null | Select-String -Pattern "Ubuntu-24.04" -Quiet
if (-not $ubuntuInstalled) {
    Write-Host "[3/4] Setting WSL2 as default and installing Ubuntu 24.04..." -ForegroundColor Yellow
    wsl --set-default-version 2
    wsl --install -d Ubuntu-24.04

    Write-Host ""
    Write-Host "=== Ubuntu was installed. It will launch automatically to finish setup. ===" -ForegroundColor Cyan
    Write-Host "Create your Linux user/password when prompted, then close the Ubuntu window." -ForegroundColor Yellow
    pause
}
else {
    Write-Host "[3/4] Ubuntu 24.04 already installed — skipping." -ForegroundColor Green
}

# --- 4. Install Windows Terminal ---
if (-not (Get-Command wt.exe -ErrorAction SilentlyContinue)) {
    Write-Host "[4/4] Installing Windows Terminal..." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Microsoft.WindowsTerminal --accept-source-agreements
    } else {
        Write-Host "  -> winget not found. Install from: https://apps.microsoft.com/detail/9n0dx20hk701" -ForegroundColor Yellow
    }
}
else {
    Write-Host "[4/4] Windows Terminal already installed — skipping." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== All done! ===" -ForegroundColor Green
Write-Host ""
Write-Host "Now open Windows Terminal, select 'Ubuntu-24.04' from the tab dropdown, and run:" -ForegroundColor Cyan
Write-Host ""
Write-Host '  git clone <url-del-repo> ~/dotfiles' -ForegroundColor White
Write-Host '  cd ~/dotfiles' -ForegroundColor White
Write-Host '  ./install.sh' -ForegroundColor White
Write-Host ""
```

> If you prefer to do it manually instead, each step is detailed below.

### Manual steps

#### 1. Enable WSL2

```powershell
# Enable WSL feature (if `wsl` command is not found)
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
# Restart, then:
wsl --set-default-version 2
wsl --install -d Ubuntu-24.04
```

#### 2. Install Windows Terminal

```powershell
winget install --id Microsoft.WindowsTerminal --accept-source-agreements
```

#### 3. Clone and install (inside WSL)

```bash
wsl -d Ubuntu-24.04
git clone <repo-url> ~/dotfiles
cd ~/dotfiles
./install.sh
```

The installer detects WSL, uses `apt` for bootstrap packages, and sets up Windows Terminal config via `post_install.py`.

</details>

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
│  Augment (auggie) user-level +          │
│    work-profile (neovim-deployed),      │
│  Gemini CLI (stow-managed),             │
│  Neovim MCP integration across all      │
│  three clients                          │
└─────────────────────────────────────────┘
```

## Terminal strategy

| OS          | Terminal             | Stow package                                     |
| ----------- | -------------------- | ------------------------------------------------ |
| macOS       | Ghostty              | `ghostty/`                                       |
| Linux       | Ghostty              | `ghostty/`                                       |
| macOS/Linux | Alacritty or Wezterm | configure via `config.json` `stow.terminal`      |
| WSL         | Windows Terminal     | `windows-terminal/` (symlinked via post_install) |

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
│   ├── augment/            ← Augment user-level config (AGENTS.md, skills)
│   ├── gemini/             ← Gemini CLI config (policies, custom-skills)
│   ├── bat/                ← bat theme (.config/bat/config)
│   ├── local-bin/          ← local scripts (includes sync_git_config.py)
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

Stage 1 handles the absolute minimum to get Python running. `stow`, `curl`, and `unzip` are installed here and not duplicated in Stage 2. 3. Hands off to Stage 2

**Stage 2** (`tools_management/2_management.py`) — Python orchestrator:

1.  **System packages** — brew/apt/pacman packages (tmux, git)
2.  **CLI tools** — neovim, ripgrep, fd, bat, lazygit, lazydocker, lazysql, gh, fzf, yazi, zig
3.  **Fonts** — installs CodeNewRoman and NerdFontsSymbolsOnly Nerd Fonts
4.  **Stow** — creates symlinks for all stow packages
5.  **Git config** — prompts for identity vars, generates `~/.gitconfig` via `sync_git_config.py`
6.  **Runtimes** — nvm + Node LTS, Bun, Rust (rustup), OpenCode, uv
7.  **NPM packages** — auggie, gemini-cli (via bun, fallback npm)
8.  **Post-install** — TPM, Windows Terminal symlink (WSL)
9.  **Verify** — checks essential commands are in PATH

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

## Git

`~/.gitconfig` is **generated** from environment variables by
[`sync_git_config.py`](stow-packages/local-bin/.local/bin/sync_git_config.py),
which is called automatically during `install.sh` (the "Git config" step).

Define these in `~/.config/zsh/.credentials` (see [Credentials docs](stow-packages/zsh/.config/zsh/README.md)):

| Variable            | Purpose                                |
| ------------------- | -------------------------------------- |
| `GIT_NAME`          | Personal `[user] name`                 |
| `GIT_EMAIL`         | Personal `[user] email`                |
| `COMPANY_GIT_NAME`  | Work identity (for `includeIf`)        |
| `COMPANY_GIT_EMAIL` | Work email (for `includeIf`)           |
| `COMPANY_DIR`       | Path under which work identity applies |

To regenerate manually:

```bash
source ~/.config/zsh/.credentials
sync_git_config.py
```

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

## OpenCode / AI Clients

### OpenCode

- Config sourced from [Sarctiann/opencode-config](https://github.com/Sarctiann/opencode-config)
- Custom agents: x-teach, z-forge, z-logic, z-nexus, z-pilot, z-spark, z-ultra, x--free
- MCP servers: Playwright, Augment Context Engine, Neovim
- Plugins: opencode-quota (toast + TUI), opencode-notifier, superpowers
- Skills: agent-model-audit, agent-sync-neovim
- Theme: custom tokyonight

### Augment (auggie)

- **User-level** (`~/.augment/`): `AGENTS.md` + skills stow-managed via `stow-packages/augment/`
- **Work-profile** (`<project>/.augment_work_profile/`): `AGENTS.md` + skills deployed by Neovim
  from `nvim/lua/utils/augment-work-profile/` on every `on_open_auggie` hook

### Gemini CLI

- **Policy** (`~/.gemini/policies/default.md`): stow-managed, loaded via `gemini --policy ...`
- **Skills** (`~/.gemini/custom-skills/`): stow-managed via `stow-packages/gemini/`, linked
  to `~/.gemini/skills/` via `gemini skills link`

### Multi-Client Skill Synchronization

The three Neovim MCP skills (`using-neovim`, `using-neovim-lsp`, `using-quickfix`) in
`nvim/lua/utils/opencode-neovim/skills/` are **shared across all AI clients**:

| Client         | Location                                     | Method                                |
| -------------- | -------------------------------------------- | ------------------------------------- |
| OpenCode       | `.../opencode-neovim/skills/<name>/SKILL.md` | Native (source of truth)              |
| Augment (user) | `~/.augment/skills/<name>.md`                | Stow symlink                          |
| Augment (work) | `<work-profile>/skills/<name>.md`            | Neovim-deployed symlink               |
| Gemini         | `~/.gemini/custom-skills/<name>/SKILL.md`    | Stow symlink (+ `gemini skills link`) |

**Changes to any skill MUST be replicated to all four destinations** (opencode source,
augment user-level, augment work-profile, gemini). The content is identical except for
client-specific details (prerequisites section, connection instructions).

## Supported OS

- macOS (Homebrew)
- Linux (apt, pacman, dnf)
- WSL2 (apt)
