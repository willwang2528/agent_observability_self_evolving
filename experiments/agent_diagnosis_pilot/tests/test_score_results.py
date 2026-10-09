"""Synthetic aggregation tests: failures stay in denominators and cost totals."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "score_results.py"


class ScoreResultsTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "score_results.py has not been implemented")
        spec = importlib.util.spec_from_file_location("score_results", SCRIPT)
        self.scorer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.scorer)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.jobs = []
        self.gold = {}
        for case_id, stratum, total, gold_step, visible in (
            ("a", "algorithm", 5, 2, [0, 4]),
            ("b", "algorithm", 2, 0, [0, 1]),
            ("c", "handcrafted", 5, 4, [0, 4]),
        ):
            self.gold[case_id] = {"agent": "Planner", "step": gold_step, "reason": "Gold reason."}
            for condition in ("full", "head_tail_12000_chars"):
                included = list(range(total)) if condition == "full" else visible
                job = {"job_id": f"{case_id}__{condition}", "case_id": case_id,
                       "condition": condition, "stratum": stratum, "length_tertile": "short",
                       "included_steps": included, "omitted_steps": [i for i in range(total) if i not in included],
                       "total_steps": total, "known_agent_names": ["Planner"],
                       "prompt_sha256": f"hash-{case_id}-{condition}", "prompt_chars": 200,
                       "trace_stats": {"full_chars": 100, "rendered_chars": 100 if len(included) == total else 50}}
                self.jobs.append(job)
        self.write_json("results/plan.json", {"jobs": self.jobs, "model": "test-model",
                                               "reasoning_effort": "xhigh", "source_commit": "fixture"})
        self.write_json("data/gold.json", self.gold)

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def result(self, case_id, condition="full", *, step=None, abstain=False, **overrides):
        job = next(j for j in self.jobs if j["case_id"] == case_id and j["condition"] == condition)
        pred = {"agent": None if abstain else "Planner",
                "step": None if abstain else (self.gold[case_id]["step"] if step is None else step),
                "evidence_steps": [] if abstain else [job["included_steps"][0]],
                "reason": "Recorded diagnosis.", "repair_hint": "Proposed correction only."}
        result = {"job_id": job["job_id"], "case_id": case_id, "condition": condition,
                  "prompt_sha256": job["prompt_sha256"], "completed": True,
                  "transport_ok": True, "usable": True, "prediction": pred,
                  "prediction_error": None, "tool_item_types": [], "attempt_count": 1,
                  "usage": {"input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 3},
                  "all_attempt_usage": {"input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 3},
                  "elapsed_seconds": 3, "all_attempt_elapsed_seconds": 3}
        result.update(overrides)
        self.write_json(f"results/runs/{job['job_id']}/result.json", result)
        return result

    def populate_mixed_results(self):
        budget = "head_tail_12000_chars"
        self.result("a")
        self.result("a", budget, step=4)
        self.result("b")
        # b's budget job is missing: it must still count in all/no-op denominators.
        final = self.result("c", attempt_count=2,
                            all_attempt_usage={"input_tokens": 17, "cached_input_tokens": 3, "output_tokens": 5},
                            all_attempt_elapsed_seconds=5)
        self.write_json("results/runs/c__full/attempt_1/metadata.json", {
            "usage": {"input_tokens": 7, "cached_input_tokens": 1, "output_tokens": 2},
            "elapsed_seconds": 2, "tool_item_types": ["command_execution"]})
        self.write_json("results/runs/c__full/attempt_2/metadata.json", {
            "usage": final["usage"], "elapsed_seconds": 3, "tool_item_types": []})
        self.result("c", budget, abstain=True)

    def test_missing_and_contaminated_jobs_stay_in_planned_accuracy_denominator(self):
        self.populate_mixed_results()
        metrics, rows = self.scorer.score_directory(self.root)
        self.assertEqual(len(rows), 6)
        full = metrics["groups"]["all"]["full"]
        budget = metrics["groups"]["all"]["head_tail_12000_chars"]
        self.assertEqual((full["n"], full["usable"], full["counts"]["joint"]), (3, 2, 2))
        self.assertAlmostEqual(full["rates"]["joint"], 2 / 3)
        self.assertEqual((budget["n"], budget["missing"], budget["abstained"]), (3, 1, 1))
        self.assertEqual(budget["rates"]["joint"], 0)
        contaminated = next(row for row in rows if row["job_id"] == "c__full")
        self.assertEqual(contaminated["status"], "tool_contaminated")
        self.assertFalse(contaminated["usable"])
        self.assertEqual(contaminated["joint"], 0)

    def test_groups_distinguish_reduced_noop_stratum_and_gold_visibility(self):
        self.populate_mixed_results()
        metrics, _ = self.scorer.score_directory(self.root)
        groups = metrics["groups"]
        self.assertEqual(groups["reduced"]["full"]["n"], 2)
        self.assertEqual(groups["no_op"]["full"]["n"], 1)
        self.assertEqual(groups["stratum"]["algorithm"]["full"]["n"], 2)
        self.assertEqual(groups["stratum"]["handcrafted"]["full"]["n"], 1)
        self.assertEqual(groups["gold_step_included"]["false"]["head_tail_12000_chars"]["n"], 1)
        self.assertEqual(groups["gold_step_included"]["true"]["head_tail_12000_chars"]["n"], 2)

    def test_tokens_count_cached_as_input_subset_and_include_failed_attempt_costs(self):
        self.populate_mixed_results()
        metrics, _ = self.scorer.score_directory(self.root)
        costs = metrics["costs"]
        self.assertEqual(costs["final_tokens"], {
            "input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 15, "total_tokens": 65})
        self.assertEqual(costs["all_attempt_tokens"], {
            "input_tokens": 57, "cached_input_tokens": 11, "output_tokens": 17, "total_tokens": 74})
        self.assertEqual(costs["attempts"], 6)
        self.assertEqual(costs["final_elapsed_seconds"], 15)
        self.assertEqual(costs["all_attempt_elapsed_seconds"], 17)

    def test_paired_outcomes_keep_missing_jobs_and_report_noop_controls_separately(self):
        self.populate_mixed_results()
        metrics, _ = self.scorer.score_directory(self.root)
        pairs = metrics["pairs"]
        self.assertEqual(pairs["all"]["n"], 3)
        self.assertEqual(pairs["all"]["joint_outcomes"], {
            "both_correct": 0, "full_only": 2, "budget_only": 0, "both_wrong": 1})
        self.assertEqual(pairs["all"]["both_usable"], 1)
        self.assertAlmostEqual(pairs["all"]["joint_rate_delta_budget_minus_full"], -2 / 3)
        self.assertEqual(pairs["reduced"]["n"], 2)
        self.assertEqual(pairs["no_op"]["n"], 1)

    def test_out_of_range_or_claimed_usable_invalid_prediction_scores_zero(self):
        self.result("a", step=5)
        metrics, rows = self.scorer.score_directory(self.root)
        row = next(row for row in rows if row["job_id"] == "a__full")
        self.assertEqual(row["status"], "invalid_prediction")
        self.assertFalse(row["valid"])
        self.assertEqual(row["joint"], 0)
        self.assertEqual(metrics["groups"]["all"]["full"]["n"], 3)

    def test_missing_final_result_keeps_available_attempt_cost_without_scoring_it(self):
        self.write_json("results/runs/a__full/attempt_1/metadata.json", {
            "usage": {"input_tokens": 7, "cached_input_tokens": 1, "output_tokens": 2},
            "elapsed_seconds": 2, "tool_item_types": []})
        metrics, rows = self.scorer.score_directory(self.root)
        row = next(row for row in rows if row["job_id"] == "a__full")
        self.assertEqual(row["status"], "missing_result")
        self.assertEqual(row["joint"], 0)
        self.assertEqual(metrics["costs"]["all_attempt_tokens"]["total_tokens"], 9)

    def test_cli_writes_readable_outputs_without_changing_plan_or_gold(self):
        self.populate_mixed_results()
        plan_before = (self.root / "results/plan.json").read_bytes()
        gold_before = (self.root / "data/gold.json").read_bytes()
        proc = subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root)],
                              text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        metrics = json.loads((self.root / "results/metrics.json").read_text())
        self.assertEqual(metrics["planned_jobs"], 6)
        self.assertIn("job_id", (self.root / "results/raw_rows.csv").read_text().splitlines()[0])
        self.assertEqual((self.root / "results/plan.json").read_bytes(), plan_before)
        self.assertEqual((self.root / "data/gold.json").read_bytes(), gold_before)


if __name__ == "__main__":
    unittest.main()
