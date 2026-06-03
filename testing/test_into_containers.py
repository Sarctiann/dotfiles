#!/usr/bin/env python3
"""Test dotfiles install inside Docker containers or locally on macOS."""

import argparse
import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
LOG_DIR = SCRIPT_DIR / "test_containers" / "logs"
PIPELINE_SCRIPT = "/dotfiles/testing/test_containers/test_pipeline.sh"


async def run_command(
    cmd: list[str],
    cwd: str | None = None,
) -> tuple[bytes, int]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    assert proc.returncode is not None
    return out, proc.returncode


async def build_container(system: str) -> None:
    print(f"🔨 Building {system}...")
    out, rc = await run_command(
        ["docker", "compose", "build", system],
        cwd=str(SCRIPT_DIR),
    )
    if rc != 0:
        print(f"   ❌ {system} build failed")
        print(out.decode())
        raise RuntimeError(f"Build failed for {system}")
    print(f"   ✓ {system} built")


async def start_pipeline(system: str) -> str:
    """Start pipeline script inside a detached container. Returns container name."""
    container_name = f"test-{system}"

    out, rc = await run_command(
        [
            "docker",
            "compose",
            "run",
            "-d",
            "--name",
            container_name,
            system,
            "bash",
            PIPELINE_SCRIPT,
        ],
        cwd=str(SCRIPT_DIR),
    )
    if rc != 0:
        raise RuntimeError(f"Failed to start {container_name}: {out.decode()}")

    return container_name


async def _heartbeat(system: str, stop_event: asyncio.Event) -> None:
    """Print progress every 15s until stop_event is set."""
    interval = 15
    elapsed = 0
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            elapsed += interval
            print(f"   ⏳ {system} running... ({elapsed}s)")


async def collect_result(
    container_name: str,
    system: str,
    no_log: bool,
) -> int:
    """Wait for container to finish, capture logs, return exit code."""

    stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat(system, stop_event))
    await run_command(["docker", "wait", container_name])
    stop_event.set()
    await heartbeat_task

    insp_out, _ = await run_command(
        ["docker", "inspect", "-f", "{{.State.ExitCode}}", container_name],
    )
    exit_code = int(insp_out.decode().strip())

    log_out, _ = await run_command(["docker", "logs", container_name])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"{system}-{ts}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not no_log:
        log_path.write_bytes(log_out)
    else:
        print(log_out.decode())

    return exit_code


async def run_pipeline_phase(
    systems: list[str],
    no_log: bool,
) -> dict[str, int]:
    print(f"\n{'='*50}")
    print("  🚀 Running pipeline (parallel — install + uninstall)")
    print(f"{'='*50}")

    start_tasks = {s: asyncio.create_task(start_pipeline(s)) for s in systems}
    containers = {}
    for s in systems:
        containers[s] = await start_tasks[s]

    collect_tasks = {
        s: asyncio.create_task(collect_result(containers[s], s, no_log))
        for s in systems
    }

    results = {}
    for s in systems:
        exit_code = await collect_tasks[s]
        results[s] = exit_code
        status = "✅" if exit_code == 0 else "❌"
        print(f"  {status} {s} → exit {exit_code}")

    return results


def cleanup() -> None:
    print("🧹 Cleaning up...")
    subprocess.run(
        ["docker", "compose", "rm", "-f", "-s"],
        cwd=SCRIPT_DIR,
        capture_output=True,
    )
    subprocess.run(
        ["docker", "compose", "down", "--remove-orphans"],
        cwd=SCRIPT_DIR,
        capture_output=True,
    )
    for name in ("test-linux", "test-wsl"):
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


async def run_mac(no_log: bool) -> int:
    """Run install with --just nvim on the host macOS machine."""
    print("\n  🍏 macOS test (local — no container)")
    print("  ⚠️  Will run `./install.sh --just nvim` on your machine")
    print("  System packages (brew) are skipped. Stow/verify only.\n")

    cmd = ["bash", str(REPO_ROOT / "install.sh"), "--just", "nvim"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    exit_code = proc.returncode or 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"mac-{ts}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not no_log:
        log_path.write_bytes(out)
    else:
        print(out.decode())

    return exit_code


async def main_async(systems: list[str], keep: bool, no_log: bool) -> int:
    docker_systems = [s for s in systems if s != "mac"]
    run_mac_flag = "mac" in systems

    if docker_systems:
        cleanup()
        try:
            await asyncio.gather(*[build_container(s) for s in docker_systems])
        except RuntimeError:
            return 1

    docker_results = {}
    if docker_systems:
        docker_results = await run_pipeline_phase(docker_systems, no_log)

    mac_code = 0
    if run_mac_flag:
        mac_code = await run_mac(no_log)
        status = "✅" if mac_code == 0 else "❌"
        print(f"  {status} mac   → exit {mac_code}")

    print(f"\n{'='*50}")
    print("  === SUMMARY ===")
    print(f"{'='*50}")
    results = {**docker_results}
    if run_mac_flag:
        results["mac"] = mac_code
    for s, code in results.items():
        status = "✅" if code == 0 else "❌"
        print(f"  {status} {s:6s} → exit {code}")

    if docker_systems and not keep:
        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(
                None,
                lambda: input("\n🧹 Remove test containers? [Y/n] ").strip().lower(),
            )
        except (EOFError, KeyboardInterrupt):
            resp = "y"
        if resp in ("", "y", "yes"):
            cleanup()

    failures = [s for s, c in results.items() if c != 0]
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test dotfiles install in Docker containers",
    )
    parser.add_argument(
        "system",
        nargs="?",
        default="all",
        choices=["all", "linux", "wsl", "mac"],
        help="system to test (default: all)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep containers after test (skip cleanup prompt)",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="print logs to stdout instead of file",
    )
    args = parser.parse_args()

    systems = []
    if args.system in ("all", "linux"):
        systems.append("linux")
    if args.system in ("all", "wsl"):
        systems.append("wsl")
    if args.system == "mac":
        systems.append("mac")

    sys.exit(asyncio.run(main_async(systems, args.keep, args.no_log)))


if __name__ == "__main__":
    main()
