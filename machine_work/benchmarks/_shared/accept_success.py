"""Require real, replayed success on every fixed recovery task before publication."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "machine_work/benchmarks"
NAMES = ("webshop", "tau_bench")
RECORD = BASE / "SUCCESS_ACCEPTANCE.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_success(name, report):
    """Validate the success boundary after the native verifier has replayed evidence."""
    if name not in NAMES or report.get("benchmark") != name:
        raise ValueError("Wrong benchmark identity")
    if report.get("acceptance") != "PASS":
        raise ValueError("Native evidence verification did not pass")
    if report.get("real_model_tasks") != 2 or report.get("successes") != 2:
        raise ValueError("All two fixed tasks must succeed")
    cases = report.get("cases", [])
    if len(cases) != 2 or sorted(c.get("task", -1) for c in cases) != [0, 1]:
        raise ValueError("Fixed task indices 0 and 1 must each appear once")
    if not report.get("selected_attempt"):
        raise ValueError("Missing identity of the complete two-task attempt")
    for case in cases:
        score = case.get("score", {})
        if score.get("reward") != 1.0 or score.get("won") is not True or score.get("done") is not True:
            raise ValueError("A selected task is incomplete or below full reward")
        if case.get("official_replay") != "PASS":
            raise ValueError("Every task needs successful official replay")
        if case.get("actor", {}).get("calls", 0) < 1:
            raise ValueError("Missing actual model actions")


def write_record(record):
    temporary = RECORD.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(RECORD)


def main():
    record = {
        "acceptance": "RUNNING", "publication_allowed": False,
        "scope": "WebShop and historical tau-bench fixed development tasks [0,1], all four full successes required",
        "human_audit": "pending", "model_calls_in_this_acceptance": 0,
        "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "benchmarks": {}, "checks": [],
    }
    write_record(record)
    try:
        env = os.environ.copy()
        env.pop("PYTHONOPTIMIZE", None)  # Native verifiers use assertions; keep them enabled.
        env["PYTHONPYCACHEPREFIX"] = "/tmp/benchmark-success-pycache"
        if sys.platform == "darwin" and "JAVA_HOME" not in env:
            env["JAVA_HOME"] = subprocess.check_output(["/usr/libexec/java_home"], text=True).strip()
        python = ROOT / ".benchmark_cache/venv/bin/python"
        commands = [
            [python, "-m", "unittest", "discover", "-s", BASE / "_shared", "-p", "test_*.py", "-v"],
            [python, "-m", "unittest", "discover", "-s", BASE / "webshop/runner", "-p", "test_*.py", "-v"],
            [python, "-m", "unittest", "discover", "-s", BASE / "who_when/pilot_20261009/tests", "-v"],
        ]
        for name in NAMES:
            folder = BASE / name / "recovery_20261011"
            if list(folder.glob("test_*.py")):
                commands.append([python, "-m", "unittest", "discover", "-s", folder, "-p", "test_*.py", "-v"])
            commands.append([python, folder / "verify.py"])
        logs = BASE / "validation/recovery_20261011"
        logs.mkdir(parents=True, exist_ok=True)
        test_count = 0
        for index, command in enumerate(commands):
            command = list(map(str, command))
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
            log = logs / f"check_{index:02d}.log"
            log.write_text(result.stdout + result.stderr)
            record["checks"].append({"command": command, "returncode": result.returncode,
                                     "log": str(log.relative_to(ROOT)), "sha256": sha(log)})
            if result.returncode:
                raise RuntimeError(f"Verification failed: {log.relative_to(ROOT)}")
            if "unittest" in command:
                count = re.search(r"^Ran (\d+) tests? in ", result.stdout + result.stderr, re.MULTILINE)
                if count is None:
                    raise RuntimeError("Missing test count")
                test_count += int(count.group(1))
        for name in NAMES:
            path = BASE / name / "recovery_20261011/acceptance.json"
            report = json.loads(path.read_text())
            validate_success(name, report)
            record["benchmarks"][name] = {
                "acceptance": "PASS", "report": str(path.relative_to(ROOT)), "sha256": sha(path),
                "tasks": [0, 1], "successes": 2, "selected_attempt": report["selected_attempt"],
                "rewards": [c["score"]["reward"] for c in report["cases"]],
            }
        record.update(acceptance="PASS", publication_allowed=True, unit_tests=test_count,
                      verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      verifier_sha256=sha(Path(__file__)))
        write_record(record)
        print(f"Strict success acceptance PASS: WebShop 2/2; tau-bench 2/2; {test_count} tests.")
    except Exception as exc:
        record.update(acceptance="FAIL", publication_allowed=False, error=str(exc))
        write_record(record)
        raise


if __name__ == "__main__":
    main()
