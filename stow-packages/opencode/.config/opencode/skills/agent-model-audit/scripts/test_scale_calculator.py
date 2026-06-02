#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("scale-calculator.py")


class ScaleCalculatorCliTest(unittest.TestCase):
    def run_script(self, data, assignments=None, *args):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            data_path = tmp_path / "data.json"
            data_path.write_text(json.dumps(data), encoding="utf-8")

            command = [sys.executable, str(SCRIPT), "--data", str(data_path), *args]
            if assignments is not None:
                assignments_path = tmp_path / "assignments.json"
                assignments_path.write_text(json.dumps(assignments), encoding="utf-8")
                command.extend(["--assignments", str(assignments_path)])

            return subprocess.run(command, text=True, capture_output=True, check=False)

    def test_errors_when_assignment_references_missing_model(self):
        data = {"models": {"known": {"intelligence": 80, "cost": 1.0, "speed": 100}}}
        assignments = {"agent-a": "known", "agent-b": "missing"}

        result = self.run_script(data, assignments)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr)

    def test_json_output_includes_tiers_icons_and_labels(self):
        data = {
            "models": {
                "slow": {"intelligence": 50, "cost": 1.0, "speed": 10},
                "mid": {"intelligence": 75, "cost": 5.0, "speed": 50},
                "fast": {"intelligence": 100, "cost": 9.0, "speed": 90},
            }
        }

        result = self.run_script(data, None, "--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["models"]["fast"]["intelligence"]["tier"], 3)
        self.assertEqual(output["models"]["fast"]["intelligence"]["icon"], "󰫣󰫣󰫣 ")
        self.assertEqual(output["models"]["fast"]["intelligence"]["label"], "Excellent")

        slow_intel = output["models"]["slow"]["intelligence"]
        self.assertEqual(slow_intel["tier"], 0)
        self.assertEqual(slow_intel["icon"], "--- ")
        self.assertEqual(slow_intel["label"], "Basic")

    def test_cost_zero_and_missing_speed_use_special_tier_zero(self):
        data = {
            "models": {
                "free": {"intelligence": 50, "cost": 0.0},
                "cheap": {"intelligence": 75, "cost": 5.0, "speed": 50},
                "fast": {"intelligence": 100, "cost": 10.0, "speed": 100},
            }
        }

        result = self.run_script(data, None, "--format", "json")

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)

        self.assertEqual(output["models"]["free"]["cost"]["tier"], 0)
        self.assertEqual(output["models"]["free"]["cost"]["icon"], "--- ")
        self.assertEqual(output["models"]["free"]["cost"]["label"], "Free")

        self.assertEqual(output["models"]["free"]["speed"]["tier"], 0)
        self.assertEqual(output["models"]["free"]["speed"]["icon"], "--- ")
        self.assertEqual(output["models"]["free"]["speed"]["label"], "Unknown")

        self.assertEqual(output["models"]["cheap"]["cost"]["tier"], 1)
        self.assertEqual(output["models"]["fast"]["cost"]["tier"], 3)
        self.assertEqual(output["models"]["cheap"]["speed"]["tier"], 1)
        self.assertEqual(output["models"]["fast"]["speed"]["tier"], 3)

    def test_text_header_does_not_escape_dollar_sign(self):
        data = {"models": {"known": {"intelligence": 80, "cost": 1.0, "speed": 100}}}

        result = self.run_script(data)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Cost ($/1M tok)", result.stdout)
        self.assertNotIn("\\$/1M tok", result.stdout)


if __name__ == "__main__":
    unittest.main()
