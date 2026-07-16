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
  current mainline is ProofAlign-first evaluation: supported-slice clean utility,
  duality, closed-loop intervention, and cost come before external comparisons.
- SAFE and FIPER official R0 attempts used the dedicated
  `external/worktrees/safe-fiper-r0` worktree. They were interrupted during the
  2026-07-15 closeout and are not reproduction results. Their already
  downloaded, hash-frozen assets, partial outputs, and uv environments remain
  under `/data0/ldx` for audit. The dedicated worktree has been removed; frozen
  source checkouts remain in `external/{SAFE,SAFE-openpi,fiper}`, and future
  commands run from the main repository. A 2026-07-16 fresh FIPER attempt reused
  the existing environment but exited without a terminal manifest; its partial
  outputs remain audit-only and do not block ProofAlign self-evaluation.
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
