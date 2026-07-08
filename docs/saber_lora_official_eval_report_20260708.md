# SABER Official LoRA Eval Report: 2026-07-08

## Scope

This report summarizes the completed official SABER LoRA attack-agent evaluation reproduced in `external/SABER`.

The run used the authors' released LoRA attack agents after local merge, loaded the LoRA-derived attack-agent weights, and generated attack records through SABER's official `eval_attack_vla.py` path. It did not train new attack agents and did not use hand-written perturbation records.

Large models, datasets, and caches were kept under `/data0/ldx`. The workspace and experiment documents remain under `/home/ldx/lean-vla`.

## Eval Configuration

```text
SABER repo: external/SABER
victim VLA: openpi_pi05
attack agents:
  task_failure
  action_inflation
  constraint_violation
suites:
  libero_spatial
  libero_object
  libero_goal
  libero_10
task ids: 7-9
episodes per task: 5
total scenarios per objective: 60
seed: 42
VLA GPU: 4
attack GPUs: 2
vLLM GPU memory utilization: 0.45
```

Merged LoRA model directories:

```text
/data0/ldx/saber/outputs/hf_merged_attack_agents/task_failure
/data0/ldx/saber/outputs/hf_merged_attack_agents/action_inflation
/data0/ldx/saber/outputs/hf_merged_attack_agents/constraint_violation
```

Saved attack records:

```text
external/SABER/outputs/agent_output_records_task_failure_hf/task_failure_openpi_pi05.json
external/SABER/outputs/agent_output_records_action_inflation_hf/action_inflation_openpi_pi05.json
external/SABER/outputs/agent_output_records_constraint_violation_hf/constraint_violation_openpi_pi05.json
```

All three JSON files contain 60 `per_episode` records. Each record has the required fields, a changed instruction, and non-empty `tools_used`.

## Aggregate Results

| Objective | Baseline success rate | Attack task execution rate | Attack success rate | Flipped / baseline-success episodes | Avg step ratio | Avg reward | Avg constraint violations |
|---|---:|---:|---:|---:|---:|---:|---:|
| task_failure | 95.00% | 95.00% | 1.75% | 1 / 57 | 1.03 | 0.0117 | 0.00 |
| action_inflation | 93.33% | 90.00% | 8.93% | 5 / 56 | 1.22 | 0.2224 | 0.00 |
| constraint_violation | 93.33% | 50.00% | 50.00% | 28 / 56 | 1.72 | 0.5262 | 665.47 |

Constraint-violation breakdown:

```text
avg collisions: 662.35
avg joint-limit violations: 3.12
avg excessive-force violations: 0.00
```

## Interpretation

The reproduction pipeline is complete, but the attack effectiveness only partially matches the SABER paper and README expectation.

`constraint_violation` is the successful objective in this run. It reached 50% attack success, produced many collision and joint-limit events, and increased the average step count to 1.72x baseline. This is qualitatively aligned with SABER's intended constraint-violation behavior and with the README examples that show more unsafe contacts or constraint violations after attack.

`action_inflation` is directionally aligned but weaker than expected. The run shows a 1.22x average step ratio and 8.93% attack success. SABER's README headline reports about 55% more steps, while this run shows about 22% more steps on this Pi0.5 subset. Some high-reward action-inflation cases also come from long horizon or timeout behavior, so the result should not be read as a clean "same task success with many more actions" result without a success-preserving step-ratio analysis.

`task_failure` did not reproduce a strong attack effect. Only 1 of 57 baseline-success episodes flipped to failure, with an attack success rate of 1.75%. Many generated perturbations behaved like fallback object-token substitutions rather than robust model-selected task-failure edits.

Overall conclusion:

```text
The official LoRA eval path is reproduced and validated.
The result is paper-consistent for constraint_violation.
The action_inflation trend is present but materially weaker than the README headline.
The task_failure attack is not consistent with the expected attack strength.
Do not claim full paper-level reproduction from this run alone.
```

## Comparison Caveats

This run is not an exact one-to-one reproduction of all SABER paper tables:

- It evaluates one victim model, `openpi_pi05`.
- It uses task ids `7-9` with 5 episodes per task, for 60 scenarios per objective.
- The README headline metrics are aggregate results and may include multiple VLA victims and a broader attack-replay protocol.
- The local `eval_attack_vla.py` path includes runtime fixes for GPU isolation, text-tool fallback, and parsing robustness.
- `action_inflation` used `max_steps=800`, so some long runs may represent timeout/failure rather than pure success-preserving inflation.
- Absolute constraint-violation counts are event counts, not directly the README's percent increase. A paper-style comparison should compute baseline-vs-attack ratios with the same metric definition.

## Recommended Next Steps

1. For a paper-style transfer result, replay the generated records on the other target VLAs and summarize per-victim metrics.
2. For action inflation, compute the step ratio only on episodes where both baseline and attack succeed.
3. For constraint violation, compute baseline and attack violation deltas or ratios using the exact paper aggregation.
4. For task failure, inspect why the LoRA agent frequently falls back to simple replacements and whether prompt/tool parsing differs from the authors' expected runtime.

