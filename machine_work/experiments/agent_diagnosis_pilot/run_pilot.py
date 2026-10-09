"""Prepare frozen answer-free inputs and run independent real-model diagnoses.

No gold file is read by this runner. Evaluation is a separate, post-run step.
All attempts and model stream events are retained, including transport failures.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import time
from datetime import datetime, timezone

from pilot_core import sanitize_case, render_trace, validate_prediction
from runtime import build_command, summarize_events, CODEX_BINARY, MODEL, REASONING_EFFORT

ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def prepare_input(raw, budget):
    case = sanitize_case(raw)
    trace = render_trace(case, budget)
    prompt = (
        "Diagnose the decisive error that caused this recorded multi-agent task to fail.\n"
        "Select the responsible agent and one original zero-based step. Distinguish an error "
        "from downstream symptoms; do not simply select the final unsuccessful message.\n"
        "Use only the recorded evidence. Missing middle steps are explicitly marked. "
        "If evidence is insufficient, set both agent and step to null.\n"
        "TASK\n" + case["question"] + "\n\nRECORDED AGENT INSTRUCTIONS\n" +
        (case["system_prompt"] or "(not provided)") +
        "\n\nKNOWN AGENT IDENTITIES\n" + json.dumps(case["known_agent_names"], ensure_ascii=False) +
        "\n\n" + trace["text"] +
        "\n\nReturn the required JSON: agent, step, evidence_steps, reason, repair_hint. "
        "Cite only visible original step IDs in evidence_steps. "
        "The repair_hint is a proposed correction, not a claim that a repair was executed."
    )
    return prompt, {"included_steps": trace["included_steps"],
                    "omitted_steps": trace["omitted_steps"], "trace_stats": trace["stats"],
                    "known_agent_names": case["known_agent_names"],
                    "prompt_chars": len(prompt), "prompt_sha256": digest(prompt.encode()),
                    "total_steps": len(case["steps"])}


def schema_error(pred):
    fields = {"agent", "step", "evidence_steps", "reason", "repair_hint"}
    if not isinstance(pred, dict) or set(pred) != fields:
        return "response does not have exactly the required fields"
    if pred["agent"] is not None and not isinstance(pred["agent"], str):
        return "agent must be a string or null"
    if pred["step"] is not None and type(pred["step"]) is not int:
        return "step must be an integer or null"
    if not isinstance(pred["evidence_steps"], list) or any(type(s) is not int for s in pred["evidence_steps"]):
        return "evidence_steps must be a list of integers"
    if not isinstance(pred["reason"], str) or not isinstance(pred["repair_hint"], str):
        return "reason and repair_hint must be strings"
    return None


def prepare_plan():
    """Freeze job order and prompts before requesting any benchmark predictions."""
    manifest = json.loads((ROOT / "data/selected_manifest.json").read_text())
    protocol = json.loads((ROOT / "protocol.json").read_text())
    hashes = {name: digest((ROOT / name).read_bytes()) for name in
              ["protocol.json", "instructions.md", "prediction.schema.json", "pilot_core.py", "runtime.py", "run_pilot.py"]}
    jobs = []
    for item in manifest["cases"]:
        source = ROOT / item["source_path"]
        if digest(source.read_bytes()) != item["sha256"]:
            raise ValueError("source snapshot checksum mismatch: " + item["case_id"])
        raw = json.loads(source.read_text())
        for condition in protocol["conditions"]:
            budget = None if condition == "full" else protocol["character_budget"]
            prompt, info = prepare_input(raw, budget)
            job_id = item["case_id"] + "__" + condition
            directory = ROOT / "results/runs" / job_id
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "prompt.txt").write_text(prompt)
            info.update({"job_id": job_id, "case_id": item["case_id"], "condition": condition,
                         "stratum": item["stratum"], "length_tertile": item["length_tertile"],
                         "source_sha256": item["sha256"]})
            save_json(directory / "input_metadata.json", info)
            jobs.append(info)
    random.Random(20261009).shuffle(jobs)
    plan = {"created_utc": datetime.now(timezone.utc).isoformat(), "jobs": jobs,
            "source_commit": manifest["source_commit"], "seed": 20261009,
            "model": MODEL, "reasoning_effort": REASONING_EFFORT,
            "sampling_temperature": "provider default; not overridden", "hashes": hashes,
            "ground_truth_loaded_by_runner": False, "planned_calls": len(jobs),
            "codex_version": subprocess.check_output([CODEX_BINARY, "--version"], text=True).strip()}
    plan_path = ROOT / "results/plan.json"
    if plan_path.exists():
        existing = json.loads(plan_path.read_text())
        if existing["hashes"] != hashes or existing["jobs"] != jobs:
            raise ValueError("frozen plan differs; do not overwrite after predictions")
        return existing
    save_json(plan_path, plan)
    return plan


def isolated_env():
    # Existing Codex login remains available. No API key is read or newly stored.
    return {k: v for k, v in os.environ.items()
            if not any(s in k.upper() for s in ("API_KEY", "SECRET", "ACCESS_TOKEN"))
            and (not k.startswith("CODEX_") or k == "CODEX_HOME")}


def run_attempt(job, index, timeout):
    directory = ROOT / "results/runs" / job["job_id"] / ("attempt_" + str(index))
    directory.mkdir(parents=True, exist_ok=True)
    response = directory / "response.json"
    started = datetime.now(timezone.utc).isoformat()
    tick = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="diagnosis-pilot-model-", dir="/private/tmp") as cwd:
        command = build_command(Path(cwd), ROOT / "prediction.schema.json", response, ROOT / "instructions.md")
        save_json(directory / "command.json", command)
        timed_out = False
        with (directory / "events.jsonl").open("w") as out, (directory / "stderr.log").open("w") as err:
            try:
                proc = subprocess.run(command, input=(directory.parent / "prompt.txt").read_text(),
                                      text=True, stdout=out, stderr=err, env=isolated_env(), timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = None
        elapsed = time.monotonic() - tick
    events = []
    malformed_events = 0
    for line in (directory / "events.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            malformed_events += 1
    summary = summarize_events(events)
    error = None
    pred = None
    try:
        pred = json.loads(response.read_text())
        error = schema_error(pred)
        if error is None:
            validated = validate_prediction(pred, job["known_agent_names"], job["included_steps"], job["total_steps"])
    except (OSError, ValueError) as exc:
        error = str(exc)
    transport_ok = (exit_code == 0 and summary["completed"] and not timed_out)
    result = {**summary, "started_utc": started, "elapsed_seconds": round(elapsed, 3),
              "exit_code": exit_code, "timeout": timed_out, "malformed_event_lines": malformed_events,
              "prediction": pred, "prediction_error": error,
              "abstained": bool(error is None and validated["abstained"]),
              "transport_ok": transport_ok,
              "usable": bool(transport_ok and error is None and not summary["tool_item_types"]),
              "attempt": index, "directory": str(directory.relative_to(ROOT))}
    save_json(directory / "metadata.json", result)
    return result


def run_job(job, timeout):
    directory = ROOT / "results/runs" / job["job_id"]
    result_path = directory / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text())
        if result["prompt_sha256"] != job["prompt_sha256"]:
            raise ValueError("cannot reuse a result from a different input")
        print(json.dumps({"reused": job["job_id"], "usable": result["usable"]}), flush=True)
        return result
    attempts = []
    for index in (1, 2):
        attempt = run_attempt(job, index, timeout)
        attempts.append(attempt)
        # Only retry transport failure. Never retry an incorrect diagnosis or an abstention.
        if attempt["transport_ok"]:
            break
    final = {**attempts[-1], **{k: job[k] for k in ("job_id", "case_id", "condition", "prompt_sha256")},
             "attempt_count": len(attempts),
             "all_attempt_elapsed_seconds": round(sum(x["elapsed_seconds"] for x in attempts), 3),
             "all_attempt_usage": {k: sum(x["usage"][k] for x in attempts) for k in attempts[-1]["usage"]}}
    save_json(result_path, final)
    print(json.dumps({"finished": job["job_id"], "usable": final["usable"],
                      "elapsed_seconds": final["elapsed_seconds"], "usage": final["usage"],
                      "error": final["prediction_error"]}), flush=True)
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="perform real model calls")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    plan = prepare_plan()
    print(json.dumps({"planned_calls": len(plan["jobs"]), "model": MODEL,
                      "reasoning_effort": REASONING_EFFORT, "source_commit": plan["source_commit"]}), flush=True)
    if not args.run:
        return
    tick = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda job: run_job(job, args.timeout), plan["jobs"]))
    save_json(ROOT / "results/execution_summary.json", {
        "planned": len(plan["jobs"]), "completed": sum(r["transport_ok"] for r in results),
        "usable": sum(r["usable"] for r in results), "wall_seconds": round(time.monotonic() - tick, 3),
        "workers": args.workers, "timeout_seconds": args.timeout,
        "attempts": sum(r["attempt_count"] for r in results),
        "tool_contaminated": sum(bool(r["tool_item_types"]) for r in results),
        "tokens": {k: sum(r["all_attempt_usage"][k] for r in results) for k in results[0]["usage"]}})


if __name__ == "__main__":
    main()
