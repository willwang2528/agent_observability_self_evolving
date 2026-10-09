"""Contract tests for leakage prevention, budgeted evidence, and strict scoring."""

import importlib.util
from pathlib import Path
import unittest


CORE_PATH = Path(__file__).resolve().parents[1] / "pilot_core.py"


class PilotCoreTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CORE_PATH.is_file(), "pilot_core.py has not been implemented")
        spec = importlib.util.spec_from_file_location("pilot_core", CORE_PATH)
        self.core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.core)

    def raw_case(self):
        return {
            "question": "Find a result.",
            "system_prompt": "Use tools.",
            "question_ID": "SECRET-ID",
            "ground_truth": "SECRET-ANSWER",
            "mistake_agent": "SECRET-AGENT",
            "mistake_step": "SECRET-STEP",
            "mistake_reason": "SECRET-REASON",
            "history": [
                {"name": "Planner", "role": "assistant", "content": "Plan first.",
                 "mistake_reason": "SECRET-INNER"},
                {"name": "Executor", "role": "tool", "content": "Observed result."},
            ],
        }

    def test_sanitize_removes_all_annotation_fields_at_both_levels(self):
        # A broad dictionary copy would leak diagnosis labels into model input.
        case = self.core.sanitize_case(self.raw_case())
        self.assertEqual(set(case), {"question", "system_prompt", "steps", "known_agent_names"})
        self.assertEqual(case["known_agent_names"], ["Planner", "Executor"])
        self.assertEqual(case["steps"][0], {
            "step": 0, "name": "Planner", "role": "assistant", "content": "Plan first."
        })
        self.assertNotIn("SECRET", repr(case))

    def test_sanitize_uses_original_zero_based_positions_and_preserves_text(self):
        case = self.core.sanitize_case(self.raw_case())
        self.assertEqual([entry["step"] for entry in case["steps"]], [0, 1])
        self.assertEqual(case["steps"][1]["content"], "Observed result.")

    def test_sanitize_accepts_rawhistory_alias_but_prefers_history(self):
        raw = self.raw_case()
        raw["rawhistory"] = [{"name": "Other", "content": "Wrong alias."}]
        self.assertEqual(self.core.sanitize_case(raw)["known_agent_names"], ["Planner", "Executor"])
        raw.pop("history")
        self.assertEqual(self.core.sanitize_case(raw)["steps"], [
            {"step": 0, "name": "Other", "role": "", "content": "Wrong alias."}
        ])

    def test_sanitize_rejects_conflicting_source_step_number(self):
        raw = self.raw_case()
        raw["history"][1]["step"] = 2
        with self.assertRaisesRegex(ValueError, "zero-based"):
            self.core.sanitize_case(raw)

    def test_sanitize_rejects_boolean_source_step_number(self):
        raw = self.raw_case()
        raw["history"][0]["step"] = False
        with self.assertRaises(ValueError):
            self.core.sanitize_case(raw)

    def test_sanitize_rejects_missing_agent_identity(self):
        raw = self.raw_case()
        raw["history"][0].pop("name")
        raw["history"][0].pop("role")
        with self.assertRaisesRegex(ValueError, "name"):
            self.core.sanitize_case(raw)

    def test_sanitize_uses_role_as_identity_in_handcrafted_histories(self):
        case = self.core.sanitize_case({
            "system_prompt": {"worker": "Work.", "planner": "Plan."},
            "history": [{"role": "Assistant A", "content": "Look up the answer."}],
        })
        self.assertEqual(case["known_agent_names"], ["Assistant A"])
        self.assertEqual(case["steps"][0]["name"], "Assistant A")
        self.assertEqual(case["system_prompt"], '{"planner": "Plan.", "worker": "Work."}')

    def test_orchestrator_display_suffix_does_not_create_a_different_agent(self):
        case = self.core.sanitize_case({"history": [
            {"role": "Orchestrator (thought)", "content": "Think."},
            {"role": "Orchestrator (-> WebSurfer)", "content": "Search."},
        ]})
        self.assertEqual(case["known_agent_names"], ["Orchestrator"])
        self.assertEqual(case["steps"][1]["name"], "Orchestrator (-> WebSurfer)")
        scores = self.core.score_prediction({"agent": "Orchestrator (thought)", "step": 1},
                                           {"agent": "Orchestrator", "step": 1}, case["known_agent_names"])
        self.assertEqual(scores["joint"], 1)
        self.assertEqual(self.core.canonical_agent("Planner (thought)"), "planner (thought)")

    def test_render_full_trace_preserves_every_step(self):
        result = self.core.render_trace(self.core.sanitize_case(self.raw_case()))
        self.assertIn("zero-based", result["text"])
        self.assertIn("[step 0]", result["text"])
        self.assertIn("[step 1]", result["text"])
        self.assertIn("Observed result.", result["text"])
        self.assertEqual(result["included_steps"], [0, 1])
        self.assertEqual(result["omitted_steps"], [])
        self.assertEqual(result["stats"]["rendered_chars"], len(result["text"]))
        self.assertFalse(result["stats"]["truncated"])

    def test_render_budget_preserves_head_tail_ids_and_exact_character_bound(self):
        raw = {"history": [
            {"name": "Agent", "role": "assistant", "content": str(i).zfill(2) * 40}
            for i in range(12)
        ]}
        case = self.core.sanitize_case(raw)
        result = self.core.render_trace(case, char_budget=350)
        self.assertLessEqual(len(result["text"]), 350)
        self.assertEqual(result["included_steps"], [0, 11])
        self.assertEqual(result["omitted_steps"], list(range(1, 11)))
        self.assertIn("[step 11]", result["text"])
        self.assertIn("omitted steps 1..10", result["text"])
        self.assertEqual(result["stats"]["omitted_step_count"], 10)
        self.assertEqual(result, self.core.render_trace(case, char_budget=350))

    def test_render_does_not_silently_cut_an_oversized_step(self):
        case = self.core.sanitize_case({"history": [{"name": "Agent", "content": "X" * 1000}]})
        result = self.core.render_trace(case, char_budget=100)
        self.assertEqual(result["included_steps"], [])
        self.assertEqual(result["omitted_steps"], [0])
        self.assertNotIn("X", result["text"])
        self.assertLessEqual(len(result["text"]), 100)

    def test_render_rejects_budget_too_small_for_an_honest_omission_marker(self):
        case = self.core.sanitize_case(self.raw_case())
        with self.assertRaisesRegex(ValueError, "budget"):
            self.core.render_trace(case, char_budget=1)

    def test_scoring_uses_integer_equality_not_substring_matching(self):
        scores = self.core.score_prediction({"agent": "Planner", "step": 1},
                                           {"agent": "Planner", "step": 10}, ["Planner"])
        self.assertEqual((scores["who"], scores["when"], scores["joint"]), (1, 0, 0))
        self.assertEqual(scores["when_pm1"], 0)

    def test_scoring_canonicalizes_agent_whitespace_and_case_only(self):
        scores = self.core.score_prediction({"agent": " planner ", "step": 0},
                                           {"agent": "Planner", "step": 0}, ["Planner"])
        self.assertEqual((scores["who"], scores["when"], scores["joint"]), (1, 1, 1))
        bad = self.core.score_prediction({"agent": "Plan", "step": 0},
                                        {"agent": "Planner", "step": 0}, ["Planner"])
        self.assertFalse(bad["valid"])
        self.assertEqual(bad["joint"], 0)

    def test_scoring_rejects_boolean_string_float_and_negative_steps(self):
        for bad_step in (True, False, "1", 1.0, -1):
            with self.subTest(step=bad_step):
                scores = self.core.score_prediction({"agent": "Planner", "step": bad_step},
                                                   {"agent": "Planner", "step": 1}, ["Planner"])
                self.assertFalse(scores["valid"])
                self.assertEqual((scores["who"], scores["when"], scores["joint"]), (0, 0, 0))

    def test_scoring_reports_pm1_separately_from_strict_when(self):
        scores = self.core.score_prediction({"agent": "Planner", "step": 2},
                                           {"agent": "Planner", "step": 1}, ["Planner"])
        self.assertEqual((scores["when"], scores["joint"]), (0, 0))
        self.assertEqual((scores["when_pm1"], scores["joint_pm1"]), (1, 1))

    def test_evidence_validity_requires_visible_step_references(self):
        gold = {"agent": "Planner", "step": 5}
        visible = self.core.score_prediction({"agent": "Planner", "step": 5, "evidence_steps": [0, 9]},
                                            gold, ["Planner"], included_steps=[0, 9])
        omitted = self.core.score_prediction({"agent": "Planner", "step": 5, "evidence_steps": [5]},
                                            gold, ["Planner"], included_steps=[0, 9])
        self.assertTrue(visible["evidence_valid"])
        self.assertFalse(omitted["evidence_valid"])
        self.assertEqual(omitted["joint"], 1)

    def test_prediction_validation_rejects_boolean_evidence_and_unknown_agent(self):
        for prediction in ({"agent": "Planner", "step": 0, "evidence_steps": [True]},
                           {"agent": "Unknown", "step": 0}):
            with self.assertRaises(ValueError):
                self.core.validate_prediction(prediction, ["Planner"])

    def test_explicit_double_null_is_valid_abstention_with_zero_scores(self):
        scores = self.core.score_prediction({"agent": None, "step": None, "evidence_steps": []},
                                           {"agent": "Planner", "step": 1}, ["Planner"])
        self.assertTrue(scores["valid"])
        self.assertTrue(scores["abstained"])
        self.assertEqual((scores["who"], scores["when"], scores["joint"],
                          scores["when_pm1"], scores["joint_pm1"]), (0, 0, 0, 0, 0))

    def test_half_null_or_missing_diagnosis_fields_are_invalid_not_abstentions(self):
        for prediction in ({"agent": None, "step": 1},
                           {"agent": "Planner", "step": None},
                           {}, {"agent": None}, {"step": None}):
            with self.subTest(prediction=prediction):
                scores = self.core.score_prediction(prediction, {"agent": "Planner", "step": 1}, ["Planner"])
                self.assertFalse(scores["valid"])
                self.assertFalse(scores.get("abstained", False))

    def test_step_at_or_beyond_total_steps_is_invalid(self):
        for step in (2, 10):
            with self.subTest(step=step):
                try:
                    scores = self.core.score_prediction({"agent": "Planner", "step": step},
                                                       {"agent": "Planner", "step": 1}, ["Planner"],
                                                       total_steps=2)
                except TypeError as exc:
                    self.fail(f"total_steps validation is not implemented: {exc}")
                self.assertFalse(scores["valid"])
                self.assertEqual(scores["joint"], 0)

    def test_step_bounds_do_not_require_diagnosis_step_to_be_visible(self):
        try:
            scores = self.core.score_prediction({"agent": "Planner", "step": 1},
                                               {"agent": "Planner", "step": 1}, ["Planner"],
                                               included_steps=[0, 2], total_steps=3)
        except TypeError as exc:
            self.fail(f"total_steps validation is not implemented: {exc}")
        self.assertTrue(scores["valid"])
        self.assertEqual(scores["joint"], 1)


if __name__ == "__main__":
    unittest.main()
