# `--just` flag + package dependency resolution

## Problem

`./install.sh` stows **every** package in `stow-packages/` with no way to select specific ones. Adding `--just <pkg> [<pkg> ...]` lets the user stow only what they need, with automatic dependency resolution.

## Design

### 1. `config.json` — dependency metadata

Extend the `"stow"` section:

```json
{
  "stow": {
    "enabled": true,
    "terminal": "ghostty",
    "base": ["local-bin"],
    "deps": {
      "zsh": ["lazyvim", "opencode", "mojo"],
      "tmux": ["zsh"],
      "ghostty": ["tmux", "zsh"],
      "alacritty": ["tmux", "zsh"],
      "wezterm": ["tmux", "zsh"],
      "windows-terminal": ["tmux", "zsh"],
      "lazyvim": ["opencode"],
      "opencode": ["lazyvim"],
      "bat": [],
      "mojo": [],
      "local-bin": []
    }
  }
}
```

- **`base`**: stowed always (e.g., `local-bin`).
- **`deps`**: adjacency list. A → [B, C] means "A depends on B and C".
- **Resolution**: transitive closure over `deps` union `base`.

### 2. `stow.py` — resolve + plan-aware stow

New function `resolve_stow_plan()` — takes `--just` values, computes transitive closure. `stow_packages()` is modified to read `core.STOW_PLAN`:

```python
# New
def resolve_stow_plan(config, requested):
    deps = config["stow"]["deps"]
    base = set(config["stow"]["base"])
    plan = set(requested)
    changed = True
    while changed:
        changed = False
        for pkg in list(plan):
            for dep in deps.get(pkg, []):
                if dep not in plan:
                    plan.add(dep)
                    changed = True
    return plan | base


# Modified — reads core.STOW_PLAN instead of iterating all dirs
def stow_packages(config):
    if not config.get("stow", {}).get("enabled", True):
        return

    if not which("stow"):
        print("❌ stow is not installed. Cannot create symlinks.")
        return

    plan = core.STOW_PLAN  # set[str] or None
    terminal = config.get("stow", {}).get("terminal", "ghostty")
    wsl = is_wsl()

    if plan is None:
        # Full install: iterate all directories (existing behavior)
        candidates = sorted(p.name for p in STOW_DIR.iterdir() if p.is_dir())
    else:
        # --just mode: only resolved packages
        candidates = sorted(plan)

    print("🔗 Creating symlinks with stow...")

    for pkg_name in candidates:
        if plan is None:
            # Old terminal-filter logic only in full mode
            if pkg_name in ("ghostty", "alacritty", "wezterm"):
                if wsl: continue
                if pkg_name != terminal: continue
            if pkg_name == "windows-terminal":
                continue

        if not (STOW_DIR / pkg_name).is_dir():
            print(f"   ⚠  package '{pkg_name}' not found in stow-packages")
            continue

        print(f"   → {pkg_name}")
        run(["stow", "-R", "-t", str(Path.home()), pkg_name], cwd=str(STOW_DIR))
```

### 3. `2_install.py` — `--just` flag

```python
parser.add_argument(
    "--just", nargs="+", metavar="PKG",
    help="only stow specified packages + deps + base packages"
)
```

When `--just` is present, run the full pipeline but each step consults the resolved plan to decide whether to execute.

```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("--just", nargs="+", metavar="PKG")
    args = parser.parse_args()
    conf = cfg.load()

    if args.just:
        core.STOW_PLAN = resolve_stow_plan(conf, args.just)

    for label, fn in STEPS:
        if core.STOW_PLAN is not None and should_skip_step(label, core.STOW_PLAN, conf):
            print(f"   (skipped — not needed by {', '.join(args.just)})")
            continue
        banner(label)
        fn(conf)

    # … summary …
```

`core.STOW_PLAN` is `None` by default (full install mode). When `--just` is used, it's set to a `set[str]` of resolved packages.

### Step-level skip logic (`should_skip_step`)

| Step            | Skip condition                                                                    |
| --------------- | --------------------------------------------------------------------------------- |
| System packages | Never skips (base deps always needed)                                             |
| CLI tools       | Skip if no tool in the plan requires it (e.g., `lazyvim` needs neovim binary)     |
| Fonts           | Skip if no package in the plan uses Nerd Font                                     |
| Stow            | Never skips (main action of `--just`)                                             |
| Runtimes        | Skip if no runtime in the plan is needed (e.g., `lazyvim` → node, `opencode` → node) |
| Post-install    | Skip if TPM/windows-terminal not in plan                                          |
| Verify          | Only verify tools relevant to the plan                                            |

### 4. Terminal configs — tmux consistency

- **alacritty** (`alacritty.toml`): add a startup command to launch tmux (matching ghostty's behavior: `tmux new-session -A -D -s main`).
- **wezterm** (`wezterm.lua`): same — spawn tmux at startup.

This makes all four terminals behave consistently.

### 5. No changes needed

- `install.sh` and `1_setup.sh` already pass `$@` through — no edits required.
- Existing `stow.enabled`, `stow.terminal`, and WSL detection stay unchanged.

## Files changed

| File                                                       | Change                                                                        |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `install/config.json`                                      | Add `stow.base`, `stow.deps`                                                  |
| `install/core.py`                                          | Add `STOW_PLAN = None` module variable                                        |
| `install/stow.py`                                          | Add `resolve_stow_plan()`, modify `stow_packages()` to check `core.STOW_PLAN` |
| `install/2_install.py`                                     | Add `--just` flag, `should_skip_step()`, smart pipeline                       |
| `stow-packages/alacritty/.config/alacritty/alacritty.toml` | Add tmux launch                                                               |
| `stow-packages/wezterm/.config/wezterm/wezterm.lua`        | Add tmux launch                                                               |

## Non-goals

- This does not change the full-install flow (`./install.sh` with no flags).
- No new config files or external dependency files — everything lives in `config.json` and the python modules.
