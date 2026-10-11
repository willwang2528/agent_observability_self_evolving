"""Reject execution-only PASS, dropped cases, and incomplete success evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
TARGET = Path(__file__).with_name("accept_success.py")

class SuccessGateTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TARGET.exists(), "Strict success gate is not implemented")
        spec = importlib.util.spec_from_file_location("accept_success", TARGET)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def old_report(self, name):
        return json.loads((ROOT / "machine_work/benchmarks" / name / "results/acceptance.json").read_text())

    def valid_report(self, name="webshop"):
        # Synthetic validation fixture only; never a benchmark result.
        r = self.old_report(name)
        r.update(successes=2, mean_reward=1.0, selected_attempt="test_fixture_only")
        for c in r["cases"]:
            c["score"].update(reward=1.0, won=True, done=True)
        return r

    def test_old_partial_webshop_pass_is_rejected(self):
        with self.assertRaises(ValueError):
            self.module.validate_success("webshop", self.old_report("webshop"))

    def test_old_zero_success_tau_pass_is_rejected(self):
        with self.assertRaises(ValueError):
            self.module.validate_success("tau_bench", self.old_report("tau_bench"))

    def test_two_completed_replayed_successes_are_accepted(self):
        self.module.validate_success("webshop", self.valid_report())

    def test_inflating_successes_does_not_override_case_rewards(self):
        r = self.valid_report(); r["cases"][0]["score"]["reward"] = 2/3
        with self.assertRaises(ValueError): self.module.validate_success("webshop", r)

    def test_duplicate_task_cannot_replace_failed_task(self):
        r = self.valid_report(); r["cases"][1]["task"] = 0
        with self.assertRaises(ValueError): self.module.validate_success("webshop", r)

    def test_dropped_task_is_rejected(self):
        r = self.valid_report(); r["cases"].pop()
        with self.assertRaises(ValueError): self.module.validate_success("webshop", r)

    def test_unfinished_episode_cannot_pass_with_reward_one(self):
        r = self.valid_report(); r["cases"][0]["score"]["done"] = False
        with self.assertRaises(ValueError): self.module.validate_success("webshop", r)

    def test_unverified_replay_is_rejected(self):
        r = self.valid_report(); r["cases"][0]["official_replay"] = "FAIL"
        with self.assertRaises(ValueError): self.module.validate_success("webshop", r)

    def test_missing_model_calls_is_rejected(self):
        r = self.valid_report(); r["cases"][0]["actor"]["calls"] = 0
        with self.assertRaises(ValueError): self.module.validate_success("webshop", r)

    def test_missing_whole_attempt_identity_is_rejected(self):
        r = self.valid_report(); r.pop("selected_attempt")
        with self.assertRaises(ValueError): self.module.validate_success("webshop", r)

if __name__ == "__main__": unittest.main()
