# dotfiles

Configuration files managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Quick start

```bash
git clone <repo-url> ~/dotfiles
cd ~/dotfiles
./install.sh [-i]
```

- `-i` — interactive mode: confirms each step before running
- Edit `tools_management/config.json` to toggle steps or change terminal

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
│  yazi, gh, zig, bun, rust, nvm          │
├─────────────────────────────────────────┤
│  AI: OpenCode + custom agents,          │
│  Gemini CLI, Neovim MCP integration     │
└─────────────────────────────────────────┘
```

## Terminal strategy

| OS          | Terminal             | Stow package                                                 |
| ----------- | -------------------- | ------------------------------------------------------------ |
| macOS       | Ghostty              | `ghostty/`                                                   |
| Linux       | Ghostty              | `ghostty/`                                                   |
| macOS/Linux | Alacritty or Wezterm | configure via `tools_management/config.json` `stow.terminal` |
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
│   ├── runtimes.py         ← nvm/bun/rust/opencode
│   ├── post_install.py     ← TPM, Windows Terminal
│   └── verify.py           ← post-install verification
└── README.md
```

## How it works

The install runs in two stages:

**Stage 1** (`tools_management/1_setup.sh`) — minimal bash bootstrap:

1. **macOS**: Xcode Command Line Tools → Homebrew → `brew install python@3 curl unzip stow`
2. **Linux/WSL**: ensures `python3 curl unzip stow` via apt/pacman/dnf
3. Hands off to Stage 2

**Stage 2** (`tools_management/2_management.py`) — Python orchestrator:

1. **System packages** — brew/apt/pacman packages (tmux, git, pipx, luarocks)
2. **CLI tools** — neovim, ripgrep, fd, bat, lazygit, lazydocker, lazysql, gh, fzf, yazi, zig
3. **Fonts** — installs CodeNewRoman and NerdFontsSymbolsOnly Nerd Fonts
4. **Stow** — creates symlinks for all stow packages
5. **Runtimes** — nvm + Node LTS, Bun, Rust (rustup), OpenCode
6. **Post-install** — TPM, Windows Terminal symlink (WSL)
7. **Verify** — checks essential commands are in PATH

All steps can be toggled on/off via `tools_management/config.json`. Run with `-i` for interactive mode (confirms each step before proceeding).

## Uninstall

```bash
./uninstall.sh              # removes symlinks, restores backups, removes tools
./uninstall.sh -f           # skip confirmation prompt
./uninstall.sh -i           # confirm before each step
```

What gets removed:

- **Stow symlinks** — deleted, original files restored from backup
- **CLI tools** — only those installed by the script (not pre-existing ones)
- **Runtimes** — nvm, Bun, Rust, OpenCode (only if not pre-existing)
- **Fonts** — CodeNewRoman and NerdFontsSymbolsOnly font files
- **Post-install** — TPM, Windows Terminal symlink (WSL)

System packages (stow, tmux, git via brew/apt) are **not** removed.

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
