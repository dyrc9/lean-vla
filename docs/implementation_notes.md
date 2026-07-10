# Implementation Notes

## Agent Environment Conventions

Use the conda-provided uv for project Python work:

```bash
source scripts/env_vla.sh
conda run -n proofalign-libero "$PROOFALIGN_UV" run python ...
conda run -n proofalign-libero "$PROOFALIGN_UV" run pytest
```

Do not rely on system Python. For installs, prefer uv with a China-accessible
PyPI mirror such as `https://pypi.tuna.tsinghua.edu.cn/simple`.

Network access to GitHub and Hugging Face may require mirrors or transfer
proxies. Use a working GitHub proxy for source archives when direct GitHub
fails, and use `hf-mirror.com` for Hugging Face datasets / model files.

Keep code checkouts and other working files in the repository workspace, usually
under `external/`. Large reusable data, model weights, Hugging Face caches, and
multi-GB assets should default to `/data0/ldx`, with symlinks from the workspace
when the code expects an in-tree path.

## VLA Runtime

OpenVLA-OFT is the current real VLA backend. The source checkout lives at
`external/openvla-oft`; the plugin lives at `experiments/libero_vla_plugin.py`.
Do not create a code workspace under `/data0/ldx`.

Install or repair the VLA inference stack through uv:

```bash
source scripts/env_vla.sh
conda run -n proofalign-libero "$PROOFALIGN_UV" sync \
  --inexact \
  --extra vla \
  --cache-dir "$UV_CACHE_DIR" \
  --default-index https://pypi.tuna.tsinghua.edu.cn/simple
```

The `vla` extra pins the versions that resolved the OpenVLA-OFT dependency
conflicts:

- `torch==2.2.0` with cu121 wheels
- OpenVLA-OFT `transformers` fork at commit `bc339d9ad707454c0c115970db43c260067c61ab`
- `dlimp_openvla` at commit `040105d256bd28866cc6620621a3d5f7b6b91b46`
- `protobuf==3.20.3`
- `tensorflow-metadata==1.14.0`
- `wandb==0.16.6`

Verified smoke commands:

```bash
CUDA_VISIBLE_DEVICES=4 \
PYTHONPATH="$PWD:$PWD/src" \
conda run -n proofalign-libero python scripts/smoke_openvla.py

CUDA_VISIBLE_DEVICES=4,5 \
MUJOCO_EGL_DEVICE_ID=5 \
PYTHONPATH="$PWD:$PWD/src" \
conda run -n proofalign-libero python scripts/run_libero_online.py \
  --benchmark affordance \
  --task-id 2 \
  --init-state-id 0 \
  --max-steps 1 \
  --warmup-steps 2 \
  --camera-height 224 \
  --camera-width 224 \
  --render-gpu-device-id 5 \
  --policy experiments.libero_vla_plugin:create_policy \
  --abstractor experiments.libero_vla_plugin:create_abstractor \
  --output results/libero_online/affordance_task2_init0_openvla_oft_smoke.json
```

The online smoke verifies VLA raw action generation, LIBERO execution, symbolic
abstraction, and ProofAlign wrapper tracing. It is not a paper metric. A mock
checker result is diagnostic-only and can no longer authorize execution.

## Trusted Boundary

Lean is used only as a trusted checker for discrete symbolic contracts. Python is
responsible for orchestration, typed object construction, finite-template parsing,
action/state abstraction, simulation adapters and execution decisions.

The prototype intentionally avoids claiming that Lean verifies raw images, point
clouds, continuous trajectories, low-level controllers or real-world dynamics.

Two checker paths coexist:

- `legacy-lean-boolean`: Python emits a concrete `IntentAligned`,
  `EffectAligned` or `CertifiedDualChunkAligned` expression and Lean checks
  `expression = true` with `by decide`;
- `ctda-python-reference`: Python runs the typed CTDA staged protocol. The Lean
  CTDA definitions and reflection theorems build successfully, but the online
  LIBERO path does not yet call them as its evaluator.

Do not label a `ctda-python-reference` result as an online Lean CTDA proof.

## Runtime Flow

### Legacy/toy flow

1. `intent_parser.parse_intent` maps a supported natural-language template into
   `TaskIntent`.
2. `action_abstraction.action_from_dict` maps a candidate dictionary into
   `Action`.
3. `DualAlignmentChecker.check_intent_alignment` performs Python diagnostics and
   requires a passing Lean Boolean claim.
4. The simulator or LIBERO wrapper executes the allowed action/chunk.
5. `check_effect_alignment` or `check_chunk_effect_alignment` audits the
   post-state/trace and requires another passing Lean Boolean claim.
6. The runtime returns `allow`, `reject`, `replan` or `safe_stop`.

Dangerous or unsupported instructions are represented as `reject_required` and rejected before candidate action execution.

### CTDA online flow

1. The runner freezes instruction/BDDL bytes, action bounds, safety spec, time
   base, episode nonce and a structured fallback manifest.
2. `CTDARuntimeSession` creates an authenticated typed mission and activates a
   semantic macro-contract.
3. `prepare_prefix` binds the current state/monitor, VLA proposal, authorized
   command, conditional tube, evidence and fallback.
4. `CTDASupervisor.authorize_prefix` must return `proven` before dispatch.
5. The wrapper dispatches exactly one raw action step, then records actuator
   receipt, plant trace, symbolic event trace and abstraction/runtime evidence.
6. `observe_prefix` advances the persistent monitor to `complete`,
   `safe_pending`, `violated`, `unknown` or `inconsistent`.
7. A non-continuable verdict atomically invalidates the old chain and dispatches
   the pinned fallback, whose switch receipt is persisted.

One raw step per authorization is intentional. A semantic contract may still
span multiple steps and policy calls.

## Lean Specification

The legacy Lean files define:

- `Action`
- `TaskIntent`
- `WorldState`
- `SafetySpec`
- `IntentAligned`
- `EffectAligned`
- `SafeAction`
- `DualAligned`
- `ChunkEffectAligned`
- `CertifiedDualChunkAligned`

`lean/ProofAlign/Examples.lean` includes examples showing a safe mug-handle grasp passing, a knife-blade grasp failing intent alignment, and a collision failing effect alignment.

`lean/ProofAlign/CTDA.lean` additionally defines the frozen mission, semantic
contract, action/authorization/receipt/trace bindings, staged checkers, persistent
finite-prefix monitor and checker soundness/reflection theorems.
`lean/ProofAlign/CTDAExamples.lean` contains positive and fail-closed negative
examples.

When Lean and Lake are installed, the Python bridge runs:

```bash
cd lean
lake build ProofAlign
```

If Lean is not installed, the default `LeanBridge` returns mode `unavailable`
with `passed = false`. Explicit mock mode is limited to tests and demonstrations
and must never be connected to the execution-authorization path.

## CTDA Runtime Requirements

`--ctda` is intentionally stricter than legacy mode. It requires:

- `--warmup-steps 0`;
- `--ctda-fallback-witness <v2-json>`;
- `--ctda-fallback-witness-sha256 <digest>`;
- `--ctda-evidence-mode local-simulator-exact-allowlist`;
- a fallback manifest bound to the live BDDL digest, `SafetySpec`, environment
  action bounds and switch-latency declaration;
- a canonical all-zero `hold` command inside the live action bounds.

Batch CTDA runs reject `--skip-existing`, because cached output cannot revalidate
the live task root, initial state, environment version, action bounds, observer
state or fallback dispatch.

The exact fallback manifest schema is enforced in
`src/proofalign/benchmark/libero_online_runner.py`. Treat code and `--help` as the
command-line source of truth; never copy an old manifest without regenerating and
pinning its digest.

## Local Verification

Run the full local suite before pushing changes that affect CTDA semantics:

```bash
uv run pytest
(cd lean && lake build ProofAlign)
uv run python -m proofalign.executor
uv run python -m proofalign.experiments --input examples/tasks --output results/toy
```

Focused checks during development:

```bash
uv run pytest \
  tests/test_ctda.py \
  tests/test_ctda_runtime.py \
  tests/test_libero_online_wrapper.py \
  tests/test_libero_online_runner.py \
  tests/test_lean_bridge.py
```

Important regression categories are:

- wrong spec/episode/contract/monitor digest;
- stale or replayed proposal authorization;
- sparse or discontinuous tube coverage;
- authorized/executed command mismatch;
- empty or non-monotonic plant trace;
- symbolic fact without plant provenance;
- missing post evidence or expired deadline;
- fallback manifest mismatch and failed/late switch receipt.

## Remaining Integration Points

For a real VLA or LIBERO-Safety integration:

- connect the online serializer/evaluator to the Lean CTDA checker rather than the
  Python reference evaluator;
- validate the BDDL/task-root compiler against the typed mission semantics;
- replace simulator allowlist attestations with signature/proof-verifiable
  observer and actuator evidence;
- replace the conditional kinematic tube with a dynamics-aware CBF, predictive
  filter or reachability witness;
- provide a verified fallback controller, recoverable set and switching theorem;
- preserve the separation between untrusted abstraction/certificate generation
  and trusted contract checking.

See `docs/method.md` for the normative protocol and `docs/README.md` for the
documentation status matrix.
