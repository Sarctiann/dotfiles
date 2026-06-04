# Split Pipeline + Parallel Containers Design

> **Status:** Implemented — see implementation notes below.

**Date:** 2026-06-02
**Author:** Sebastian (via opencode)

## Problem

The current `test_pipeline.py` script:

1. Removes containers immediately via `--rm`, making the cleanup prompt useless
2. Runs containers serially (no parallelism)
3. Has no pause point for manual testing between install and uninstall

## Solution

Split the pipeline into two phases with per-container pauses, run containers in parallel using `asyncio`.

## Architecture

### New Files

| File                                | Purpose                                        |
| ----------------------------------- | ---------------------------------------------- |
| `test_containers/test_install.sh`   | Stages 0-2: preexisting files, install, verify |
| `test_containers/test_uninstall.sh` | Stages 3-4: uninstall, verify                  |

### Modified Files

| File                      | Changes                                                                 |
| ------------------------- | ----------------------------------------------------------------------- |
| `test_pipeline.py` | asyncio parallelism, per-container pauses, split pipeline orchestration |
| `TESTING.md`              | Updated usage docs                                                      |

### Unchanged

| File                 | Reason                                         |
| -------------------- | ---------------------------------------------- |
| `docker-compose.yml` | Service names already stable                   |
| `test_pipeline.sh`   | Kept as reference, superseded by split scripts |

## Pipeline State Sharing

When running in pipeline mode, checksums from `test_install.sh` must be available to `test_uninstall.sh`.

**Mechanism:** Shared file via bind mount at `/dotfiles/testing/test_containers/.pipeline_state/<system>.env`

- `test_install.sh` writes `GHOSTTY_MD5`, `BAT_MD5`, `PRETOOL_MD5` to the file
- `test_uninstall.sh` sources the file at startup
- Directory created at test start, cleaned up in `cleanup()`

## Python Script Flow

```
main()
├── asyncio: build all containers in parallel
├── asyncio: install phase (parallel)
│   └── per container: run test_install.sh → show result → pause for manual testing → prompt for uninstall
├── asyncio: uninstall phase (parallel)
│   └── per container: run test_uninstall.sh → show result → pause
└── cleanup (if not --keep)
```

### Per-container pause prompt

```
🧪 linux install → exit 0
   → Container: testing-test-into-containers-linux-1
   → Enter with: docker exec -it testing-test-into-containers-linux-1 bash
   → Ready for manual testing. Proceed to uninstall? [Y/n]
```

### Container name resolution

Container names are derived by running `docker compose run -d system bash <script>`, then reading the container name from stdout (docker prints the name when run with `-d`). The name is shown to the user for `docker exec`. After showing the name, we `docker wait <name>` to block until the script finishes.

## Parallel Execution

```python
import asyncio

async def run_container_phase(system: str, phase_script: str, no_log: bool, pipeline_state_dir: Path) -> tuple[str, int]:
    """Run a single phase in a container. Returns (container_name, exit_code)."""
    # docker compose run -d system bash <phase_script> → get container name
    # docker wait <container_name> → get exit code
    # Stream logs from file or docker logs
    # Return (container_name, exit_code)

async def build_all(systems: list[str]) -> None:
    """Build all containers in parallel."""
    await asyncio.gather(*[asyncio.create_subprocess_exec("docker", "compose", "build", s) for s in systems])

async def run_phase(systems: list[str], phase_script: str, no_log: bool, pipeline_state_dir: Path) -> dict[str, int]:
    """Run a phase across all containers in parallel, then pause per container."""
    results = {}
    tasks = {sys: asyncio.create_task(run_container_phase(sys, phase_script, no_log, pipeline_state_dir)) for sys in systems}
    # Wait all, then prompt per container sequentially
    for sys in systems:
        results[sys] = await tasks[sys]
        # pause and prompt
    return results
```

## Implementation Notes

- `--pipeline` flag was removed — the default mode always runs the full install + uninstall pipeline
- No per-container pause between phases; pipeline runs in a single shot via `test_pipeline.sh`
- Progress indicator (heartbeat every 15s) added so users see containers are still working
- `npm` added to Dockerfiles for npm global package compatibility

## Flags (backwards compatible)

| Flag       | Behavior                                                |
| ---------- | ------------------------------------------------------- |
| (none)     | Run full install + uninstall pipeline, prompt for cleanup |
| `--keep`   | Skip cleanup prompt, containers persist                 |
| `--no-log` | Print logs to stdout instead of file                    |

## Cleanup

```
docker compose rm -f -s  # Remove stopped containers
docker compose down --remove-orphans  # Tear down network
rm -rf .pipeline_state/  # Clean shared state
```

## Testing

- Verify parallel build works
- Verify per-container pause shows correct container name
- Verify checksums pass between install and uninstall in pipeline mode
- Verify `--keep` skips cleanup prompt
- Verify `--no-log` streams to stdout
