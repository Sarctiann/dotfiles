# `--just` flag for uninstall

## Problem

`./uninstall.sh` removes **everything** — all stow symlinks, CLI tools, runtimes, fonts. There's no way to undo only a subset (e.g., "I installed ghostty but I don't want it anymore").

The install side already has `--just PKG` for selective install. The uninstall side needs the same.

## Design

### Entry point

```bash
./uninstall.sh --just ghostty
```

### What it does

1. Only runs the **Stow** step of the uninstall pipeline
2. Unstows only the requested packages (removes symlinks)
3. Restores stow backups for those packages
4. Updates the manifest — removes those packages and their backups from `stow.packages` and `stow.backups`
5. Skips everything else (CLI tools, runtimes, npm packages, fonts, post-install)

### What it does NOT do

- Does not remove CLI tools / binaries
- Does not remove runtimes (nvm, bun, rust, opencode)
- Does not remove npm global packages
- Does not remove fonts
- Does not resolve transitive dependencies

### CLI

```python
uninstall_parser.add_argument("--just", nargs="+", metavar="PKG")
```

### Pipeline changes

In `cmd_uninstall()`, if `--just` is provided:

1. Set `core.STOW_PLAN = resolve_stow_plan(conf, args.just)`
2. In the UNINSTALL_STEPS loop, skip everything except Stow (similar to how `should_skip_step` works in install)

### Stow changes

`_uninstall_stow()` needs to accept the `--just` plan. If `STOW_PLAN` is set:

1. Only unstow packages in the plan
2. Only restore backups for those packages
3. Update manifest — remove unstowed packages from `packages` list and their entries from `backups`

### `--just` + other uninstall flags

Work with `-f` (force) and `-i` (interactive): `./uninstall.sh --just ghostty -f`

### Edge cases

| Scenario | Behavior |
|----------|----------|
| Package not in manifest | Warn and skip |
| Package not in stow-packages | Warn and skip |
| Multiple packages | `--just ghostty tmux` — all are processed |
| No packages after removal | Manifest updated, stow section may be empty |
| `--just` without `-f` | Still prompts for confirmation |
