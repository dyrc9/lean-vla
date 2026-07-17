# ProofAlign

ProofAlign is a research prototype for **mission-rooted, persistent dual runtime
monitoring of Vision-Language-Action (VLA) execution**. The current method is a
scope-frozen form of Contract-Carrying Temporal Dual Alignment (CTDA):

1. a candidate semantic contract must refine a trusted, locally frozen benchmark
   mission and its active phase; and
2. each raw action prefix, dispatch record, and cumulative observed trace must
   conform to that contract before the task phase may advance.

The current paper target is **VLA runtime execution integrity in simulation**.
It is not an end-to-end physical safety proof.

## Current Status

- The canonical progress dashboard is [docs/project_status.md](docs/project_status.md):
  CTDA's five-prefix method-validity gate passed, while real-time enforcement,
  Phantom R1, and SABER R1 have explicit negative or fail-closed outcomes. The
  current mainline is ProofAlign-first evaluation. Its outcome-blind E0 v1 audit
  found 13/75 live structural compiler candidates but zero strict E1-supported
  units. The first E0 v2 repair now binds all 15 affordance contact-part goals to
  exact BDDL digests and independently observes two-finger MuJoCo contacts; its
  outcome-blind 75-task candidate audit compiled all 15 selected tasks, and all 15
  passed the init/collision/cost gate. The strict timing failure remains recorded for
  E4. After timing was explicitly moved out of E0, a fresh slow-interlock safety audit
  accepted 12 tasks and rejected frypan tasks 4/9/14 for cross-seed initial-state digest
    mismatch. E0 v2 is now frozen at 12 supported / 63 unsupported. E1-v1 then failed
    before environment construction because of a physical-EGL binding error; E1-v2
    fixed that startup path but all 24 preregistered records failed before dispatch on
    unsupported nested policy metadata. Both runs are retained as invalid evidence.
    E1-v3 then isolated recursive policy-metadata freezing from the byte-frozen E0
    wrapper, excluded invalid pairs from inference, and passed an exact-GPU real
    policy-output preflight. Its fresh run retained all 24 artifacts, but all 12 Full
    CTDA records were rejected after dispatch because the enriched CTDA initial-state
    digest was compared with a less enriched VLA-only observation digest. Thus v3 is
    terminal-invalid with zero valid pairs and no E1 inference. Those dispatched pairs
    cannot be replaced and duality remains blocked. A distinct, preregistered E3
    Full-CTDA-only safety run then completed on the same E0-supported task slice without
    reinterpreting E1: all 12 records were valid and safety-preserved, with 117/117
    collision/cost observations, zero hard-invariant failures, and 12 pre-dispatch
    blocks with zero phase advance. Task success was 0/12 and no fresh online fallback
    was triggered, so this is clean simulator safety evidence rather than utility,
    recovery, attack-defense, hardware-safety, or real-time evidence. A separately
    preregistered post-dispatch observation-failure challenge then completed 12/12
    valid records: every trace monitor-failed closed, replanned, applied the exact
    zero hold, and observed a complete safe postcondition. Its frozen primary labeler
    nevertheless classified all 12 as unknown because it required a top-level receipt
    integrity boolean absent from the typed receipt schema. Post-hoc typed receipt
    reconstruction verified all retained digests but does not upgrade the primary
    `0 contained / 0 failed / 12 unknown` result or authorize a rerun. E4 then froze a
    CPU/Lean fail-closed robustness matrix. Its v1 runner was retained as terminal-invalid
    after a result-serialization defect; a serialization-only v2 amendment used a new
    root and passed 36/36 cases (1 real-Lean control and 35 fault cases). This establishes
    only scoped component fail-closed behavior, not physical safety, recovery, attack
    defense, real-time enforcement, availability, or task utility.
- SAFE and FIPER official R0 attempts used the dedicated
  `external/worktrees/safe-fiper-r0` worktree. They were interrupted during the
  2026-07-15 closeout and are not reproduction results. Their already
  downloaded, hash-frozen assets, partial outputs, and uv environments remain
  under `/data0/ldx` for audit. The dedicated worktree has been removed; frozen
  source checkouts remain in `external/{SAFE,SAFE-openpi,fiper}`, and future
  commands run from the main repository. A 2026-07-16 fresh FIPER attempt reused
  the existing environment but exited without a terminal manifest; its partial
  outputs remain audit-only. A second isolated fresh run now uses the same existing
  environment under a user-systemd service. Neither run blocks ProofAlign
  self-evaluation, and only a completed terminal manifest can enter comparison.
- The legacy dual checker calls Lean for concrete Boolean claims.
- Python contains a typed CTDA reference runtime and LIBERO single-prefix loop.
- Lean contains CTDA datatypes, staged checkers, a persistent finite-prefix
  monitor, and reflection/soundness results.
- The paper CTDA path now derives a persistent Pick/Place contract only from the
  frozen mission phase and residual obligation. Policy prompts and
  `proofalign_action` remain untrusted diagnostic metadata.
- `ctda-wire-v1` and selectable `ctda-python-reference`, `ctda-lean-kernel`, and
  `ctda-shadow` evaluators cover semantic, prefix-pre, observed-prefix, and
  monitor-step judgments. Lean failure never falls back to Python dispatch.
- The 27-case CPU golden/shadow corpus has zero Python/Lean mismatch. Generated
  Lean replay artifacts, checker/build digests, stdout/stderr, and verdicts are
  saved per request.
- The current policy plugins can derive symbolic metadata from the policy-facing
  instruction. That path is compatibility/diagnostic code, not an acceptable
  authority for the paper CTDA contract. A consumer-side versioned binder now
  checks trusted state and raw commands independently.
- GPU work is isolated behind fail-closed readiness gates and dedicated result
  roots; a partial log or active process is never treated as a completed result.

## Documentation

Start at [docs/README.md](docs/README.md). The canonical documents are:

- [Method and claim boundary](docs/method.md)
- [Current and target architecture](docs/system_architecture.md)
- [Execution roadmap](docs/roadmap.md)
- [Experiment protocol](docs/experiments.md)
- [E0 support audit and frozen self-evaluation scope](docs/e0_support_audit.md)
- [E1 clean paired pilot execution handoff](docs/e1_clean_pilot.md)
- [E3 safety-only evaluation](docs/e3_safety_evaluation.md)
- [E3 post-dispatch intervention result](docs/e3_postdispatch_intervention.md)
- [E4 fail-closed robustness evaluation](docs/e4_robustness_evaluation.md)
- [E0 v2 candidate machine protocol](experiments/proofalign_e0_protocol_v2_candidate.json)
- [E0 v2 init/fallback audit record](experiments/proofalign_e0_v2_fallback_audit_summary.json)
- [E0 v2 candidate gate decision](experiments/proofalign_e0_v2_gate_decision.json)
- [Frozen E0 v2 protocol](experiments/proofalign_e0_protocol_v2.json)
- [Frozen E1-v2 startup amendment](experiments/proofalign_e1_clean_pilot_protocol_v2.json)
- [Frozen E3 safety protocol](experiments/proofalign_e3_safety_protocol.json)
- [E3 terminal machine summary](experiments/proofalign_e3_safety_terminal_summary.json)
- [E3 post-dispatch terminal machine summary](experiments/proofalign_e3_postdispatch_terminal_summary.json)
- [Attack/defense reproduction plan](docs/reproduction_plan.md)
- [Implementation notes](docs/implementation_notes.md)
- [Remote/GPU execution runbook](docs/remote_execution.md)
- [Paper story](docs/paper_story.md)

Files under `docs/archive/` are historical and non-normative. Agents must not use
them as the current method, CLI, experiment plan, or claim boundary.

## Local CPU/Lean Verification

```bash
uv sync --dev
uv run pytest
(cd lean && lake build ProofAlign)
```

Useful focused checks while developing the next milestone:

```bash
uv run pytest \
  tests/test_ctda.py \
  tests/test_ctda_runtime.py \
  tests/test_ctda_wire.py \
  tests/test_ctda_evaluator.py \
  tests/test_ctda_shadow.py \
  tests/test_libero_online_wrapper.py \
  tests/test_libero_online_runner.py \
  tests/test_libero_task_manifest.py \
  tests/test_proofalign_e0_audit.py \
  tests/test_lean_bridge.py
```

The toy demo remains available for compatibility diagnostics:

```bash
uv run python -m proofalign.executor
```

CPU-only golden parity/shadow replay:

```bash
uv run python -m proofalign.ctda_shadow \
  tests/fixtures/ctda_golden.json \
  --artifact-dir /tmp/proofalign-ctda-shadow-artifacts \
  --output /tmp/proofalign-ctda-shadow-report.json
```

Remote GPU checkouts should run the fail-closed readiness manifest before any
rollout, then use the single-episode smoke wrapper documented in the remote
runbook:

```bash
python3 scripts/remote_gpu_preflight.py --help
scripts/run_remote_gpu_smoke.sh
```

The smoke wrapper requires physical VLA/EGL GPU ids and, for CTDA, a live
task-bound fallback witness plus its pinned SHA-256. See
[`docs/remote_execution.md`](docs/remote_execution.md) for the complete setup.

## Main Code Paths

- `src/proofalign/ctda.py`: typed mission, contract, evidence, and reference
  checker objects.
- `src/proofalign/ctda_runtime.py`: persistent CTDA runtime session and prefix
  transaction logic.
- `src/proofalign/ctda_wire.py`: strict canonical wire schema and reference
  semantics.
- `src/proofalign/ctda_evaluator.py`: Python, Lean-kernel, and shadow evaluators.
- `src/proofalign/ctda_shadow.py`: CPU replay, parity, latency, and provenance
  summary harness.
- `src/proofalign/benchmark/libero_online_wrapper.py`: LIBERO execution loop.
- `experiments/libero_openpi_plugin.py`: pi0.5/OpenPI policy integration.
- `lean/ProofAlign/CTDA.lean`: Lean CTDA specification and checker results.
- `lean/ProofAlign/CTDAWire.lean`: jointly supported online wire judgments.
- `scripts/run_liberosafety_pi05_openpi_eval.py`: pure pi0.5 baseline/attack
  rollout runner.
- `scripts/run_libero_online_batch.py`: defense/ablation online runner.

## Claim Boundary

The repository does not currently claim:

- cryptographically authenticated missions;
- a verified general BDDL or natural-language compiler;
- verified perception or raw-action semantic truth;
- continuous-dynamics or hardware safety;
- sensor/actuator attestation;
- a verified recovery controller;
- real-time Lean enforcement: the current per-request replay compilation has
  sub-second-to-multi-second CPU p99 and exceeds the simulator control period;
  or
- defense efficacy until paired clean/attacked/defended GPU experiments are
  complete.

CLI behavior is defined by the current code and `--help`, not by archived run
logs or handoff notes.
