import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import runtime
except ImportError:
    runtime = None


class RuntimeTests(unittest.TestCase):
    def test_external_tools_are_detected_and_usage_comes_from_completed_turn(self):
        self.assertIsNotNone(runtime, "pilot runtime not implemented")
        summary = runtime.summarize_events([
            {"type": "thread.started", "thread_id": "example"},
            {"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
            {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 30}},
        ])
        self.assertEqual(summary["tool_item_types"], ["command_execution"])
        self.assertEqual(summary["usage"], {"input_tokens": 100, "cached_input_tokens": 20, "output_tokens": 30})
        self.assertTrue(summary["completed"])

    def test_clean_response_without_usage_is_not_claimed_complete(self):
        self.assertIsNotNone(runtime, "pilot runtime not implemented")
        summary = runtime.summarize_events([
            {"type": "item.completed", "item": {"type": "agent_message", "text": "{}"}},
            {"type": "turn.failed", "error": {"message": "temporary failure"}},
        ])
        self.assertFalse(summary["completed"])
        self.assertEqual(summary["failures"], ["temporary failure"])

    def test_run_command_disables_retrieval_and_context_reuse(self):
        self.assertIsNotNone(runtime, "pilot runtime not implemented")
        command = runtime.build_command(Path("/tmp/empty"), Path("/tmp/schema.json"), Path("/tmp/result.json"), Path("/tmp/instructions.md"))
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ephemeral", command)
        self.assertIn('web_search="disabled"', command)
        self.assertIn("features.shell_tool=false", command)
        self.assertIn("memories.use_memories=false", command)
        self.assertIn("project_doc_max_bytes=0", command)
        self.assertEqual(command[command.index("--model") + 1], "gpt-6-astra")

    def test_configuration_warning_is_not_a_tool_call(self):
        summary = runtime.summarize_events([
            {"type": "item.completed", "item": {"type": "error", "message": "ignored setting"}},
            {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}},
        ])
        self.assertEqual(summary["tool_item_types"], [])
        self.assertEqual(summary["warnings"], ["ignored setting"])


if __name__ == "__main__":
    unittest.main()
