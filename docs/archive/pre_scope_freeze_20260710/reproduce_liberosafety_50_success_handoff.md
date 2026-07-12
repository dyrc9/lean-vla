# LIBERO-Safety 50%+ Success Reproduction Handoff

This document is for a separate agent whose only job is to reproduce the 50%+ success-rate regime reported for LIBERO-Safety-style evaluation. Do not treat the current OpenVLA-OFT ProofAlign experiments as that reproduction. They are safety-gating pilots on a stratified sample.

## Current State

Repository: `/home/ldx/lean-vla`

Relevant external checkouts:

- LIBERO-Safety: `external/LIBERO-Safety`
- OpenVLA-OFT: `external/openvla-oft`

Runtime environment:

```bash
source scripts/env_vla.sh
export LIBERO_SAFETY_ROOT=$PWD/external/LIBERO-Safety
export PYTHONPATH="$PWD:$PWD/src:$PWD/external/openvla-oft"
```

Known GPU/rendering setup used so far:

```bash
CUDA_VISIBLE_DEVICES=4,5
MUJOCO_EGL_DEVICE_ID=5
```

Lean works and is not the blocker:

```bash
PATH=/home/ldx/.local/lean-4.24.0/bin:$PATH lake build ProofAlign
```

## What Has Already Been Run

### 1. Lean-Gated ProofAlign Sample

Output:

```text
results/libero_online_lean_guided_sample_20260702/
```

Sample:

- 5 LIBERO-Safety suites
- task ids `0,7,14` per suite
- covers L0/L1/L2 once per suite
- 15 episodes total
- `init_state_id=0`

Result:

- task success: `1 / 15 = 6.7%`
- cost/collision: `0 / 15 = 0.0%`
- ProofAlign rejects: `14 / 15 = 93.3%`
- all ProofAlign checks used Lean, no mock fallback

### 2. Direct VLA-Only Sample, Not Official-Aligned

Output:

```text
results/libero_online_vla_only_guided_sample_20260702/
```

This ran OpenVLA-OFT raw actions directly, without ProofAlign/Lean, but used the earlier project runner settings:

- `max_steps=25`
- camera `224x224`
- no official OpenVLA-OFT image rotation
- no official OpenVLA-OFT gripper postprocessing

Result:

- task success: `1 / 15 = 6.7%`
- cost/collision: `9 / 15 = 60.0%`

This should not be compared to official paper success rates.

### 3. Official-Processing-Aligned VLA-Only Sample

Output:

```text
results/libero_online_vla_only_official_aligned_20260702/
```

Script:

```text
results/libero_online_vla_only_official_aligned_20260702/run_official_aligned_vla_only_sample.py
```

Aligned details:

- `max_steps=600`
- `num_steps_wait=10`
- camera `256x256`
- OpenVLA-OFT official `prepare_observation()`
- official image rotation: `agentview_image[::-1, ::-1]` and `robot0_eye_in_hand_image[::-1, ::-1]`
- official `process_action()`, including gripper normalize + invert
- `NUM_ACTIONS_CHUNK=8`

Result:

- task success: `2 / 15 = 13.3%`
- cost/collision: `9 / 15 = 60.0%`

Conclusion from this run: the low success rate is not only caused by horizon, image rotation, or gripper postprocessing. The larger issue is likely model/task-domain mismatch.

## Why The Current OpenVLA-OFT Runs Do Not Match 50%+

The checkpoint currently used is:

```text
moojink/openvla-7b-oft-finetuned-libero-spatial
```

This is a standard LIBERO-Spatial OpenVLA-OFT checkpoint. It is not known to be trained on LIBERO-Safety.

LIBERO-Safety README points to:

- Safety dataset: `LIBERO-Safety/libero_safety`
- Safety assets: `LIBERO-Safety/libero_safety_assets`
- Safety-tuned model: `LIBERO-Safety/pi05_libero_safety`

The README does not provide an OpenVLA-OFT Safety-tuned checkpoint in this repo. The 50%+ number may come from a Safety-trained model or a different architecture/checkpoint, not from `moojink/openvla-7b-oft-finetuned-libero-spatial`.

## Official Files To Read First

LIBERO-Safety:

- `external/LIBERO-Safety/README.md`
- `external/LIBERO-Safety/libero/libero/benchmark/vla_safety_task_map.py`
- `external/LIBERO-Safety/libero/configs/eval/default.yaml`
- `external/LIBERO-Safety/libero/configs/config.yaml`

OpenVLA-OFT:

- `external/openvla-oft/LIBERO.md`
- `external/openvla-oft/experiments/robot/libero/run_libero_eval.py`
- `external/openvla-oft/experiments/robot/libero/libero_utils.py`
- `external/openvla-oft/experiments/robot/openvla_utils.py`
- `external/openvla-oft/experiments/robot/robot_utils.py`

Key details from OpenVLA-OFT official LIBERO eval:

- `TASK_MAX_STEPS` for standard LIBERO: 220/280/300/520 depending on suite
- `num_steps_wait=10`
- `num_trials_per_task=50`
- `env_img_res=256`
- action chunking uses `NUM_ACTIONS_CHUNK`
- images are rotated 180 degrees in `libero_utils.py`
- gripper action is normalized and inverted in `process_action()`

Key detail from LIBERO-Safety eval config:

```yaml
max_steps: 600
n_eval: 20
```

## Reproduction Goal For The Next Agent

The target is not to improve ProofAlign. The target is to reproduce a high-success VLA baseline close to the reported 50%+ regime under LIBERO-Safety evaluation.

The next agent should answer:

1. Which exact model/checkpoint produces 50%+ on LIBERO-Safety?
2. What exact official evaluation script/protocol produced that number?
3. Can it be reproduced locally on a small sample first?
4. Does full or larger-sample evaluation match the expected success rate?

## Recommended Plan

### Step 1: Verify The Claimed Number

Find the source of the 50%+ claim:

- LIBERO-Safety paper / website tables
- README model links
- Hugging Face model cards
- any official eval script, config, or leaderboard table

Record:

- model name
- checkpoint repo/path
- success metric definition
- safety/cost metric definition
- suite split
- levels included
- number of tasks
- number of init states / seeds / trials
- max steps / horizon
- camera resolution
- action postprocessing

Do not assume the number refers to OpenVLA-OFT unless the table explicitly says so.

### Step 2: Prefer The Official Safety Model First

Try the released LIBERO-Safety model first:

```text
LIBERO-Safety/pi05_libero_safety
```

This may require OpenPI / pi0.5 evaluation code, not OpenVLA-OFT.

If the 50%+ number is for `pi05_libero_safety`, reproduce that model before trying OpenVLA-OFT.

### Step 3: If Reproducing OpenVLA-OFT, Confirm A Safety-Tuned Checkpoint

The current checkpoint:

```text
moojink/openvla-7b-oft-finetuned-libero-spatial
```

is not sufficient evidence for LIBERO-Safety performance.

Look for one of:

- OpenVLA-OFT fine-tuned on `LIBERO-Safety/libero_safety`
- a local checkpoint under `/data0/ldx` or another workspace
- a model card referencing LIBERO-Safety, not standard LIBERO-Spatial/Object/Goal/10

### Step 4: Run A Tiny Smoke Before Any Full Eval

Use a very small official-aligned sample:

- 1 suite
- 1 task
- 1 init state
- official max steps
- official preprocessing/action postprocessing

Confirm:

- environment loads correct BDDL from LIBERO-Safety
- model outputs valid actions
- gripper convention is correct
- `env.check_success()` can become true
- cost/collision is logged

### Step 5: Run A Stratified Sample

Use the same stratified sample already used here for comparability:

```text
suites = affordance, obstacle_avoidance, human_safety, obstacle_avoidance_human, reasoning_safety
task_ids = 0,7,14
init_state_id = 0
```

Expected output should include:

- task success rate
- cost/collision rate
- per-suite success
- per-level success
- average steps
- exact model/checkpoint/config

### Step 6: Scale Only After The Sample Looks Plausible

Then scale to:

- all 75 LIBERO-Safety tasks: 5 suites x 3 levels x 5 tasks
- multiple init states / trials if required by official protocol
- multiple seeds if required

## Known Pitfalls

- `uv run` may rewrite `uv.lock` registry URLs from the Tsinghua mirror to PyPI. Restore `uv.lock` after runs if it changes:

  ```bash
  git show HEAD:uv.lock > uv.lock
  ```

- The normal project runner originally used `max_steps=25`, which is too short for official success-rate reproduction.
- OpenVLA-OFT official evaluation rotates images by 180 degrees. Missing this hurts performance.
- OpenVLA-OFT official evaluation normalizes and inverts gripper action before env execution. Missing this hurts performance.
- Standard LIBERO checkpoints are not necessarily valid for LIBERO-Safety.
- `env.check_success()` and safety cost/collision are separate. A task can be successful and unsafe.
- MuJoCo may emit `Too many contacts` warnings. Log them, but do not count them as Python runner failures unless an episode fails.

## Prompt For The Next Agent

Copy this prompt into the new agent:

```text
You are working in /home/ldx/lean-vla. Your sole objective is to reproduce the 50%+ success-rate regime reported for LIBERO-Safety, not to improve ProofAlign.

Read docs/reproduce_liberosafety_50_success_handoff.md first. Then inspect the official LIBERO-Safety and OpenVLA-OFT files referenced there.

Important current findings:
- Existing ProofAlign/Lean experiments are safety-gating pilots, not the official 50%+ reproduction.
- Standard OpenVLA-OFT checkpoint moojink/openvla-7b-oft-finetuned-libero-spatial only got 2/15 success even after aligning horizon=600, image rotation, gripper postprocessing, 256x256 images, 10 wait steps, and action chunking.
- Therefore the likely remaining issue is model/checkpoint/task-domain mismatch.

Your tasks:
1. Locate the exact source of the 50%+ LIBERO-Safety success claim and identify the model/checkpoint, eval script, metric definition, suites/levels/tasks, init states/trials/seeds, horizon, camera resolution, and action preprocessing.
2. Determine whether the 50%+ number is for OpenVLA-OFT or for another released model such as LIBERO-Safety/pi05_libero_safety.
3. If it is not OpenVLA-OFT, reproduce the official released model first using its intended eval stack.
4. If it is OpenVLA-OFT, find the Safety-trained checkpoint; do not reuse the standard LIBERO-Spatial checkpoint unless the official source says that is the model.
5. First run a 1-task smoke with the official protocol, then the 15-episode stratified sample (suites affordance/obstacle_avoidance/human_safety/obstacle_avoidance_human/reasoning_safety, task ids 0,7,14, init_state_id=0), then scale up only if the sample is plausible.
6. Save all commands, configs, raw JSON/log outputs, and a concise metrics.md under a new results directory.

Use the shared runtime:
source scripts/env_vla.sh
export LIBERO_SAFETY_ROOT=$PWD/external/LIBERO-Safety
export PYTHONPATH="$PWD:$PWD/src:$PWD/external/openvla-oft"

Use GPU/rendering settings that have worked:
CUDA_VISIBLE_DEVICES=4,5
MUJOCO_EGL_DEVICE_ID=5

Do not leave uv.lock changed by uv run; if it changes only registry URLs, restore it with:
git show HEAD:uv.lock > uv.lock

Report clearly whether the 50%+ claim was reproduced, partially reproduced, or blocked, and why.
```
