#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("probe-models.py")

FAKE_OPENCODE = """#!/usr/bin/env bash
set -u

target=""
prompt=""
while [ $# -gt 0 ]; do
  case "$1" in
    --model|-m)
      target="$2"
      shift 2
      ;;
    *)
      prompt="$1"
      shift
      ;;
  esac
done

printf '%s\\n' "$target" >> "$FAKE_LOG"
key=$(printf '%s' "$target" | tr '/#' '__')
count_file="$FAKE_STATE/$key"
count=0
if [ -f "$count_file" ]; then
  count=$(cat "$count_file")
fi
count=$((count + 1))
printf '%s' "$count" > "$count_file"

mode="${FAKE_MODE:-ok}"
if [ "$mode" = "unavailable" ]; then
  echo "Error: Model unavailable: $target" >&2
  exit 1
fi
if [ "$mode" = "retry" ] && [ "$count" -lt 2 ]; then
  echo "Error: temporary provider failure" >&2
  exit 1
fi
if [ "$mode" = "missing-token" ]; then
  echo "I cannot do that."
  exit 0
fi
if [ "$mode" = "timeout" ]; then
  sleep 5
fi

token=$(printf '%s\\n' "$prompt" | grep -o 'PROBE-[A-Z0-9]*' | head -n 1)
if [ -z "$token" ]; then
  echo "probe token missing" >&2
  exit 1
fi
printf '%s\\n' "$token"
exit 0
"""


class ProbeModelsCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        self.log = self.root / "calls.log"
        self.fake = self.bin / "opencode"
        self.fake.write_text(FAKE_OPENCODE, encoding="utf-8")
        self.fake.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, assignments=None, *args, env=None):
        command = [
            sys.executable,
            str(SCRIPT),
            "--format",
            "json",
            "--retry-delay",
            "0",
            "--delay",
            "0",
        ]
        if assignments is not None:
            path = self.root / "assignments.json"
            path.write_text(json.dumps(assignments), encoding="utf-8")
            command.extend(["--assignments", str(path)])
        command.extend(args)

        environment = os.environ.copy()
        environment["PATH"] = "{}:{}".format(self.bin, environment["PATH"])
        environment["FAKE_LOG"] = str(self.log)
        environment["FAKE_STATE"] = str(self.state)
        environment.update(env or {})

        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            env=environment,
            timeout=30,
        )

    def test_passes_available_model(self):
        result = self.run_script({"agent-a": "provider/model"})

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["summary"], {"total": 1, "ok": 1, "failed": 0})
        self.assertEqual(output["unavailable"], [])
        self.assertTrue(output["results"][0]["passed"])

    def test_reports_unavailable_model_without_retrying(self):
        result = self.run_script(
            {"agent-a": "provider/missing"},
            env={"FAKE_MODE": "unavailable"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["summary"]["failed"], 1)
        self.assertEqual(output["unavailable"], ["provider/missing"])
        self.assertEqual(output["results"][0]["status"], "unavailable")
        self.assertEqual(output["results"][0]["attempts"], 1)

    def test_retries_transient_failure(self):
        result = self.run_script(
            {"agent-a": "provider/flaky"},
            "--attempts",
            "2",
            env={"FAKE_MODE": "retry"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["results"][0]["passed"])
        self.assertEqual(output["results"][0]["attempts"], 2)

    def test_fails_when_probe_token_is_missing(self):
        result = self.run_script(
            {"agent-a": "provider/model"},
            env={"FAKE_MODE": "missing-token"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(output["results"][0]["passed"])
        self.assertEqual(output["results"][0]["status"], "unexpected-response")

    def test_probes_variant_from_assignment_object(self):
        result = self.run_script(
            {"agent-a": {"model": "provider/model", "variant": "max"}}
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["results"][0]["target"], "provider/model#max")
        self.assertIn("provider/model#max", self.log.read_text(encoding="utf-8"))

    def test_dedupes_shared_models(self):
        assignments = {
            "agent-a": "provider/model",
            "agent-b": "provider/model",
            "agent-c": {"model": "provider/model", "variant": "max"},
        }

        result = self.run_script(assignments)

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(len(output["results"]), 2)
        calls = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls, ["provider/model", "provider/model#max"])

    def test_marks_timeout(self):
        result = self.run_script(
            {"agent-a": "provider/slow"},
            "--attempts",
            "1",
            "--timeout",
            "0.3",
            env={"FAKE_MODE": "timeout"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(output["results"][0]["passed"])
        self.assertEqual(output["results"][0]["status"], "timeout")

    def test_accepts_explicit_targets(self):
        result = self.run_script(None, "--targets", "provider/model#high")

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["results"][0]["target"], "provider/model#high")


if __name__ == "__main__":
    unittest.main()
