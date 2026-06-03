# TODO

Pending improvements and known gaps.

## Stow packages

- [ ] **`--just` for uninstall** — allow `./uninstall.sh --just PKG` to remove only specific packages and their dependencies, with backup restore
- [ ] **Auto-derive `should_skip_step` from config** — instead of hardcoding which packages need which pipeline steps, derive it from `config.json` metadata so new packages don't require code changes
- [ ] **Validate new packages** — check that files in `stow-packages/` have correct relative paths before stowing
- [ ] **Config-package diff** — warn when config.json references packages missing from `stow-packages/`, or when `stow-packages/` has directories not mentioned in config

## Pipeline

- [ ] **Stricter error handling** — decide which pipeline failures should abort vs warn. Currently some errors crash the whole pipeline, others print ⚠️ and continue
- [ ] **Skip verification on `--just`** — verification currently runs but always returns True (hardcoded). Either make it meaningful or skip it entirely
- [ ] **Detect config changes since last install** — diff current config vs manifest to know what changed before running
- [x] **Fonts as base step** — fonts are now always installed (non-skippable), removed from `should_skip_step`
- [x] **Clean system_packages** — removed `stow`, `curl`, `unzip` (duplicated from Stage 1), removed `luarocks` (not base)

## Package dependencies

- [ ] **Conditional system packages** — install luarocks only when zsh is in the stow plan, not unconditionally
- [ ] **Formalize base_dependencies in config.json** — explicit section for packages/steps that always run

## Testing

- [ ] **GitHub Actions CI** — run container tests on push/PR
- [ ] **Test macOS path** — the `mac` target exists in design specs but was never implemented (runs subset of pipeline locally)
- [ ] **WSL-specific tests** — verify windows-terminal symlink logic, `/mnt/c` path resolution

## Documentation

- [ ] **CLI reference** — document all `2_management.py` subcommands and flags (for power users calling it directly)
- [ ] **Architecture diagram** — visual flow of install/uninstall pipeline

## Maintenance

- [ ] **Dependency bumps** — pin GitHub release versions in config.json or auto-update
- [ ] **Nix / Homebrew / system package drift** — ensure `system_packages` list matches what each OS actually needs
