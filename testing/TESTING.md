# Testing

## Purpose

Validate the dotfiles `install.sh` pipeline on Linux and WSL environments using Docker containers. This is the only way to test install changes when developing from macOS.

## Targets

```
./testing/test_into_containers.py [system]
```

| Target  | Runs                         |
| ------- | ---------------------------- |
| `linux` | Ubuntu 24.04 container       |
| `wsl`   | Ubuntu 24.04 + WSL emulation |
| `all`   | Both (default)               |

WSL emulation sets `DOTFILES_WSL=1` (detected by `tools_management/core.py:is_wsl()`) and creates a fake `/mnt/c/Users/` structure to test the windows-terminal stow logic.

## Usage

```bash
# Test both platforms (parallel)
./testing/test_into_containers.py

# Test a single platform
./testing/test_into_containers.py linux
./testing/test_into_containers.py wsl

# Keep containers after test (skip cleanup prompt)
./testing/test_into_containers.py --keep

# Print logs to stdout instead of saving to files
./testing/test_into_containers.py --no-log

# Run full install + uninstall pipeline with pause between phases
./testing/test_into_containers.py --pipeline
./testing/test_into_containers.py linux --pipeline
```

Logs are saved to `testing/test_containers/logs/<target>-<timestamp>.log`.

## Requirements

- Docker Desktop
- The repo bind-mounted into the container (no rebuild needed for code changes)

## What Gets Tested (normal mode)

The full `install.sh` pipeline runs inside each container:

1. System packages (apt)
2. CLI tools from GitHub releases
3. Nerd Fonts
4. Stow symlinks
5. Runtimes (nvm, bun, rust, opencode)
6. Post-install (TPM, Windows Terminal)
7. Verification

## Pipeline mode (`--pipeline`)

Tests the complete install + uninstall cycle, including backup and restore, split into two phases with a pause for manual testing between them.

### Phase 1: Install

1. Creates files simulating a preexisting environment (config files, CLI tool)
2. Runs full `./install.sh`
3. Verifies: tools installed, symlinks created, preexisting files backed up, manifest tracks preexisting correctly
4. **Pauses** — per-container prompt with `docker exec` command for manual testing

### Phase 2: Uninstall

4. Runs `./uninstall.sh -f`
5. Verifies: preexisting files restored with original content, preexisting tools preserved, installed tools removed, manifest deleted
6. **Pauses** — per-container prompt before cleanup

## Manual Testing

During the pause between phases, you can enter any container and inspect the installed state:

```bash
docker exec -it test-linux bash
docker exec -it test-wsl bash
```

The container remains running until you confirm or skip the next phase.

## Parallel Execution

When testing both linux and wsl (`all`), containers build and run in parallel. Each container pauses independently after install, so you can inspect one while the other is still running.
