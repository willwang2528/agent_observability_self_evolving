"""Pure data preparation and strict evaluation for the Who&When pilot.

No function reads files, sends requests, or receives diagnosis labels while
preparing model input. Step IDs always refer to zero-based source-list indices.
"""

from collections.abc import Mapping
import json
import re


def canonical_agent(name):
    """Return a comparison key; strip/casefold and one documented dataset alias.

    Hand-crafted logs display ``Orchestrator (thought)`` or
    ``Orchestrator (-> WebSurfer)`` while labels use ``Orchestrator``. Only that
    exact agent's parenthesized display suffix is removed; no substring matches.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("agent name must be a nonempty string")
    key = name.strip().casefold()
    if re.fullmatch(r"orchestrator(?:\s*\(.*\))?", key):
        return "orchestrator"
    return key


def _text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _nonnegative_integer(value):
    return type(value) is int and value >= 0


def sanitize_case(raw):
    """Allowlist question, system_prompt, and ordered history entry text.

    ``history`` takes precedence over the legacy ``rawhistory`` alias. Entries
    expose only step/name/role/content. Name falls back to role for hand-crafted
    histories. ``known_agent_names`` comes solely from observed entry identities.
    All source annotations, question IDs, and task answers are excluded.
    """
    if not isinstance(raw, Mapping):
        raise ValueError("case must be a mapping")
    history = raw.get("history") if "history" in raw else raw.get("rawhistory")
    if not isinstance(history, list) or not history:
        raise ValueError("history must be a nonempty list")
    steps = []
    names = {}
    for index, entry in enumerate(history):
        if not isinstance(entry, Mapping):
            raise ValueError(f"history entry {index} must be a mapping")
        if "step" in entry and (not _nonnegative_integer(entry["step"]) or entry["step"] != index):
            raise ValueError(f"history entry {index} has conflicting zero-based step number")
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            name = entry.get("role")
        key = canonical_agent(name)
        display_name = "Orchestrator" if key == "orchestrator" else name.strip()
        names.setdefault(key, display_name)
        steps.append({"step": index, "name": name.strip(),
                      "role": _text(entry.get("role")), "content": _text(entry.get("content"))})
    return {"question": _text(raw.get("question")),
            "system_prompt": _text(raw.get("system_prompt")),
            "steps": steps, "known_agent_names": list(names.values())}


def render_trace(case, char_budget=None):
    """Render complete steps with original IDs, optionally within a char budget.

    Question/system_prompt are separate caller context and do not count toward
    this trace-only budget. Budgeted selection alternates complete head and tail
    entries, trying the other end if the preferred entry does not fit. An omitted
    middle range is explicit. No entry content is silently shortened. Stats and
    included/omitted IDs describe the exact text supplied to the model.
    """
    if char_budget is not None and (type(char_budget) is not int or char_budget < 0):
        raise ValueError("char_budget must be a nonnegative integer or None")
    steps = case["steps"]
    if any(type(step.get("step")) is not int or step["step"] != i for i, step in enumerate(steps)):
        raise ValueError("case steps must preserve zero-based source numbering")
    header = "TRACE (zero-based step IDs)"
    blocks = [f"[step {step['step']}] name={step['name']} role={step['role']}\n{step['content']}"
              for step in steps]
    full = "\n".join([header] + blocks)
    head, tail = len(blocks), 0
    truncated = char_budget is not None and len(full) > char_budget

    def assemble(n_head, n_tail):
        middle_end = len(blocks) - n_tail
        marker = f"[... omitted steps {n_head}..{middle_end - 1} ...]"
        return "\n".join([header] + blocks[:n_head] + [marker] + blocks[middle_end:])

    if truncated:
        head = tail = 0
        if len(assemble(head, tail)) > char_budget:
            raise ValueError("char_budget is too small for the omission marker")
        prefer_head = True
        while head + tail < len(blocks):
            candidates = [(head + 1, tail), (head, tail + 1)]
            if not prefer_head:
                candidates.reverse()
            fitting = [(h, t) for h, t in candidates if h + t < len(blocks)
                       and len(assemble(h, t)) <= char_budget]
            if not fitting:
                break
            head, tail = fitting[0]
            prefer_head = not prefer_head
        text = assemble(head, tail)
    else:
        text = full
    included = list(range(head)) + list(range(len(steps) - tail, len(steps)))
    omitted = list(range(head, len(steps) - tail))
    return {"text": text, "included_steps": included, "omitted_steps": omitted,
            "stats": {"total_steps": len(steps), "included_step_count": len(included),
                      "omitted_step_count": len(omitted), "full_chars": len(full),
                      "rendered_chars": len(text), "char_budget": char_budget,
                      "truncated": truncated, "strategy": "head_tail" if truncated else "full"}}


def validate_prediction(pred, known_agent_names, included_steps=None, total_steps=None):
    """Validate agent/step and optional evidence IDs; return canonical identity.

    Raises ValueError for malformed values or an agent not observed in history.
    Explicit ``agent=None, step=None`` is a valid abstention; missing fields and
    half-null diagnoses are invalid. Optional total_steps bounds the error step
    against the full source history, independently of which steps are visible.
    Evidence visibility is reported separately: it does not restrict the inferred
    error step. Missing/empty evidence has validity None/False respectively.
    """
    if not isinstance(pred, Mapping):
        raise ValueError("prediction must be a mapping")
    if total_steps is not None and not _nonnegative_integer(total_steps):
        raise ValueError("total_steps must be a nonnegative integer or None")
    if "agent" not in pred or "step" not in pred:
        raise ValueError("prediction must explicitly contain agent and step")
    evidence = pred.get("evidence_steps")
    if evidence is not None and (not isinstance(evidence, list)
                                 or any(not _nonnegative_integer(s) for s in evidence)):
        raise ValueError("evidence_steps must be a list of nonnegative integers")
    evidence_valid = None if evidence is None else bool(evidence)
    if evidence is not None and included_steps is not None:
        evidence_valid = bool(evidence) and set(evidence).issubset(set(included_steps))
    if pred["agent"] is None and pred["step"] is None:
        return {"agent": None, "step": None, "evidence_steps": evidence,
                "evidence_valid": evidence_valid, "abstained": True}
    known = {canonical_agent(name): name for name in known_agent_names}
    key = canonical_agent(pred["agent"])
    if key not in known:
        raise ValueError("predicted agent is not a known history identity")
    step = pred["step"]
    if not _nonnegative_integer(step):
        raise ValueError("predicted step must be a nonnegative integer, excluding bool")
    if total_steps is not None and step >= total_steps:
        raise ValueError("predicted step is outside the full source history")
    return {"agent": known[key], "step": step, "evidence_steps": evidence,
            "evidence_valid": evidence_valid, "abstained": False}


def score_prediction(pred, gold, known_agent_names, included_steps=None, total_steps=None):
    """Score exact agent and integer step match, with ±1 as a secondary metric.

    Invalid predictions and valid abstentions remain in the denominator and
    receive zero primary and secondary scores. Invalid gold (including null
    diagnosis labels) is a dataset error and raises ValueError.
    Evidence validity is independent of diagnostic accuracy.
    """
    target = validate_prediction(gold, known_agent_names, total_steps=total_steps)
    if target["abstained"]:
        raise ValueError("gold diagnosis cannot abstain")
    scores = {"valid": False, "abstained": False, "who": 0, "when": 0, "joint": 0,
              "when_pm1": 0, "joint_pm1": 0, "evidence_valid": False}
    try:
        prediction = validate_prediction(pred, known_agent_names, included_steps, total_steps)
    except ValueError as exc:
        return {**scores, "error": str(exc)}
    if prediction["abstained"]:
        return {**scores, "valid": True, "abstained": True,
                "evidence_valid": prediction["evidence_valid"]}
    who = int(canonical_agent(prediction["agent"]) == canonical_agent(target["agent"]))
    when = int(prediction["step"] == target["step"])
    near = int(abs(prediction["step"] - target["step"]) <= 1)
    return {**scores, "valid": True, "who": who, "when": when, "joint": who * when,
            "when_pm1": near, "joint_pm1": who * near,
            "evidence_valid": prediction["evidence_valid"]}
