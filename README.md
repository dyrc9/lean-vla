# ProofAlign

ProofAlign is a research prototype for mission-rooted, persistent dual runtime monitoring of
Vision-Language-Action execution. Its scoped method, Contract-Carrying Temporal Dual Alignment (CTDA), requires:

1. a candidate contract to refine a trusted, locally frozen benchmark mission and active phase; and
2. each raw prefix, dispatch receipt, and cumulative observation to remain bound to that contract before phase
   advancement.

The target is auditable simulator execution integrity, not an end-to-end or absolute physical safety proof.

## Current result

- E0 freezes 12 non-real-time supported LIBERO-Safety affordance/init0 units.
- E1 clean utility is complete on the frozen policy-seed-1 slice: 12/12 pairs are valid, VLA-only succeeds on
  8/12 tasks, Full CTDA succeeds on 0/12, and task/safe-success retention is 0.
- E3 clean safety is 12/12 preserved with 117/117 complete negative collision/cost observations.
- E3 post-dispatch behavior failed closed in all 12 episodes, but the frozen primary classifier remains
  `0 contained / 0 failed / 12 unknown` because of a receipt-schema mismatch.
- E4 passes 1/1 real-Lean control and 35/35 frozen fault cases.
- Lean evaluation remains too slow for real-time enforcement; the system is a slow-interlock/offline prototype.

CTDA v1 therefore requires revision before any expanded runtime claim. The immediate upstream blocker is attack
validity: no retained Phantom Menace or SABER workload passed the complete held-out independent-safety
qualification chain. All GPU experiments are paused until a new VLA-only threat-validation-only protocol is
frozen and explicitly authorized.

## Start here

- [Project status](docs/project_status.md)
- [Unified evaluation results](docs/evaluation_results.md)
- [Method and claim boundary](docs/method.md)
- [Roadmap](docs/roadmap.md)
- [Experiment rules](docs/experiments.md)
- [Current execution environment](docs/remote_execution.md)
- [Next experiment prompt](docs/next_experiment_prompt.md)
- [Documentation index](docs/README.md)

Detailed phase reports and old handoffs are retained under [docs/archive](docs/archive/README.md) for audit only.

## Main code

- `src/proofalign/ctda*.py`: typed CTDA semantics, runtime, wire, evaluator, and replay.
- `src/proofalign/benchmark/`: LIBERO task manifests, state observation, online transaction, and E1 baseline.
- `lean/ProofAlign/`: Lean definitions and staged wire checker.
- `scripts/`: frozen experiment runners, validators, and preflight tools.
- `experiments/`: machine protocols, registries, and terminal summaries.

## Basic verification

```bash
cd /home/ldx/lean-vla
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH=/home/ldx/lean-vla/src:/home/ldx/lean-vla
.venv/bin/pytest -q
(cd lean && lake build ProofAlign)
```

The stopped FIPER partial run intentionally retains its audited `data` symlink binding. The generic external-
baseline preflight must report `source_ready=false` in that state; the test suite asserts that fail-closed result.
Do not delete or alter the binding merely to make the preflight ready.

GPU/OpenPI execution requires the additional environment and isolation rules in
[docs/remote_execution.md](docs/remote_execution.md). All project experiments are currently paused; no GPU rollout
is authorized.
