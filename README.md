# ProofAlign

ProofAlign is a small research prototype for a Lean-based dual alignment safety wrapper for Vision-Language-Action (VLA) robots.

The prototype accepts:

- an initial natural-language task intent,
- a symbolic current world state,
- a candidate VLA action or action chunk,
- an observed post-action state from a tiny simulator.

Python orchestrates parsing, symbolic abstraction, simulation, and runtime decisions. Lean is the trusted checker for the discrete action-contract specification. Lean does not do perception, motion planning, trajectory optimization, or VLA inference.

## Dual Alignment

ProofAlign checks two layers:

1. **Intent-Action Alignment**
   Checks whether the candidate action is a legal refinement of the original task intent. For example, `pick up the mug by the handle` cannot be refined into picking a knife or grasping an unsafe blade.

2. **Action-Effect Alignment**
   Checks whether the observed post-state satisfies the symbolic contract promised by the action. For example, after `Pick(mug, handle)`, the mug should be held by the gripper; after `Place(mug, plate)`, the mug should be inside the plate region; collisions trigger `safe_stop`.

The output is an execution decision: `allow`, `reject`, `replan`, or `safe_stop`.

## Install

This project uses `uv` for Python environment management.

```bash
uv sync --dev
```

Lean is optional for the Python pipeline, but recommended. If Lean is unavailable, `LeanBridge` enters explicit mock fallback mode so the research pipeline remains runnable. To install Lean 4, use `elan`:

```bash
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
```

This repository includes `lean/lean-toolchain` pinned to Lean `v4.24.0`.

## Run

Run the default demo:

```bash
uv run python -m proofalign.executor
```

Run a specific task:

```bash
uv run python -m proofalign.executor examples/tasks/hri_avoid_hand.json
```

Run tests:

```bash
uv run pytest
```

Run the toy ablation experiment suite:

```bash
uv run python -m proofalign.experiments --input examples/tasks --output results/toy
```

Check the Lean specification directly:

```bash
cd lean
lake build ProofAlign
```

Or run all local checks:

```bash
make check
```

## Examples

The `examples/tasks/` directory contains five JSON scenarios inspired by LIBERO-Safety categories:

- `aag_safe_grasp.json`: safe mug handle grasp.
- `hri_avoid_hand.json`: human-hand proximity causes `replan`.
- `tsa_avoid_obstacle.json`: obstacle collision causes `safe_stop`.
- `fshoa_hand_object.json`: human-held object is rejected.
- `ssr_dangerous_instruction.json`: dangerous/negative instruction is rejected before execution.

## Architecture

- `intent_parser.py`: rule-based parser for a small instruction grammar.
- `action_abstraction.py`: converts VLA-like action dictionaries into symbolic actions.
- `checker.py`: implements the dual alignment checker and runtime decisions.
- `simulator.py`: discrete post-state simulator for prototype tests.
- `lean_bridge.py`: calls Lean/Lake when available; otherwise uses explicit mock fallback.
- `certificates.py`: schema for untrusted perception/planner/simulator certificates.
- `baselines.py` and `experiments.py`: local ablation runner and metrics export.
- `benchmark/libero_safety_adapter.py`: handoff point for GPU-machine LIBERO-Safety integration.
- `benchmark/libero_online_wrapper.py`: online wrapper for the native LIBERO-Safety robosuite/MuJoCo backend.
- `lean/ProofAlign/*.lean`: Lean 4 datatypes and predicates for symbolic contracts.

## GPU Benchmark Handoff

The repository does not vendor LIBERO-Safety. Copy this project to the GPU machine, set `LIBERO_SAFETY_ROOT`, export or adapt episodes through `src/proofalign/benchmark/libero_safety_adapter.py`, then run `python -m proofalign.experiments`.

For online rollouts, instantiate LIBERO-Safety's native `OffScreenRenderEnv`
through `make_libero_offscreen_env`, wrap it with `ProofAlignLiberoWrapper`, and
pass each VLA step as `{raw_action, proofalign_action}` so the same robosuite /
MuJoCo backend is used for execution while ProofAlign checks symbolic contracts.
The executable entrypoint is:

```bash
uv run python scripts/run_libero_online.py --benchmark affordance --task-id 0 --policy my_vla_eval:create_policy
```

An OpenVLA/OpenVLA-OFT plugin is provided at
`experiments/libero_vla_plugin.py`. The default model is the published
LIBERO-tuned OpenVLA-OFT checkpoint
`moojink/openvla-7b-oft-finetuned-libero-spatial`; Hugging Face cache files are
stored under `/data0/ldx/huggingface` by default.

```bash
source scripts/env_vla.sh
git clone https://github.com/moojink/openvla-oft.git external/openvla-oft
conda run -n proofalign-libero "$PROOFALIGN_UV" sync \
  --inexact \
  --extra vla \
  --cache-dir "$UV_CACHE_DIR" \
  --default-index https://pypi.tuna.tsinghua.edu.cn/simple

export LIBERO_SAFETY_ROOT=/path/to/LIBERO-Safety

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

For a standalone VLA model smoke without LIBERO:

```bash
CUDA_VISIBLE_DEVICES=4 \
PYTHONPATH="$PWD:$PWD/src" \
conda run -n proofalign-libero python scripts/smoke_openvla.py
```

Known-good smoke:

- `scripts/smoke_openvla.py` loads OpenVLA-OFT and emits an 8-action chunk.
- `results/libero_online/affordance_task2_init0_openvla_oft_smoke.json` records a real one-step LIBERO online run with OpenVLA-OFT raw action and ProofAlign `allow`.

See [docs/benchmark_gpu.md](docs/benchmark_gpu.md) for the exact handoff commands.

## Scope

This is a paper-idea prototype, not a complete robot safety system. It demonstrates the separation between:

- external certificate generation,
- symbolic abstraction,
- Lean proof/spec checking,
- runtime execution decisions.

It does not prove continuous robot dynamics safe, verify perception correctness, or replace collision checking and motion planning. A real VLA integration would generate action contracts from policy outputs and feed observed symbolic postconditions from perception/state-estimation modules into this checker.
