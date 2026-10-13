"""AgentRx tau-retail official baseline and deterministic scoring boundary.

Only selected AST nodes from pinned upstream files are executed. Their function
bodies are unchanged; Azure/TRAPI/Copilot clients and module-level initialization
are not imported. Inputs reproduce upstream's ``Conversation: str(steps)``:
policy and observed messages are retained; task instructions, reference actions,
reference outputs, reward metadata and diagnosis annotations are not appended.

The upstream template still mentions reference actions despite not supplying
them. We preserve that wording for reproducibility and report this limitation.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
UPSTREAM_REVISION = '7a18c79708e7671be15124460f4f7296107c2a55'


def _first_file(root: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = root / candidate
        if path.is_file():
            return path
    raise FileNotFoundError(f'Missing upstream file under {root}: {candidates}')


def _load_selected(path: Path, names: set[str], namespace: dict) -> None:
    """Execute verbatim AST nodes and safe standard-library imports only."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    safe_modules = {'typing', 'json', 'os', 're', 'time', 'warnings', 'argparse',
                    'traceback', 'enum', 'collections', 'statistics', 'datetime', 'dataclasses'}
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            if all(alias.name.split('.')[0] in safe_modules for alias in node.names):
                selected.append(node)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or '').split('.')[0] in safe_modules:
                selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in names:
                selected.append(node); found.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            assigned = {target.id for target in targets if isinstance(target, ast.Name)}
            if assigned & names:
                selected.append(node); found.update(assigned)
    missing = names - found
    if missing:
        raise ValueError(f'Pinned upstream symbols missing in {path}: {sorted(missing)}')
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, filename=str(path), mode='exec'), namespace)


def load_official(upstream: str | Path | None = None) -> SimpleNamespace:
    """Return selected official functions/classes without initializing providers.

    By default reads ``./upstream`` beside this file; an explicit parameter can
    select a different snapshot. Supports either a complete clone or
    a compact snapshot retaining the upstream relative source paths.
    """
    root = Path(upstream if upstream is not None else HERE / 'upstream').resolve()
    judge_path = _first_file(root, ['agentrx/judge/judge.py', 'judge/judge.py', 'judge.py'])
    ir_path = _first_file(root, ['agentrx/ir/trajectory_ir.py', 'ir/trajectory_ir.py', 'trajectory_ir.py'])
    namespace = {'__name__': 'agentrx_official_selected', '__file__': str(judge_path)}
    _load_selected(ir_path, {
        'Event', 'Trajectory', 'PREFERRED_KEYS', 'ID_KEYS', 'find_first_key',
        'extract_instruction', '_parse_markdown_trajectory', 'load_trajectories',
        'validate_ir', 'tau_bench_ir',
    }, namespace)
    _load_selected(judge_path, {
        'TAXONOMY_DATA', '_TMPL_NO_CONTEXT', '_TMPL_WITH_CONTEXT', '_TMPL_FAILURE',
        '_TMPL_VIOLATIONS_BEFORE', 'EXAMPLES_DIR', 'FEW_SHOT_EXAMPLES',
        'build_taxonomy_text', 'get_system_prompt', 'format_example_for_prompt',
        'ensure_few_shot_examples_loaded', 'load_few_shot_examples',
        'FailureCase', 'Failure', 'Report', 'convert_to_failure_case',
        'load_failures_from_json', 'analysis',
    }, namespace)
    namespace['PROMPT_MODE'] = 'baseline'
    namespace['EXECUTION_MODE'] = 'violations-after'
    namespace['raw_path'] = _first_file(root, [
        'data/tau_retail/tau_dataset_failed.json', 'tau_dataset_failed.json',
    ])
    namespace['gold_path'] = _first_file(root, [
        'data/ground_truth/tau_ground_truth.json', 'tau_ground_truth.json',
    ])
    namespace['upstream_root'] = root
    namespace['judge_path'] = judge_path
    namespace['ir_path'] = ir_path
    namespace['system_prompt'] = namespace['get_system_prompt']
    return SimpleNamespace(**namespace)


def system_prompt(upstream: str | Path | None = None) -> str:
    """Return the unchanged official baseline template and taxonomy."""
    return load_official(upstream).get_system_prompt()


def build_inputs(raw_path: str | Path, upstream: str | Path | None = None) -> list[dict]:
    """Use the official loader/converter, retain every step, omit wrapper metadata."""
    official = load_official(upstream)
    trajectories = official.tau_bench_ir(official.load_trajectories(str(raw_path)))
    rows = []
    seen = set()
    for trajectory in trajectories:
        task_id = str(trajectory['trajectory_id'])
        if task_id in seen:
            raise ValueError(f'Duplicate trajectory id: {task_id}')
        seen.add(task_id)
        steps = trajectory['steps']
        if not steps or [step['index'] for step in steps] != list(range(1, len(steps) + 1)):
            raise ValueError(f'Invalid complete 1-based steps for task {task_id}')
        rows.append({'task_id': task_id, 'steps': steps,
                     'user_prompt': f'Conversation: {steps}'})
    return rows


def official_score(predictions: dict, out_path: str | Path,
                   upstream: str | Path | None = None,
                   raw_path: str | Path | None = None,
                   gold_path: str | Path | None = None) -> dict:
    """Compute upstream Report+analysis, with complete-coverage validation first.

    ``predictions`` must contain one response per gold task, indexed by string id.
    This wrapper rejects missing/extra ids and malformed answers rather than
    allowing upstream's skip-on-error behavior to silently shrink the denominator.
    Integer indices outside the trajectory and category 0 (no error) remain
    predictions and count as errors, without triggering retries. No generative
    judge is invoked during scoring.
    """
    official = load_official(upstream)
    raw_path = Path(raw_path) if raw_path else official.raw_path
    gold_path = Path(gold_path) if gold_path else official.gold_path
    with contextlib.redirect_stdout(io.StringIO()):
        labels = official.load_failures_from_json(str(gold_path))
    inputs = {row['task_id']: row for row in build_inputs(raw_path, upstream)}
    label_ids = [str(label.task_id) for label in labels]
    expected = set(label_ids)
    if len(label_ids) != len(expected) or set(inputs) != expected or set(predictions) != expected:
        raise ValueError(f'Prediction coverage mismatch: expected {len(expected)} unique tasks; '
                         f'missing={sorted(expected - set(predictions))}; '
                         f'extra={sorted(set(predictions) - expected)}')
    reports = []
    for label in labels:
        tid = str(label.task_id)
        response = predictions[tid]
        category = response.get('failure_case')
        index = response.get('index')
        if type(category) is not int or not 0 <= category <= 10:
            raise ValueError(f'Invalid failure_case for task {tid}: {category!r}')
        if type(index) is not int:
            raise ValueError(f'Invalid step index for task {tid}: {index!r}')
        report = official.Report(tid, len(inputs[tid]['steps']))
        report.add_failure(official.Failure(
            task_id=tid, failure_case=category, step_number=index,
            description=response.get('reason_for_failure', ''),
            checklist_reasoning=response.get('taxonomy_checklist_reasoning'),
        ))
        report.compute_stats(label)
        reports.append(report.to_dict())
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Write fresh reports so a pre-existing upstream output cannot override them.
    destination.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    with contextlib.redirect_stdout(io.StringIO()):
        official.analysis(reports, str(destination), model_name='gpt-6-astra', api_version='codex-exec')
    return json.loads(destination.read_text(encoding='utf-8'))
