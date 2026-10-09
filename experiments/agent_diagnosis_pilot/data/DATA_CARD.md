# Who&When pilot data snapshot

- Official repository: https://github.com/ag2ai/Agents_Failure_Attribution
- Fixed commit: `f4d2b6da464a826580e59b3a0eae15ea2d642d7c`
- License: MIT, preserved in `upstream/LICENSE`.
- Downloaded archive: 5,421,854 bytes. Archive SHA-256 and all 185 extracted file checksums are in `source_manifest.json`.
- Only the 184 Who&When JSON records and LICENSE were extracted. Official README/evaluation/inference/helper text was read, saved in `source_evidence.json`, and never executed. No upstream package was installed.

## Selection

`selected_manifest.json` contains 12 cases: six Algorithm-Generated and six Hand-Crafted; two from each source-specific rank-based history-length tertile. Length is the sum of original history `content` character counts, independent of failure labels. Ties sort by source filename. A shared `random.Random(20261009)` shuffles the six buckets in Algorithm then Hand-Crafted, short/medium/long order. The first two with globally unseen `question_ID` are retained.

The full dataset has 126 Algorithm and 58 Hand-Crafted records, representing 139 unique task IDs. There are 45 cross-source task overlaps. All 12 pilot IDs are unique. Selection did not exclude any record based on label quality. `prepare_selection.py` deterministically regenerates selection, gold, inventory and audit from the pinned snapshot.

`source_path` is relative to the pilot directory. `gold.json` is separate and contains diagnosis labels only for selected cases. Model prompts read `question`, optional `system_prompt`, and sanitized `history` (content and agent identifiers). They must not include the top-level task answer (`ground_truth`), diagnosis labels, `labels`, or outcome flags (`is_correct` / `is_corrected`). History sanitization is performed by the harness and must be label independent.

## Schema and scoring boundaries

Algorithm histories identify agents via `name`; Hand-Crafted histories use `role`. Original step indices are zero-based, matching official helper enumeration. All 184 raw `mistake_step` strings parse to integers within history bounds. All history entries have content and an agent identifier.

The official task is to identify the failure-responsible agent and decisive mistake step. Official inference also exposes the task answer to diagnosis. This answer-free pilot is an adaptation, not a strict reproduction of paper scores. Official `evaluate.py` uses substring matching for both agent and step; this can produce false matches (for example, step 1 in 10). Pilot scores should use equality after only documented agent canonicalization.

24 records have a raw failure-agent label differing from the actor at the labeled step. 18 are resolved by mapping `Orchestrator (...)` to `Orchestrator`; six remain identity mismatches requiring semantic interpretation. The selected `algorithm_014` has gold agent `Culinary_Awards_Expert`, step 2, but the logged actor at step 2 is `Computer_terminal`. It is retained because selection was label independent. Do not replace gold with the actor automatically. An agent may be responsible for faulty code whose error appears in a terminal response, so this mismatch does not establish an invalid label. Report the audit flag without automatically excluding or correcting labels when interpreting the 12-case pilot.

No history contains the literal diagnosis annotation keys `mistake_agent`, `mistake_step`, or `mistake_reason`. A simple task-answer substring audit hits 36/184 records, including `algorithm_083`, `handcrafted_012`, and `handcrafted_025` in this pilot. This is not proof of leakage: short numeric answers can occur by chance, and original failed trajectories may legitimately contain a correct answer before later failure. The original data snapshot is preserved. Any model-input sanitization is performed separately by the harness without using diagnosis labels.
