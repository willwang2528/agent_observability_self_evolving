"""Leakage, numbering and scorer checks; no model invocation is used."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        path = HERE / 'protocol.py'
        self.assertTrue(path.exists(), 'protocol.py must implement the benchmark boundary')
        spec = importlib.util.spec_from_file_location('protocol', path)
        self.p = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.p)
        self.official = self.p.load_official()
        self.raw_path = self.official.raw_path
        self.gold_path = self.official.gold_path
        self.raw = json.loads(self.raw_path.read_text())

    def test_hidden_gold_and_task_instruction_mutations_cannot_change_input(self):
        # Catches accidentally serializing raw wrapper/reference fields into prompts.
        first = copy.deepcopy(self.raw[:1])
        modified = copy.deepcopy(first)
        modified[0]['info']['task']['instruction'] = 'PRIVATE_TASK_INSTRUCTION_SENTINEL'
        modified[0]['info']['task']['actions'] = [{'name': 'PRIVATE_REFERENCE_ACTION'}]
        modified[0]['info']['task']['outputs'] = ['PRIVATE_REFERENCE_OUTPUT']
        modified[0]['reward'] = 1.0
        modified[0]['records'] = ['PRIVATE_RECORDS']
        modified[0]['diagnostic_gold'] = {'root_cause': 'PRIVATE_DIAGNOSTIC_GOLD'}
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.json', Path(tmp) / 'b.json'
            a.write_text(json.dumps(first)); b.write_text(json.dumps(modified))
            self.assertEqual(self.p.build_inputs(a), self.p.build_inputs(b))
            self.assertNotIn('PRIVATE_', self.p.build_inputs(b)[0]['user_prompt'])

    def test_full_conversation_policy_and_tool_evidence_preserved_with_one_based_index(self):
        # Catches dropped/truncated messages or a zero-based numbering shift.
        rows = self.p.build_inputs(self.raw_path)
        self.assertEqual(len(rows), 29)
        self.assertEqual(len({r['task_id'] for r in rows}), 29)
        by_id = {str(r['task_id']): r for r in self.raw}
        for row in rows:
            source = by_id[row['task_id']]['traj']
            self.assertEqual([s['index'] for s in row['steps']], list(range(1, len(source) + 1)))
            self.assertEqual(row['steps'][0]['substeps'][0]['role'], 'system')
            self.assertEqual(row['steps'][0]['substeps'][0]['content'], source[0]['content'].strip())
            self.assertEqual(row['user_prompt'], 'Conversation: ' + str(row['steps']))
        first = next(r for r in rows if r['task_id'] == '2')
        self.assertEqual(len(first['steps']), 32)
        self.assertIn('11 available T-shirt options', first['steps'][6]['substeps'][0]['content'])
        longest = next(r for r in rows if r['task_id'] == '20')
        self.assertEqual(len(longest['steps']), 62)

    def test_official_scorer_counts_all_29_cases_with_known_integer_errors(self):
        # Catches false all-success scoring and integer/string containment matching.
        labels = self.official.load_failures_from_json(str(self.gold_path))
        predictions = {str(g.task_id): {'failure_case': g.failure_case.value, 'index': g.step_number,
                                       'reason_for_failure': 'SCORER_FIXTURE_ONLY'} for g in labels}
        predictions['2']['index'] += 1  # Correct category, wrong exact step.
        predictions['3']['failure_case'] = 10  # Correct step, wrong category.
        with tempfile.TemporaryDirectory() as tmp:
            result = self.p.official_score(predictions, Path(tmp) / 'score.json')
        summary = result['summary']
        self.assertEqual(summary['Correct cases'], 28)
        self.assertEqual(summary['Incorrect cases'], 1)
        self.assertEqual(summary['Correct step number predictions'], 28)
        self.assertEqual(summary['Incorrect step number predictions'], 1)
        self.assertEqual(summary['Step accuracy within +-1'], 1.0)
        self.assertAlmostEqual(summary['Overall average distance'], 1/29)
        self.assertEqual(len(result['detailed_results']), 29)

    def test_missing_predictions_cannot_shrink_denominator(self):
        # Catches the upstream skip-on-failure behavior giving misleading accuracy.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'coverage'):
                self.p.official_score({}, Path(tmp) / 'score.json')

    def test_invalid_category_and_step_types_rejected_before_official_scoring(self):
        labels = self.official.load_failures_from_json(str(self.gold_path))
        valid = {str(g.task_id): {'failure_case': g.failure_case.value, 'index': g.step_number}
                 for g in labels}
        with tempfile.TemporaryDirectory() as tmp:
            for field, value in [('index', '7'), ('failure_case', 11),
                                 ('index', True), ('failure_case', False)]:
                bad = copy.deepcopy(valid); bad['2'][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    self.p.official_score(bad, Path(tmp) / 'score.json')

    def test_out_of_range_index_and_no_error_predictions_remain_scored(self):
        # Catches rejecting valid JSON diagnosis failures or shrinking the denominator.
        labels = self.official.load_failures_from_json(str(self.gold_path))
        predictions = {str(g.task_id): {'failure_case': g.failure_case.value, 'index': g.step_number}
                       for g in labels}
        predictions['2'] = {'failure_case': 0, 'index': 999}
        predictions['3']['index'] = 0
        with tempfile.TemporaryDirectory() as tmp:
            result = self.p.official_score(predictions, Path(tmp) / 'score.json')
        summary = result['summary']
        self.assertEqual(len(result['detailed_results']), 29)
        self.assertEqual(summary['Correct cases'], 28)
        self.assertEqual(summary['Incorrect cases'], 1)
        self.assertEqual(summary['Correct step number predictions'], 27)
        self.assertEqual(summary['Incorrect step number predictions'], 2)
        self.assertAlmostEqual(summary['Overall average distance'], 999/29)

    def test_environment_cannot_override_frozen_upstream(self):
        # Catches loading different source when an ambient environment variable changes.
        previous = os.environ.get('AGENTRX_UPSTREAM')
        os.environ['AGENTRX_UPSTREAM'] = '/nonexistent/malicious-upstream'
        try:
            self.assertEqual(self.p.system_prompt(), self.official.get_system_prompt())
        finally:
            if previous is None:
                os.environ.pop('AGENTRX_UPSTREAM', None)
            else:
                os.environ['AGENTRX_UPSTREAM'] = previous

    def test_baseline_builder_uses_frozen_official_prompt_without_examples(self):
        # Catches changing mode to combined or injecting extra evidence implicitly.
        prompt = self.p.system_prompt()
        self.assertIn('ROOT-CAUSE DETECTION ALGORITHM:', prompt)
        self.assertNotIn('   Example:', prompt)
        self.assertNotIn('   Checklist:', prompt)
        self.assertEqual(prompt, self.official.get_system_prompt())
        self.assertEqual(self.official.PROMPT_MODE, 'baseline')


if __name__ == '__main__':
    unittest.main()
