# TODO

Items ordered by priority. We start at #1 and work down without asking.

---

## P1 — Core experience

- [x] **1. Detect config changes since last install** — diff current config vs manifest to know what changed before running. Skip steps whose config hasn't changed.
- [x] **2. Validate new packages** — check that files in `stow-packages/` have correct relative paths before stowing. Prevents broken symlinks.
- [x] **3. Config-package diff** — warn when config.json references packages missing from `stow-packages/`, or when `stow-packages/` has directories not mentioned in config.

## P2 — Code quality

- [ ] **4. Formalize `base_dependencies` in config.json** — explicit section for packages/steps that always run (instead of `should_skip_step` returning `False` for some).
- [ ] **5. Auto-derive `should_skip_step` from config** — replace hardcoded package→step mapping with config-driven metadata.
- [ ] **6. Stricter error handling** — decide which pipeline failures should abort vs warn. Currently some errors crash the whole pipeline, others print ⚠️ and continue.
- [ ] **7. Skip verification on `--just`** — verification currently runs but always returns True (hardcoded). Either make it meaningful or skip it entirely.

## P3 — Testing / CI

- [ ] **8. Test macOS path** — the `mac` target exists in design specs but was never implemented (runs subset of pipeline locally).
- [ ] **10. WSL-specific tests** — verify windows-terminal symlink logic, `/mnt/c` path resolution.

## P4 — Documentation

- [ ] **11. CLI reference** — document all `2_management.py` subcommands and flags (for power users calling it directly).
- [ ] **12. Architecture diagram** — visual flow of install/uninstall pipeline.

## P5 — Maintenance

- [ ] **13. Dependency bumps** — pin GitHub release versions in config.json or auto-update.
- [ ] **14. Nix / Homebrew / system package drift** — ensure `system_packages` list matches what each OS actually needs.

---

## Completed

- [x] **`--just` for uninstall** — allow `./uninstall.sh --just PKG` to remove only specific packages with backup restore.
- [x] **`_clean_path_from_rc` no modifica symlinks** — evitar que uninstall elimine líneas de NVM/BUN del source `.zshrc`.
- [x] **Conditional system packages** — luarocks solo si zsh está en el plan.
- [x] **Fonts as base step** — fonts always installed, removed from `should_skip_step`.
- [x] **Clean system_packages** — removed stow/curl/unzip (duplicated from Stage 1), luarocks (not base).
