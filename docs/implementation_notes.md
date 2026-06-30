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
abstraction, and ProofAlign wrapper tracing. It is not a paper metric and still
uses `lean_mode: mock`.

## Trusted Boundary

Lean is used only as a trusted checker for discrete symbolic contracts. The Python code is responsible for orchestration, parsing finite templates, action abstraction, simulation, and execution decisions.

The prototype intentionally avoids claiming that Lean verifies raw images, point clouds, continuous trajectories, low-level controllers, or real-world dynamics.

## Runtime Flow

1. `intent_parser.parse_intent` maps a supported natural-language template into `TaskIntent`.
2. `action_abstraction.action_from_dict` maps a candidate VLA action dictionary into `Action`.
3. `DualAlignmentChecker.check_intent_alignment` rejects actions that do not refine the task intent.
4. `DiscreteSimulator.execute` creates an observed symbolic post-state.
5. `DualAlignmentChecker.check_effect_alignment` checks the post-state contract.
6. `SafetyExecutor.run` returns `allow`, `reject`, `replan`, or `safe_stop`.

Dangerous or unsupported instructions are represented as `reject_required` and rejected before candidate action execution.

## Lean Specification

The Lean files define:

- `Action`
- `TaskIntent`
- `WorldState`
- `SafetySpec`
- `IntentAligned`
- `EffectAligned`
- `SafeAction`
- `DualAligned`

`lean/ProofAlign/Examples.lean` includes examples showing a safe mug-handle grasp passing, a knife-blade grasp failing intent alignment, and a collision failing effect alignment.

When Lean and Lake are installed, the Python bridge runs:

```bash
cd lean
lake build ProofAlign
```

If Lean is not installed, `LeanBridge` returns mode `mock`. This is a prototype fallback only; it should not be treated as a trusted formal check.

## Future Integration Points

For a real VLA or LIBERO-Safety integration:

- replace the rule-based parser with an external intent/certificate generator,
- replace `DiscreteSimulator` with observed symbolic state updates from perception,
- map continuous trajectories into action chunks with explicit contracts,
- keep Lean responsible for checking the discrete contract layer,
- route `replan` back to the VLA/planner and `safe_stop` to a robot safety controller.

The most important interface to preserve is the boundary between untrusted abstraction/certificate generation and trusted Lean checking.
