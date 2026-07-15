# SAFE / FIPER R0 runbook

This reproduction is isolated from the primary ProofAlign worktree.

- worktree: `/home/ldx/lean-vla/external/worktrees/safe-fiper-r0`
- branch: `exp/safe-fiper-r0`
- canonical uv: `/home/ldx/.conda/envs/proofalign-libero/bin/uv`
- caches and large artifacts: `/data0/ldx`

Run the read-only gate from the isolated worktree:

```bash
/home/ldx/lean-vla/.venv/bin/python \
  scripts/baseline_reproduction_preflight.py --workspace .
```

The target-specific readiness fields have different meanings:

- `safe_rollout`: exact source, checkpoint, tokenizer, server/client environments;
- `safe_detector`: additionally requires the validated 500-episode corpus;
- `fiper`: exact source, published data reports, and isolated environment.

Before every GPU execution, record a fresh inventory. Never infer availability
from an older manifest.

```bash
nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu \
  --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory \
  --format=csv,noheader
```

The launcher requires explicit GPU ids and refuses to reuse a result directory:

```bash
/home/ldx/lean-vla/.venv/bin/python scripts/run_safe_fiper_r0.py \
  --target safe-rollout --execute --run-dir /data0/ldx/safe-fiper-r0/safe/runs/NAME \
  --policy-gpu POLICY_ID --egl-gpu EGL_ID

/home/ldx/lean-vla/.venv/bin/python scripts/run_safe_fiper_r0.py \
  --target fiper --execute --run-dir /data0/ldx/safe-fiper-r0/fiper/runs/NAME \
  --policy-gpu GPU_ID
```

SAFE requires the physical EGL id in both `CUDA_VISIBLE_DEVICES` and
`MUJOCO_EGL_DEVICE_ID`. FIPER writes processed tensors and results to a fresh
runtime tree; its `rollouts` entries alone point to the frozen official data.

FIPER commit `13d79c5` uses the removed `np.bool` alias while leaving NumPy
unpinned. `scripts/run_fiper_compat.py` restores only `np.bool = np.bool_` before
executing the unchanged official entrypoint. The first unshimmed failure remains
under `/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-20260715`.
