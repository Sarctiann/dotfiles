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
```

Logs are saved to `testing/test_containers/logs/<target>-<timestamp>.log`. During execution, a progress indicator prints every 15s (`⏳ linux running... (30s)`) so you know containers are still working.

## Requirements

- Docker Desktop
- The repo bind-mounted into the container (no rebuild needed for code changes)

## What Gets Tested

Each container runs the full install + uninstall pipeline (`test_pipeline.sh`):

### Stage 0: Preexisting files

Creates simulated preexisting environment (config files, CLI tool) with checksums recorded for restore verification.

### Stage 1: Install

The full `install.sh` pipeline runs inside each container:

1. System packages (apt)
2. CLI tools from GitHub releases
3. Nerd Fonts
4. Stow symlinks
5. Runtimes (nvm, bun, rust, opencode)
6. NPM packages (auggie, gemini-cli — via bun, fallback npm)
7. Post-install (TPM, Windows Terminal)
8. Verification

### Stage 2: Verify install

Validates: tools installed, symlinks created, preexisting files backed up, manifest tracks preexisting correctly.

### Stage 3: Uninstall

Runs `./uninstall.sh -f`.

### Stage 4: Verify uninstall

Validates: preexisting files restored with original content, preexisting tools preserved, installed tools removed, manifest deleted.

## Progress Indicator

When testing both linux and wsl in parallel, a heartbeat prints every 15s:

```
⏳ linux running... (15s)
⏳ linux running... (30s)
⏳ linux running... (45s)
```

This confirms containers are still executing while waiting for the full pipeline.

## Parallel Execution

When testing both linux and wsl (`all`), containers build and run in parallel. Exit codes are printed as each container finishes.
