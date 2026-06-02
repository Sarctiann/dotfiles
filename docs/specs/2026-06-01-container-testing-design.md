# Container-Based Testing for Dotfiles Installation

## Problem

The dotfiles install script supports macOS, Linux (bare-metal), and WSL (Windows Subsystem for Linux).
The author only has access to macOS, making it impossible to test changes to the Linux and WSL
installation paths. Bugs in those paths go undetected until someone tries to install on those
platforms.

## Scope

This spec covers testing only. It does not modify the install pipeline itself beyond a single
minimal change to `is_wsl()`.

## Design

### Overview

A Python CLI orchestrator (`test_into_containers.py`) that builds and runs Docker containers to test
the install script on emulated Linux and WSL environments. macOS cannot be dockerized (Apple
restrictions), so a dry-run mode on the host Mac serves as the macOS test path.

### `test_containers/` Directory

```
test_containers/
├── Dockerfile.linux       # Ubuntu 24.04 with root + user setup
├── Dockerfile.wsl         # Ubuntu 24.04 + WSL emulation
└── logs/                  # Per-run log output
```

### `test_into_containers.py` — CLI Orchestrator

```
usage: test_into_containers.py [-h] [--keep] [--no-log] [system]

positional arguments:
  system      Target system to test: 'linux', 'wsl', or 'mac' (default: all)

options:
  --keep      Leave containers running after tests finish (no-op for mac)
  --no-log    Don't capture logs to file, print to stdout instead
```

When `system` is `mac`, no Docker is involved. The orchestrator runs a subset of the install
pipeline locally (stow, verify, etc.) skipping system packages and runtimes to avoid modifying
the host.

````

**Flow (no args — test both):**

1. `docker compose build linux wsl`
2. `docker compose up -d linux wsl`
3. Attach to container logs, capture to `test_containers/logs/<service>-<ts>.log`
4. Wait for both containers to exit
5. Print summary table: service, exit code, log path
6. Unless `--keep`: prompt `🧹 Remove test containers? [Y/n]`

**Flow (single system):** Same, but only that service.

### `Dockerfile.linux`

```dockerfile
FROM ubuntu:24.04

# Avoid tzdata interactive prompt
ENV DEBIAN_FRONTEND=noninteractive

# Minimal packages needed by stage 1 bootstrap
RUN apt-get update && apt-get install -y \
    sudo git python3 curl unzip stow \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user matching host uid/gid for bind-mount write compat
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} dotfiles && \
    useradd -m -u ${USER_ID} -g dotfiles -s /bin/bash dotfiles && \
    echo "dotfiles ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER dotfiles
WORKDIR /dotfiles

CMD ["./install.sh"]
````

### `Dockerfile.wsl`

Same as linux but:

```dockerfile
# Emulate WSL kernel release for is_wsl() detection
ENV DOTFILES_WSL=1
RUN sudo mkdir -p /mnt/c/Users/TestUser/AppData/Local/Packages \
    /mnt/c/Users/TestUser/AppData/Local/Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState

CMD ["./install.sh"]
```

### Change to `core.py` (`is_wsl()`)

```python
def is_wsl() -> bool:
    """Detect if running under WSL."""
    if os.environ.get("DOTFILES_WSL") == "1":
        return True
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text()
        return "microsoft" in release.lower()
    except (FileNotFoundError, OSError):
        return False
```

This is the only modification to install code. The environment variable takes precedence over the
`/proc` check, enabling WSL emulation without falsifying `/proc`.

### `docker-compose.yml`

```yaml
services:
  linux:
    build:
      context: .
      dockerfile: test_containers/Dockerfile.linux
      args:
        USER_ID: ${UID:-1000}
        GROUP_ID: ${GID:-1000}
    volumes:
      - .:/dotfiles
    working_dir: /dotfiles
    environment:
      - CI=1

  wsl:
    build:
      context: .
      dockerfile: test_containers/Dockerfile.wsl
      args:
        USER_ID: ${UID:-1000}
        GROUP_ID: ${GID:-1000}
    volumes:
      - .:/dotfiles
    working_dir: /dotfiles
    environment:
      - CI=1
```

### macOS Test Path (No Container)

For macOS, the user can run:

```bash
python3 test_into_containers.py mac
```

This runs `install/2_install.py --just nvim` (or another minimal plan) directly on the host,
skipping system packages (brew). This tests the Python pipeline logic without modifying system
packages. The dry-run focus is on stow, verify, and the orchestrator flow — not on brew
installation.

### Logging

Each container run writes to `test_containers/logs/<service>-<timestamp>.log`. The orchestrator
appends a summary line:

```
=== SUMMARY ===
linux  → exit 0  → logs/linux-20260601_143022.log
wsl    → exit 0  → logs/wsl-20260601_143025.log
```

### Cleanup

By default, the script prompts to remove containers and the default network after tests. With
`--keep`, containers remain for inspection.

## Files Changed

- **New:** `test_into_containers.py`
- **New:** `test_containers/Dockerfile.linux`
- **New:** `test_containers/Dockerfile.wsl`
- **New:** `docker-compose.yml` (repo root)
- **Modified:** `install/core.py` (3-line addition to `is_wsl()`)

## Out of Scope

- Testing macOS installation in a container (not possible)
- Modifying the install pipeline beyond the `is_wsl()` change
- GitHub Actions CI integration (future work)
- Testing with non-Ubuntu distros (Arch, Fedora)
