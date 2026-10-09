import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import run_pilot
except ImportError:
    run_pilot = None


class RunnerTests(unittest.TestCase):
    def test_labels_and_task_answer_cannot_change_prompt(self):
        self.assertIsNotNone(run_pilot, "runner not implemented")
        raw = {"question": "Find a count", "system_prompt": {"A": "Count exactly"},
               "history": [{"name": "A", "role": "assistant", "content": "count=0"}],
               "ground_truth": "SECRET ANSWER", "mistake_agent": "SECRET AGENT",
               "mistake_step": 99, "mistake_reason": "SECRET REASON"}
        prompt, info = run_pilot.prepare_input(raw, None)
        self.assertNotIn("SECRET", prompt)
        changed = {**raw, "ground_truth": "OTHER", "mistake_step": 0}
        self.assertEqual(prompt, run_pilot.prepare_input(changed, None)[0])
        self.assertEqual(info["included_steps"], [0])
        self.assertIn("Count exactly", prompt)

    def test_condition_identity_does_not_change_identical_trace_prompt(self):
        self.assertIsNotNone(run_pilot, "runner not implemented")
        raw = {"question": "q", "history": [{"name": "A", "content": "tiny"}]}
        self.assertEqual(run_pilot.prepare_input(raw, None)[0],
                         run_pilot.prepare_input(raw, 12000)[0])

    def test_output_schema_types_are_checked_before_scoring(self):
        self.assertIsNotNone(run_pilot, "runner not implemented")
        good = {"agent": None, "step": None, "evidence_steps": [],
                "reason": "insufficient", "repair_hint": "collect evidence"}
        self.assertIsNone(run_pilot.schema_error(good))
        self.assertIsNotNone(run_pilot.schema_error({**good, "reason": 5}))
        self.assertIsNotNone(run_pilot.schema_error({**good, "step": True}))
        self.assertIsNotNone(run_pilot.schema_error({**good, "extra": "field"}))


if __name__ == "__main__":
    unittest.main()
