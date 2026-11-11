#!/usr/bin/env python3
"""Probe assigned models for availability with a minimal request.

This is a connectivity check, not a benchmark: each unique model+variant gets
one tiny prompt through `opencode run`, with an optional retry for transient
failures.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time


PROBE_PROMPT = "Reply with exactly: PROBE-OK. Do not use any tools."
TOKEN_PATTERN = re.compile(r"PROBE[-_ ]?OK", re.IGNORECASE)
ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def split_target(value):
    """Split provider/model#variant into a model and an optional variant."""
    model, separator, variant = value.rpartition("#")
    if not separator:
        return value, None
    return model, variant or None


def join_target(model, variant):
    return "{}#{}".format(model, variant) if variant else model


def load_assignments(path):
    """Read assignments as agent -> model or agent -> {model, variant}."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        items = list(data.items())
    elif isinstance(data, list):
        items = [(None, value) for value in data]
    else:
        raise ValueError("Assignments must be an object or an array")

    entries = []
    for agent, value in items:
        owner = agent or "<list>"
        if isinstance(value, str):
            model, variant = split_target(value)
        elif isinstance(value, dict):
            model_value = value.get("model")
            if not isinstance(model_value, str) or not model_value:
                raise ValueError(
                    "Assignment for {} is missing a 'model' string".format(owner)
                )
            model, embedded_variant = split_target(model_value)
            variant = value.get("variant", embedded_variant)
            if variant is not None and not isinstance(variant, str):
                raise ValueError(
                    "Assignment for {} has a non-string 'variant'".format(owner)
                )
        else:
            raise ValueError(
                "Assignment for {} must be a model string or an object".format(owner)
            )

        entries.append(
            {
                "agent": agent,
                "model": model,
                "variant": variant,
                "target": join_target(model, variant),
            }
        )
    return entries


def dedupe_targets(entries):
    """Merge entries that refer to the same model+variant."""
    merged = {}
    order = []

    for entry in entries:
        target = entry["target"]
        if target not in merged:
            merged[target] = {
                "target": target,
                "model": entry["model"],
                "variant": entry["variant"],
                "agents": [],
            }
            order.append(target)
        if entry["agent"] and entry["agent"] not in merged[target]["agents"]:
            merged[target]["agents"].append(entry["agent"])

    return [merged[target] for target in order]


def strip_ansi(text):
    return ANSI_PATTERN.sub("", text or "")


def classify_error(detail):
    lowered = detail.lower()
    if "model unavailable" in lowered or "model not found" in lowered:
        return "unavailable"
    if "rate limit" in lowered or "too many requests" in lowered or "429" in lowered:
        return "rate-limited"
    return "error"


def kill_process_group(process):
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_attempt(target, timeout, cwd):
    """Run a single probe attempt and return (passed, status, detail, seconds)."""
    command = [
        "opencode",
        "run",
        "--archived",
        "--title",
        "model availability probe",
        "--model",
        target,
        PROBE_PROMPT,
    ]
    started = time.monotonic()

    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError:
        return False, "error", "OpenCode executable not found", 0.0

    try:
        stdout, stderr = process.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        kill_process_group(process)
        stdout, stderr = process.communicate()
        timed_out = True

    duration = time.monotonic() - started
    output = strip_ansi(stdout or "")
    error = strip_ansi(stderr or "")
    combined = "{} {}".format(error.strip(), output.strip()).strip()
    detail = " ".join(combined.split())[-500:] or "exit code {}".format(process.returncode)

    if timed_out:
        return False, "timeout", "Timed out after {}s".format(timeout), duration
    if process.returncode != 0:
        return False, classify_error(combined), detail, duration
    if not TOKEN_PATTERN.search(output):
        return False, "unexpected-response", detail, duration

    return True, "ok", "PROBE-OK received", duration


def probe_target(entry, timeout, attempts, retry_delay, cwd):
    history = []
    total_duration = 0.0
    passed = False
    status = "error"
    detail = ""

    for attempt in range(1, attempts + 1):
        passed, status, detail, duration = run_attempt(entry["target"], timeout, cwd)
        total_duration += duration
        history.append(
            {
                "attempt": attempt,
                "passed": passed,
                "status": status,
                "duration_seconds": round(duration, 2),
                "detail": detail,
            }
        )
        if passed:
            break
        if status in ("unavailable", "unexpected-response"):
            break
        if attempt < attempts:
            time.sleep(retry_delay)

    return {
        "target": entry["target"],
        "model": entry["model"],
        "variant": entry["variant"],
        "agents": entry["agents"],
        "passed": passed,
        "status": "ok" if passed else status,
        "attempts": len(history),
        "duration_seconds": round(total_duration, 2),
        "detail": detail,
        "history": history,
    }


def render_text(results):
    lines = ["Model availability probe results:"]

    for result in results:
        marker = "PASS" if result["passed"] else "FAIL"
        suffix = ""
        if not result["passed"]:
            suffix = " - {}: {}".format(result["status"], result["detail"])
        lines.append(
            "[{}] {} ({} attempt(s), {:.1f}s){}".format(
                marker,
                result["target"],
                result["attempts"],
                result["duration_seconds"],
                suffix,
            )
        )

    unavailable = [result["target"] for result in results if not result["passed"]]
    lines.append("")
    if unavailable:
        lines.append("Unavailable models:")
        lines.extend("- {}".format(target) for target in unavailable)
    else:
        lines.append("All models responded successfully.")

    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Probe model availability with a one-token OpenCode request"
    )
    parser.add_argument(
        "--assignments",
        help="JSON file with agent-to-model assignments",
    )
    parser.add_argument(
        "--targets",
        nargs="*",
        default=[],
        help="Explicit targets in provider/model or provider/model#variant form",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Timeout per attempt in seconds (default: 60)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=2,
        help="Total attempts per target, including the first (default: 2)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=3.0,
        help="Seconds between attempts (default: 3)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between targets (default: 0.5)",
    )
    parser.add_argument(
        "--cwd",
        help="Working directory for probes (default: a neutral temp directory)",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output",
        help="Write the rendered results to this file",
    )
    return parser.parse_args(argv)


def probe_cwd(explicit):
    if explicit:
        return explicit
    path = os.path.join(tempfile.gettempdir(), "opencode", "model-probe")
    os.makedirs(path, exist_ok=True)
    return path


def main(argv=None):
    args = parse_args(argv)

    if args.attempts < 1:
        print("error: --attempts must be at least 1", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("error: --timeout must be greater than 0", file=sys.stderr)
        return 2

    try:
        entries = []
        if args.assignments:
            entries.extend(load_assignments(args.assignments))
        for target in args.targets:
            model, variant = split_target(target)
            entries.append(
                {
                    "agent": None,
                    "model": model,
                    "variant": variant,
                    "target": join_target(model, variant),
                }
            )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2

    if not entries:
        print("error: provide --assignments and/or --targets", file=sys.stderr)
        return 2
    if not shutil.which("opencode"):
        print("error: opencode executable not found", file=sys.stderr)
        return 2

    targets = dedupe_targets(entries)
    cwd = probe_cwd(args.cwd)
    results = []

    for index, entry in enumerate(targets):
        results.append(
            probe_target(
                entry,
                args.timeout,
                args.attempts,
                args.retry_delay,
                cwd,
            )
        )
        if args.delay and index < len(targets) - 1:
            time.sleep(args.delay)

    ok_count = sum(1 for result in results if result["passed"])
    unavailable = [result["target"] for result in results if not result["passed"]]
    payload = {
        "probe_token": "PROBE-OK",
        "timeout_seconds": args.timeout,
        "attempts": args.attempts,
        "results": results,
        "summary": {
            "total": len(results),
            "ok": ok_count,
            "failed": len(results) - ok_count,
        },
        "unavailable": unavailable,
    }

    rendered = (
        json.dumps(payload, indent=2, ensure_ascii=False)
        if args.format == "json"
        else render_text(results)
    )

    if args.output:
        output_path = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as file:
            file.write(rendered)
            file.write("\n")

    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
