# AgentRx tau 29-case diagnosis acceptance plan

Prepared by the independent diagnosis_harness_audit subagent before the new run. This is a test plan, not a completed-run acceptance claim. No model calls were made while preparing it.

## Verified upstream baseline

- Source: `/tmp/agentrx_source_20261013`, commit `7a18c79708e7671be15124460f4f7296107c2a55`.
- Raw dataset: `data/tau_retail/tau_dataset_failed.json`, SHA-256 `17f8b3356d1124274cc7ed0215b5ff696970073dbed57394c60e775d5f85d717`.
- Diagnostic labels: `data/ground_truth/tau_ground_truth.json`, 29 entries. Do not substitute `tau_retail.json`, which has only 24 entries.
- Fixed task IDs: `2,3,4,12,20,21,28,31,32,34,38,39,41,47,55,59,63,71,72,74,79,80,82,87,91,98,99,104,105`.
- Direct execution of the unmodified official `load_trajectories` and `tau_bench_ir` produces 29 trajectories, 1,064 total steps, lengths 20–62. Every trajectory starts with its original system policy. Every trajectory has consecutive **one-based** indices.
- The official `judge_trajectories` passes only `item['steps']` to `judge_response`. The latter constructs exactly `f'Conversation: {trajectory}'`, using Python representation, not JSON serialization.
- The official diagnostic system prompt is `get_system_prompt()` after `PROMPT_MODE='baseline'`, with no invariant context and no failure-only prompt. Baseline excludes demonstrations and taxonomy checklists, but retains the official five output fields.
- `ground_truth` and `outputs` arguments in `judge_response` are unused; top-level IR `instruction` is also not sent. The inherited template mentions expected actions/outputs, but actual official invocation does not append them. Preserve and document actual behavior rather than inventing additional input.
- This run uses the official baseline prompt and normalization with a different model transport. It does not execute AgentRx invariant synthesis/checking or reproduce its full proposed method.

## Tests before model execution

1. **Source pinning.** Hash all vendored source/data files against the pinned checkout. Require the raw source, IR implementation, judge implementation and diagnostic-label file to match exactly.
2. **Coverage.** Assert exactly the 29 task IDs above, no duplicates and no omissions; compare both raw and gold ID sets before starting, without using category or localization labels for selection/order.
3. **Root-cause resolution.** Every `root_cause.failure_id` resolves to exactly one entry in that case's failures list. Its annotated step exists in the corresponding source trace. Do not silently fall back to the first/last failure.
4. **Official IR equivalence.** Independently import the pinned `trajectory_ir.py` and compare all generated IR dictionaries with the run's stored IR, including content, roles, original tool-call payloads, system policy and indices.
5. **Complete numbering.** For each case, `indices == list(range(1, len(raw['traj'])+1))`; all original events remain. Check 1,064 total events, including 29 leading system messages. Do not use old Who&When zero-based numbering.
6. **Prompt equivalence.** Compare stored system instructions byte-for-byte with independently generated official baseline prompt. Compare stored user prompt exactly with `'Conversation: ' + str(official_ir['steps'])`.
7. **No diagnostic gold in input.** Mutate every diagnostic root-cause/category/reason/step field to sentinels while keeping raw trajectory fixed; all model inputs and input hashes must remain identical. Gold is consumed only after predictions have been frozen.
8. **No reference-answer injection.** Mutate raw `reward`, `info.task.actions`, `info.task.outputs`, `info.reward_info`, and top-level IR `instruction`; the actual baseline user prompt must remain unchanged. Preserve legitimate occurrences of action names or outputs inside observed trajectory content.
9. **No accidental removal of trace policy.** Change a character inside the original first system message and confirm it changes IR/user input, because the policy is necessary diagnostic evidence, not forbidden ground truth.
10. **Output contract.** Require the five fields `taxonomy_checklist_reasoning`, `reason_for_failure`, `failure_case`, `reason_for_index`, `index`. Numeric values must be real integers, not booleans; category is 1–10, index references a supplied original step. Invalid/missing outputs are recorded as invalid rather than silently normalized into success.
11. **Frozen plan.** Record all task IDs, official prompt, source/data hashes, runner/schema hashes, requested model/reasoning, retry policy, concurrency, timeout and planned denominator before starting. Rerun/resume must reject changed inputs or code without a new run directory.

## Official scoring tests

12. **Load labels using official code.** Independently call pinned `load_failures_from_json`; compare category/step mapping by task ID, not list position. The official alias conversion is authoritative.
13. **Synthetic scoring controls.** Construct `Failure`/`Report` objects and execute official `Report.compute_stats` plus `analysis`: gold=prediction gives category=1, exact-step=1, distance=0; same category/step+1 gives category=1, exact-step=0, tolerance-1=1; wrong category/same step gives category=0, exact-step=1; both wrong gives both=0. These controls are unit tests only and must never be reported as real model success.
14. **Metric identity.** Official `Correct cases` means category correctness, not joint category-and-step correctness. Report category accuracy and exact-step accuracy separately. If joint accuracy is added, label it a local secondary metric and independently recompute it.
15. **Distance denominators.** Official absolute distance is `abs(step_mean - gt_step)`; normalized distance divides by the full IR trajectory length including the policy message. With one prediction, step mean equals predicted index. Verify tolerance counts for ±1 through ±5.
16. **Fixed evaluation denominator.** All 29 scheduled cases remain visible. The official analysis skips reports lacking GT comparisons; therefore acceptance must require exactly 29 successfully constructed scored reports and fail if any scheduled case disappears. An incomplete run may report diagnostics but must not claim full execution or use the reduced denominator as the full-set score.

## Independent final acceptance

17. **Raw execution evidence.** Every attempt has command, exact prompt/instructions/schema, events, stderr, raw response, exit status, time and usage. Independently parse all JSONL lines and reject malformed lines, tool calls or unresolved errors. Require successful `turn.completed`, positive output tokens and final assistant JSON identical to the saved prediction used for scoring.
18. **Isolation.** Inspect commands for the fixed app Codex binary, gpt-6-astra/xhigh, empty temporary cwd, read-only mode, disabled web/tools/skills/memory/plugins and ignored user config. Inspect actual events for tool use, not command flags alone. Gold and the repository are never exposed through the diagnostic prompt or model tools.
19. **No cherry-picking.** Retain all attempts, classify setup/transport failures separately, and only retry according to the precommitted transport policy. Do not retry a well-formed low-scoring prediction merely to obtain a correct label.
20. **Direct official recomputation.** Bypass project PASS summaries. Independently build reports from raw response JSON and execute the pinned official scoring functions; compare the resulting metrics with committed metrics and verify all 29 case identities.
21. **Preservation and scope.** Check old frozen benchmark hashes and `git diff`; old results cannot be overwritten. Human audit remains pending. Mark the new execution/scoring chain complete only after all 29 real calls/official scores are verified; accuracy is reported honestly and need not be 100% to establish a diagnostic benchmark is runnable.
22. **Process record.** Preserve preparation failures and their fixes, source selection, environment/model adaptation, exact commands, execution summary and limitations. Report baseline/model adaptation and lack of self-evolution validation explicitly.

## Known implementation hazards

- Official IR shape validation permits index 0 for other domains; tau-specific completeness must be checked separately.
- Official `Failure` can map invalid integer categories to INCONCLUSIVE. Validate raw model output before constructing this object so malformed output is not silently treated as a valid diagnosis.
- Official `analysis` catches output-writing errors and can skip GT-less cases. Assert output existence, 29-case coverage and metric values after calling it.
- The old common runner fixed action/arguments schema and loses captured stream output on timeout. New diagnosis code must use its own schema and stream logs to files before waiting.
- Source code import must not instantiate Azure/TRAPI clients or issue hidden network requests; scoring verification needs only local official normalization/report functions.
