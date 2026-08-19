# Prompt for the paper-writing main agent

Integrate the completed L1 task-conditioned successor experiment using only the machine-generated, checksum-verified artifacts below. Do not rerun, tune, filter, reinterpret, or replace any held-out episode, and do not change the registered risk-transition definition.

1. First verify `results/proofalign_l1_task_conditioned_v4_heldout_handoff_20260819/SHA256SUMS`.
2. Read `results/proofalign_l1_task_conditioned_v4_heldout_handoff_20260819/handoff_report.md`, `results/proofalign_l1_task_conditioned_v4_heldout_handoff_20260819/generated_tables.md`, and `results/proofalign_l1_task_conditioned_v4_heldout_handoff_20260819/summary.json`.
3. Treat the bound held-out analysis and raw ledgers named in the handoff as the sole numerical authority.
4. Report all four arms under clean and attacked conditions, the exact four-channel risk transition, safe task success, interventions, qualified no-dispatch aborts, identity-bound false reject and unsafe allow, channel breakdown, recovery/deadlock, the frozen ALLOW-coverage operating point, latency, and every terminal exception retained by the analysis. Do not invent a continuous risk-coverage curve because this checker has no calibrated confidence score.
5. Clearly distinguish the historical full120 non-pass from this versioned successor; never overwrite or reinterpret historical protocols, checksums, or classifications.
6. Describe the method as trusted phase/robot-part contact contracts plus exact full-link/held-object shadow checks, qualified fresh recovery, and a qualified no-dispatch deadlock when no exact-shadow ALLOW recovery exists. Never describe the abort sentinel as an executed action: the semantic checker rejects it before authorization and the dispatch boundary independently blocks it. LLM templates are non-authoritative proposals rebuilt from trusted BDDL; attacked prompts are invisible to the checker.
7. Do not claim improvement unless the generated statistics support it. Preserve negative or null results verbatim.
8. If the handoff reports zero overlap with the historical fixed 86-unit cohort, state that the fixed-cohort contrast is not estimable; do not substitute the new held-out cohort for it.
9. Make paper edits only in the paper-writing workflow; the experiment branch intentionally contains evidence and handoff artifacts, not manuscript changes.

Return a concise integration summary listing the evidence paths and the exact table values used.
