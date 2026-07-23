# ProofAlign

ProofAlign is a research prototype for mission-rooted, persistent dual runtime monitoring of
Vision-Language-Action execution. Its scoped method, Contract-Carrying Temporal Dual Alignment (CTDA), requires:

1. a candidate contract to refine a trusted, locally frozen benchmark mission and active phase; and
2. each raw prefix, dispatch receipt, and cumulative observation to remain bound to that contract before phase
   advancement.

The target is auditable simulator execution integrity, not an end-to-end or absolute physical safety proof.

The method has exactly two alignment relations: **trusted intent → planned action** and **accepted planned action →
applied/observed action**. It exposes only three transactions—certify a persistent contract, authorize one exact
final command, and check execution/effect before updating the monitor. Contracts and receipts are core protocol
objects; signatures, provenance, wire formats, Lean replay, and optional CBF filtering are supporting mechanisms,
not additional alignment layers or separate method contributions.

## Current result

- E0 freezes 12 non-real-time supported LIBERO-Safety affordance/init0 units.
- E1 clean utility is complete on the frozen policy-seed-1 slice: 12/12 pairs are valid, VLA-only succeeds on
  8/12 tasks, Full CTDA succeeds on 0/12, and task/safe-success retention is 0.
- E3 clean safety is 12/12 preserved with 117/117 complete negative collision/cost observations.
- E3 post-dispatch behavior failed closed in all 12 episodes, but the frozen primary classifier remains
  `0 contained / 0 failed / 12 unknown` because of a receipt-schema mismatch.
- E4 passes 1/1 real-Lean control and 35/35 frozen fault cases.
- Lean evaluation remains too slow for real-time enforcement; the system is a slow-interlock/offline prototype.

CTDA v1 therefore requires revision before any expanded runtime claim. A separate CTDA v2 no-dispatch prototype
preserves a six-stage wire, 21/21 Python/Lean parity, typed evidence, Ed25519, and source-bound AEGIS geometry/CBF
assets. These are frozen implementation and regression assets—not the required architecture of the next method
version—and they establish no clean utility, online liveness, recovery, or defense-efficacy result. The next method
design, if later authorized, will refreeze a smaller five-component/three-transaction architecture and first compare
VLA-only, Intent-only, Execution-only, and Dual. No retained Phantom Menace or SABER workload has yet passed the
complete held-out independent-safety qualification chain. The only current rollout exception is the explicitly
exploratory Execution-only action-envelope successor; it cannot establish confirmatory defense efficacy.

The refrozen architecture now has a separate `proofalign-integrity-v1` local prototype: five components, three public
transactions, one shared four-arm method switch, exact final-command authorization, one-use dispatch receipts, and
checked completion/atomic monitor updates. `ProofAlign.IntegrityCore` formalizes the two invariants and arm semantics;
there is not yet a machine-checked refinement from the Python fast checker to that Lean model. The only command sink
is in-memory and has no simulator, socket, GPU, or hardware capability.

The first large-sample SABER P0b producer root terminated before record generation because it used the wrong Python
environment. A separately authorized fresh2 producer/victim run then retained 48 immutable records and 96/96 valid
clean/attacked episodes. It observed 23 clean-eligible pairs—below the frozen minimum of 26—and therefore remains
`p0b_blocked_insufficient_clean_baseline`, even though 15/23 eligible pairs had a typed transition. This is not a
confirmed attack qualification.

The current experiment priority is the exploratory Execution-only action-envelope attacked+defended successor.
Its clean R1 retained 22/23 baseline-eligible strict successes; attacked R2 failed before a new environment action on
a non-finite policy command. R3 added a deterministic zero brake but was stopped before its all-or-nothing binding
probe completed after runtime GPU contention and device-isolation mismatch. R3 produced zero episodes and no
efficacy outcome. The next run requires a resource-isolated successor protocol and fresh root; see
[Current experiment priority](docs/current_experiment.md).

## Start here

- [Project status](docs/project_status.md)
- [Current experiment priority](docs/current_experiment.md)
- [Unified evaluation results](docs/evaluation_results.md)
- [Method and claim boundary](docs/method.md)
- [Current and target architecture](docs/system_architecture.md)
- [Paper story](docs/paper/paper_story.md)
- [Related work and novelty audit](docs/paper/related_work.md)
- [Roadmap](docs/roadmap.md)
- [Experiment rules](docs/experiments.md)
- [Current execution environment](docs/remote_execution.md)
- [Next experiment prompt](docs/next_experiment_prompt.md)
- [Documentation index](docs/README.md)

Detailed phase reports and old handoffs are retained under [docs/archive](docs/archive/README.md) for audit only.

## Main code

- `src/proofalign/integrity_models.py`: version-isolated minimal domain model and four causal arms.
- `src/proofalign/integrity_checker.py`: deterministic fast checker and exact-prefix authorizer.
- `src/proofalign/integrity_runtime.py`: five components, three transactions, one-use in-memory dispatch boundary,
  and checked effect/monitor update.
- `src/proofalign/integrity_intervention.py`: optional pass/project/replan/block policies whose final command returns
  to the authorizer.
- `src/proofalign/ctda*.py`: typed CTDA semantics, runtime, wire, evaluator, and replay.
- `src/proofalign/ctda_v2.py` / `ctda_v2_wire.py` / `ctda_v2_evaluator.py`: frozen, version-isolated
  certificate/rebind/intervention/progress prototype and offline Lean parity evaluator; it remains replayable but
  does not define the next target architecture and is not an online rollout path.
- `src/proofalign/benchmark/`: LIBERO task manifests, state observation, online transaction, and E1 baseline.
- `src/proofalign/benchmark/safelibero_foundation.py`: outcome-blind SafeLIBERO inventory, typed independent
  safety provenance, official collision labeling, and CAR/TSR/ETS/cost/RET classification.
- `src/proofalign/benchmark/aegis_runtime.py`: isolated AEGIS runtime/package/source/asset identity gate with
  zero policy, socket, simulator, inference, and action dispatch.
- `src/proofalign/benchmark/safelibero_ctda_support.py`: source-bound SafeLIBERO goal/mission templates, typed
  CTDA v2 state/progress/collision adapter, retained E1 attribution, and exact-unit support audit.
- `src/proofalign/benchmark/safelibero_open_region.py`: official-source-bound wooden-cabinet top-drawer joint,
  strict `qpos < -0.14 m` predicate, typed observation, and no-dispatch progress claim.
- `src/proofalign/benchmark/safelibero_ctda_v2_no_dispatch.py`: authenticated fake-observation progress packets,
  canonical 7D commands, typed post-filter witness binding, and recovery-ledger records with no action capability.
- `src/proofalign/evidence_crypto.py`: domain-separated Ed25519 attestation signing with exact producer/version key
  binding and local fingerprint revocation; production key provisioning is outside this module.
- `src/proofalign/benchmark/aegis_cbf_filter.py`: pinned-source analytical AEGIS CBF/QP projection, signed full-result
  witness, and fail-closed CTDA post-filter adapter with no action capability.
- `src/proofalign/benchmark/aegis_cbf_geometry.py`: signed typed ellipsoid geometry boundary and source-equivalent
  `compute_h_coeffs_3d` coefficient derivation; raw camera/perception trust remains external.
- `lean/ProofAlign/IntegrityCore.lean`: minimal two-invariant/four-arm Lean model; not yet refined to the Python
  checker.
- `lean/ProofAlign/`: historical CTDA definitions and staged wire checkers.
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
[docs/remote_execution.md](docs/remote_execution.md). The only current GPU priority is a fresh, resource-isolated
successor to the stopped R3 action-envelope experiment. It requires a newly frozen protocol, clean worktree, fresh
root, two stable `<4096 MiB` GPUs with no compute process, and verified runtime JAX/EGL device mapping. Local unit
tests and Lean builds do not authorize any broader ProofAlign/CTDA or defense-baseline rollout.
