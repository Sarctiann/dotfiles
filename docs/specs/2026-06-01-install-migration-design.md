# Install Scripts: Bash → Python Migration

Date: 2026-06-01

## Motivation

Migrate the dotfiles install scripts from bash to Python 3 for better maintainability, testability, and extensibility. A minimal bash bootstrap remains necessary because Python 3 is not guaranteed on macOS.

## Architecture

```
install/
  1_setup.sh             bash bootstrap (Layer -1)
  2_install.py           Python entry point / orchestrator (Layer 2)
  config.json            declarative config (what to install)
  config.py              config loader
  core.py                OS/arch/WSL detection
  system_packages.py     package manager abstraction (brew, apt, pacman, dnf)
  gh_releases.py         GitHub release download, extract, install
  fonts.py               Nerd Fonts download and install
  stow.py                GNU Stow symlink management
  cli_tools.py           aggregator: neovim, rg, fd, bat, lazy* (uses gh_releases)
  runtimes.py            nvm, bun, rust, opencode installers
  post_install.py        TPM, Windows Terminal link
  verify.py              post-install verification
```

### Layer Architecture

```
┌──────────────────────────────────────────────┐
│  Layer 2: Orchestrator                        │
│  2_install.py  (lee config, orquesta)         │
├──────────────────────────────────────────────┤
│  Layer 1: Aggregators                        │
│  cli_tools.py   runtimes.py                  │
│  post_install.py  verify.py                  │
├──────────────────────────────────────────────┤
│  Layer 0: Primitives                         │
│  system_packages.py  gh_releases.py          │
│  fonts.py  stow.py                           │
├──────────────────────────────────────────────┤
│  Shared (imported by all layers)             │
│  core.py  config.py  config.json             │
└──────────────────────────────────────────────┘
```

- **Layer 0** — primitives with no knowledge of config.json; they take parameters
- **Layer 1** — aggregators that read config and call primitives
- **Layer 2** — reads config.json, calls Layer 1 in order, reports results
- **Shared** — `core.py` has zero dependencies; `config.py` depends only on `json`

### Layer -1: `1_setup.sh`

What it does:

1. Detect OS and architecture (thin, bash-native)
2. If macOS: Xcode Command Line Tools → Homebrew → `brew install python@3 curl unzip stow`
3. If Linux/WSL: ensure `python3 curl unzip stow` via apt/pacman/dnf
4. `exec python3 "$(dirname "$0")/2_install.py" "$@"`

Kept in bash because this must work without Python 3.

All CLI arguments (e.g. `-i`) are forwarded to `2_install.py` via `"$@"`.

### Layer 0: Primitives

**`core.py`** — `detect_os()`, `detect_arch()`, `is_wsl()`, `gh_arch()`, `run()`, `download()`, `confirm()`

- `INTERACTIVE` global flag toggled by `-i` CLI flag
- `confirm(prompt, default)` reads stdin, respects `INTERACTIVE` (returns True if not interactive)

**`system_packages.py`** — one function per package manager, auto-detected:

- `install_brew(packages: list[str])` → macOS
- `install_apt(packages: list[str])` → Debian/Ubuntu
- `install_pacman(packages: list[str])` → Arch
- `install_dnf(packages: list[str])` → Fedora

**`gh_releases.py`** — download latest release from GitHub:

- `latest_asset_url(repo, pattern)` → str
- `install_binary(repo, binary_name, asset_pattern)` → bool
- Handles tar.gz, tar.xz, zip extraction

**`fonts.py`** — download and install Nerd Fonts:

- `install_nerd_font(font_name, target_dir)` → None
- Windows font detection for WSL (skips)

**`stow.py`** — symlink management:

- `stow_packages(stow_dir, terminal, is_wsl)` → None
- `stow_windows_terminal(stow_dir)` → None

### Layer 1: Aggregators

**`cli_tools.py`** — reads `config.json["cli_tools"]`, iterates tools: if enabled, calls `gh_releases.install_binary()`. Each tool has a registry entry with repo name, binary name, and OS/arch-aware asset pattern.

**`runtimes.py`** — nvm (git clone + install script), bun (curl), rust (rustup), opencode (curl). Each reads its enabled flag from config.

**`post_install.py`** — TPM git clone, Windows Terminal symlink, etc.

**`verify.py`** — checks essential and optional commands, reads list from config.

### Layer 2: `2_install.py`

```
def main():
    args = parse_args()           # supports -i/--interactive
    if args.interactive:
        core.INTERACTIVE = True

    config = load_config()

    if core.INTERACTIVE:
        print_summary(config)     # show plan before executing

    for label, fn in STEPS:
        if core.INTERACTIVE and not confirm(f"▶ {label}?"):
            continue
        banner(label)
        fn(config)

    print_summary_footer()        # done, tips, stow/terminal info
```

`STEPS` is a list of `(name, function)` tuples iterated in order. Interactive mode
asks before each step; non-interactive mode runs all steps without prompting.

## Config (`config.json`)

```json
{
  "system_packages": [
    "stow",
    "tmux",
    "git",
    "curl",
    "unzip",
    "pipx",
    "luarocks"
  ],
  "cli_tools": {
    "neovim": { "repo": "neovim/neovim", "binary": "nvim" },
    "ripgrep": { "repo": "BurntSushi/ripgrep", "binary": "rg" },
    "fd": { "repo": "sharkdp/fd", "binary": "fd" },
    "bat": { "repo": "sharkdp/bat", "binary": "bat" },
    "lazygit": { "repo": "jesseduffield/lazygit", "binary": "lazygit" },
    "lazydocker": {
      "repo": "jesseduffield/lazydocker",
      "binary": "lazydocker"
    },
    "lazysql": { "repo": "jorgerojas26/lazysql", "binary": "lazysql" },
    "gh": { "repo": "cli/cli", "binary": "gh" },
    "fzf": { "repo": "junegunn/fzf", "binary": "fzf" },
    "yazi": { "repo": "sxyazi/yazi", "binary": "yazi" },
    "zig": { "repo": "ziglang/zig", "binary": "zig" }
  },
  "fonts": ["CodeNewRoman", "NerdFontsSymbolsOnly"],
  "runtimes": {
    "nvm": true,
    "bun": true,
    "rust": true,
    "opencode": true
  },
  "stow": {
    "enabled": true,
    "terminal": "ghostty"
  },
  "post_install": {
    "tpm": true,
    "windows_terminal": true
  },
  "verify": {
    "essential": ["stow", "nvim", "tmux", "rg", "fd", "bat", "gh", "git"],
    "optional": [
      "lazygit",
      "lazydocker",
      "lazysql",
      "yazi",
      "zig",
      "nvm",
      "bun",
      "cargo",
      "opencode"
    ]
  }
}
```

All values default to "enabled" — the user can selectively disable by removing entries or setting them to false.

## Interactive mode

- `-i` / `--interactive` flag causes each step to prompt before executing
- Implemented via `confirm()` in `core.py`, which checks global `INTERACTIVE` flag
- In interactive mode, a summary of what will be installed is shown first

## Adding a New CLI Tool

1. Add entry to `config.json["cli_tools"]`
2. If the asset URL pattern is standard (v0.0.0 format), `gh_releases.py` auto-generates it
3. If non-standard, add a custom pattern method

## Error Handling

- Each Step catches exceptions, logs, and continues (non-fatal)
- Critical failures (no stow, no python3) abort immediately
- Errors are collected and printed in a summary at the end

## What Changes

- `install.sh` → removed (functionality split into `1_setup.sh` + `2_install.py`)
- `install/packages.sh` → removed (replaced by Python modules)
- `install/fonts.sh` → removed (replaced by `fonts.py`)
- New files: all the Python modules + `config.json`
