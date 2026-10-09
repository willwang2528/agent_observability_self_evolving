"""Score frozen pilot jobs without model calls or source-data modifications.

Every planned job remains in accuracy denominators. Missing, invalid, failed,
or tool-contaminated jobs receive zero; valid abstentions also receive zero.
Cached input tokens are a subset of input tokens, not an additional token cost.
Repair hints remain proposals and are never evaluated as executed improvements.
"""

import argparse
import csv
import json
from pathlib import Path
import statistics

from pilot_core import score_prediction, validate_prediction
from run_pilot import schema_error


SCORES = ("who", "when", "joint", "when_pm1", "joint_pm1", "evidence_valid")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")


def _json(path):
    return json.loads(path.read_text())


def _usage(value):
    value = value if isinstance(value, dict) else {}
    result = {k: max(0, int(value.get(k, 0))) for k in TOKENS[:-1]}
    result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


def _costs(rows):
    observed = [r for r in rows if r["result_present"]]
    return {
        "final_tokens": {k: sum(r[k] for r in rows) for k in TOKENS},
        "all_attempt_tokens": {k: sum(r["all_attempt_" + k] for r in rows) for k in TOKENS},
        "attempts": sum(r["attempt_count"] for r in rows),
        "final_elapsed_seconds": round(sum(r["elapsed_seconds"] for r in rows), 3),
        "all_attempt_elapsed_seconds": round(sum(r["all_attempt_elapsed_seconds"] for r in rows), 3),
        "mean_final_elapsed_seconds_over_observed": (
            round(statistics.mean(r["elapsed_seconds"] for r in observed), 3) if observed else None),
        "median_final_elapsed_seconds_over_observed": (
            round(statistics.median(r["elapsed_seconds"] for r in observed), 3) if observed else None),
        "observed_jobs": len(observed),
    }


def _aggregate(rows):
    n = len(rows)
    counts = {key: sum(r[key] is True if key == "evidence_valid" else r[key] for r in rows)
              for key in SCORES}
    return {"n": n, "results_present": sum(r["result_present"] for r in rows),
            "transport_completed": sum(r["transport_completed"] for r in rows),
            "usable": sum(r["usable"] for r in rows), "valid": sum(r["valid"] for r in rows),
            "abstained": sum(r["abstained"] for r in rows),
            "missing": sum(r["status"] == "missing_result" for r in rows),
            "tool_contaminated": sum(r["tool_contaminated"] for r in rows),
            "invalid": sum(r["status"] in {"invalid_prediction", "invalid_result", "input_mismatch", "unusable_result"}
                           for r in rows),
            "incomplete": sum(r["status"] == "incomplete" for r in rows),
            "counts": counts, "rates": {key: count / n if n else None for key, count in counts.items()},
            "costs": _costs(rows)}


def _by_condition(rows, conditions):
    return {condition: _aggregate([r for r in rows if r["condition"] == condition]) for condition in conditions}


def _row(root, job, gold, case_group):
    directory = root / "results/runs" / job["job_id"]
    result_path = directory / "result.json"
    result = None
    audit_errors = []
    if result_path.exists():
        try:
            result = _json(result_path)
            if not isinstance(result, dict):
                raise ValueError("result must be a JSON object")
        except (OSError, ValueError) as exc:
            result = None
            audit_errors.append(str(exc))
    attempts = []
    for path in sorted(directory.glob("attempt_*/metadata.json")):
        try:
            attempt = _json(path)
            if not isinstance(attempt, dict):
                raise ValueError("attempt metadata must be a JSON object")
            attempts.append(attempt)
        except (OSError, ValueError) as exc:
            audit_errors.append(f"{path.parent.name}: {exc}")
    result = result or {}
    contaminated = bool(result.get("tool_item_types")) or any(a.get("tool_item_types") for a in attempts)
    final_usage = _usage(result.get("usage"))
    if attempts:
        all_usage = {key: sum(_usage(a.get("usage"))[key] for a in attempts) for key in TOKENS}
        all_elapsed = sum(float(a.get("elapsed_seconds", 0)) for a in attempts)
        attempt_count = len(attempts)
    else:
        all_usage = _usage(result.get("all_attempt_usage", result.get("usage")))
        all_elapsed = float(result.get("all_attempt_elapsed_seconds", result.get("elapsed_seconds", 0)))
        attempt_count = int(result.get("attempt_count", 0))
    if attempts and result and result.get("attempt_count") != len(attempts):
        audit_errors.append("attempt metadata count differs from result attempt_count")
    transport = bool(result.get("transport_ok") and result.get("completed"))
    scores = {"valid": False, "abstained": False, "who": 0, "when": 0, "joint": 0,
              "when_pm1": 0, "joint_pm1": 0, "evidence_valid": False}
    # Dataset errors must surface even for jobs with no result; never repair labels.
    validate_prediction(gold, job["known_agent_names"], total_steps=job["total_steps"])
    pred = result.get("prediction")
    error = ""
    if not result_path.exists():
        status = "missing_result"
    elif audit_errors:
        status, error = "invalid_result", "; ".join(audit_errors)
    elif contaminated:
        status, error = "tool_contaminated", "tool activity in at least one attempt"
    elif any(result.get(key) != job[key] for key in ("job_id", "case_id", "condition", "prompt_sha256")):
        status, error = "input_mismatch", "result identity or prompt hash differs from frozen plan"
    elif not transport:
        status, error = "incomplete", "transport did not complete successfully"
    elif result.get("prediction_error") is not None or schema_error(pred) is not None:
        status, error = "invalid_prediction", str(result.get("prediction_error") or schema_error(pred))
    elif not result.get("usable"):
        status, error = "unusable_result", "runner marked result unusable"
    else:
        scores = score_prediction(pred, gold, job["known_agent_names"],
                                  job["included_steps"], job["total_steps"])
        if scores["valid"]:
            status = "abstained" if scores["abstained"] else "scored"
        else:
            status, error = "invalid_prediction", scores.get("error", "invalid prediction")
    pred = pred if isinstance(pred, dict) else {}
    return {"job_id": job["job_id"], "case_id": job["case_id"], "condition": job["condition"],
            "stratum": job["stratum"], "length_tertile": job.get("length_tertile", ""),
            "case_group": case_group, "total_steps": job["total_steps"],
            "included_step_count": len(job["included_steps"]), "omitted_step_count": len(job["omitted_steps"]),
            "included_steps": json.dumps(job["included_steps"]),
            "omitted_steps": json.dumps(job["omitted_steps"]),
            "trace_chars": job["trace_stats"]["rendered_chars"],
            "full_trace_chars": job["trace_stats"]["full_chars"], "prompt_chars": job.get("prompt_chars", 0),
            "gold_agent": gold["agent"], "gold_step": gold["step"],
            "gold_step_included": gold["step"] in job["included_steps"],
            "predicted_agent": pred.get("agent"), "predicted_step": pred.get("step"),
            "evidence_steps": json.dumps(pred.get("evidence_steps")),
            "reason": pred.get("reason", ""), "repair_hint_proposal": pred.get("repair_hint", ""),
            "status": status, "error": error, "result_present": result_path.exists(),
            "transport_completed": transport, "tool_contaminated": bool(contaminated),
            "usable": scores["valid"], **{key: scores[key] for key in ("valid", "abstained") + SCORES},
            **final_usage, **{"all_attempt_" + key: value for key, value in all_usage.items()},
            "attempt_count": attempt_count, "elapsed_seconds": float(result.get("elapsed_seconds", 0)),
            "all_attempt_elapsed_seconds": all_elapsed}


def _paired(rows, budget_condition):
    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], {})[row["condition"]] = row
    details = []
    for case_id, conditions in sorted(by_case.items()):
        full, budget = conditions["full"], conditions[budget_condition]
        details.append({"case_id": case_id, "case_group": full["case_group"],
                        "full_joint": full["joint"], "budget_joint": budget["joint"],
                        "full_usable": full["usable"], "budget_usable": budget["usable"],
                        "gold_step_included_budget": budget["gold_step_included"],
                        "full_input_tokens": full["input_tokens"], "budget_input_tokens": budget["input_tokens"],
                        "full_trace_chars": full["trace_chars"], "budget_trace_chars": budget["trace_chars"]})

    def aggregate(pairs):
        n = len(pairs)
        full_correct = sum(p["full_joint"] for p in pairs)
        budget_correct = sum(p["budget_joint"] for p in pairs)
        both_observed = [p for p in pairs if p["full_input_tokens"] > 0 and p["budget_input_tokens"] > 0]
        input_full = sum(p["full_input_tokens"] for p in both_observed)
        input_budget = sum(p["budget_input_tokens"] for p in both_observed)
        trace_full = sum(p["full_trace_chars"] for p in pairs)
        trace_budget = sum(p["budget_trace_chars"] for p in pairs)
        return {"n": n, "both_usable": sum(p["full_usable"] and p["budget_usable"] for p in pairs),
                "joint_outcomes": {
                    "both_correct": sum(p["full_joint"] == 1 and p["budget_joint"] == 1 for p in pairs),
                    "full_only": sum(p["full_joint"] == 1 and p["budget_joint"] == 0 for p in pairs),
                    "budget_only": sum(p["full_joint"] == 0 and p["budget_joint"] == 1 for p in pairs),
                    "both_wrong": sum(p["full_joint"] == 0 and p["budget_joint"] == 0 for p in pairs)},
                "full_joint_rate": full_correct / n if n else None,
                "budget_joint_rate": budget_correct / n if n else None,
                "joint_rate_delta_budget_minus_full": (budget_correct - full_correct) / n if n else None,
                "trace_character_reduction_fraction": 1 - trace_budget / trace_full if trace_full else None,
                "both_token_observed_pairs": len(both_observed),
                "input_token_reduction_fraction_over_both_observed": 1 - input_budget / input_full if input_full else None,
                "cases": pairs}

    return {"all": aggregate(details),
            "reduced": aggregate([p for p in details if p["case_group"] == "reduced"]),
            "no_op": aggregate([p for p in details if p["case_group"] == "no_op"])}


def score_directory(root):
    """Read plan, gold and result/attempt JSON; return metrics and flat CSV rows.

    No file is modified. Exactly two planned conditions (full and one budgeted)
    are required per case. The frozen plan, rather than completed results, defines
    all denominators and whether a case is reduced or a no-op control.
    """
    root = Path(root)
    plan, gold = _json(root / "results/plan.json"), _json(root / "data/gold.json")
    jobs = plan["jobs"]
    conditions = sorted({job["condition"] for job in jobs}, key=lambda x: (x != "full", x))
    if len(conditions) != 2 or conditions[0] != "full":
        raise ValueError("plan requires full and exactly one budgeted condition")
    budget = conditions[1]
    by_case = {}
    for job in jobs:
        case_jobs = by_case.setdefault(job["case_id"], {})
        if job["condition"] in case_jobs:
            raise ValueError("duplicate planned case/condition")
        case_jobs[job["condition"]] = job
    if any(set(case_jobs) != set(conditions) for case_jobs in by_case.values()):
        raise ValueError("each planned case must have both conditions")
    case_groups = {case_id: "reduced" if case_jobs[budget]["omitted_steps"] else "no_op"
                   for case_id, case_jobs in by_case.items()}
    rows = [_row(root, job, gold[job["case_id"]], case_groups[job["case_id"]]) for job in jobs]
    groups = {"all": _by_condition(rows, conditions),
              "reduced": _by_condition([r for r in rows if r["case_group"] == "reduced"], conditions),
              "no_op": _by_condition([r for r in rows if r["case_group"] == "no_op"], conditions),
              "stratum": {s: _by_condition([r for r in rows if r["stratum"] == s], conditions)
                          for s in sorted({r["stratum"] for r in rows})},
              "gold_step_included": {str(value).lower(): _by_condition(
                  [r for r in rows if r["gold_step_included"] == value], conditions) for value in (True, False)}}
    metrics = {"planned_jobs": len(jobs), "planned_cases": len(by_case), "conditions": conditions,
               "model": plan.get("model"), "reasoning_effort": plan.get("reasoning_effort"),
               "source_commit": plan.get("source_commit"), "groups": groups,
               "costs": _costs(rows), "pairs": _paired(rows, budget),
               "notes": ["All accuracy denominators include every planned job in the group.",
                         "Any attempt with tool activity invalidates the entire job; cost is retained.",
                         "Cached input tokens are included in input_tokens; total=input+output.",
                         "Missing final results score zero; available attempt costs are retained.",
                         "Repair hints are proposals; no repair or self-evolution efficacy is evaluated.",
                         "Paired input reductions use pairs with token observations in both conditions.",
                         "One run per condition; no significance or variance estimate is claimed."]}
    return metrics, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    metrics, rows = score_directory(args.root)
    output = args.root / "results"
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
    with (output / "raw_rows.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"planned_jobs": metrics["planned_jobs"],
                      "usable": sum(r["usable"] for r in rows),
                      "metrics": str(output / "metrics.json"), "rows": str(output / "raw_rows.csv")}))


if __name__ == "__main__":
    main()
