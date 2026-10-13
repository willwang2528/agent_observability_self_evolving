# AgentRx independent audit

Status: **PASS_EXECUTION_AND_OFFICIAL_SCORING**

All 29 tau traces in the pinned public GitHub snapshot; not the latest-paper 39 tau or entire 170-case collection.

Official baseline prompt and IR via Codex model transport; no invariant pipeline or self-evolution result.

Independent audit performs no model calls and does not trust project PASS summaries. Human audit remains pending.

Static checks: PASS; 29 complete trajectories, 1,064 original steps; official prompt, IR, immutable hashes and isolation controls verified.

Category: 9/29; exact step: 9/29; supplemental joint: 7/29.
MAE: 6.310344827586207; normalized MAE: 0.17255030938523813.
Real diagnostic attempts: 29; valid cases: 29/29; tool contamination: none.

Out-of-range diagnostic indices retained as errors: 1. Valid calls/JSON responses do not imply a valid localized step for every case.

Execution/scoring completion is reported independently from prediction correctness. Wrong predictions remain in the 29-case denominator.

Runtime evidence establishes the configured gpt-6-astra/xhigh request; provider-internal identity is not independently attested.
Preparation reads gold bytes only to record their checksum; gold labels are used for offline scoring and are absent from diagnostic inputs.
Category 0 and out-of-range integer indices, if emitted, are retained as wrong predictions according to the frozen protocol; they are not grounds for accuracy-conditioned retries.
