# SAFE / FIPER R0 runbook

This reproduction is isolated from the primary ProofAlign worktree.

- worktree: `/home/ldx/lean-vla/external/worktrees/safe-fiper-r0`
- branch: `exp/safe-fiper-r0`
- canonical uv: `/home/ldx/.conda/envs/proofalign-libero/bin/uv`
- caches and large artifacts: `/data0/ldx`

## Status snapshot (2026-07-15 17:02 Asia/Shanghai)

The source, asset, environment, preflight, and launcher work is complete and
committed. The two official R0 executions are still in progress, so neither
baseline is classified as reproduced yet and neither is authorized for the
ProofAlign comparison table.

| Baseline | Current state | Auditable location | Next gate |
|---|---|---|---|
| SAFE | Official `pi0_libero_10` rollout generation is running; 175 of 500 env records existed at this snapshot. | `/data0/ldx/safe-fiper-r0/safe/runs/safe-pi0-libero10-r0-20260715` | Finish all 500 episodes, validate env/policy record counts and schemas, freeze the rollout tree, then run the full official detector matrix. |
| FIPER | The unchanged official entrypoint failed on the removed `np.bool` alias and is preserved. The compatibility run has passed that point and is still executing the official full pipeline. | failed: `/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-20260715`; active: `/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-compat1-20260715` | Wait for a terminal manifest, validate all task/seed/method results, then classify the official R0 reproduction. |

The counts above are a timestamped handoff snapshot, not a final metric. A log
mtime or a partially written output tree must never be interpreted as a pass.
The protocol JSON files remain the pre-execution registration; their
`official_run_results_observed` fields intentionally describe the moment the
protocol was frozen rather than the later runtime status.

## Existing assets: reuse, do not download again

All large inputs were already present and hash-frozen before these runs. The
launchers consume these local paths and generate only new run outputs:

- SAFE checkpoint: `/data0/ldx/safe-fiper-r0/openpi/openpi-assets/checkpoints/pi0_libero`
  (19 files, 12,014,131,888 bytes, frozen tree SHA-256 in
  `experiments/safe_r0_protocol.json`);
- SAFE tokenizer: `/data0/ldx/safe-fiper-r0/openpi/big_vision/paligemma_tokenizer.model`;
- FIPER official archive: `/data0/ldx/safe-fiper-r0/fiper/fiper_data.zip`
  (5,676,727,608 bytes, SHA-256 frozen in
  `experiments/fiper_r0_protocol.json`);
- FIPER extracted data: `/data0/ldx/safe-fiper-r0/fiper/extracted/data_all`
  (3,030 files, frozen tree SHA-256 in the protocol).

Do not run a downloader merely because a fresh worktree lacks an `upstream/`
entry or a run directory. Source checkouts live under this worktree; large
assets and uv environments deliberately live under `/data0/ldx` and are shared
by absolute path. If an asset check fails, compare its frozen digest and path
first. A redownload requires an explicit decision and a new protocol record.

## Environment ownership

Use the canonical uv binary, not whichever `uv` happens to be on `PATH`:

```bash
/home/ldx/.conda/envs/proofalign-libero/bin/uv --version
```

The resolved environments are reusable and must not be recreated while the
active processes are using them:

- SAFE detector: `/data0/ldx/uv-envs/safe-r0` (Python 3.10);
- SAFE OpenPI server: `/data0/ldx/uv-envs/safe-r0-openpi` (official uv lock,
  Python 3.11);
- SAFE LIBERO client: `/data0/ldx/uv-envs/safe-r0-libero-client` (Python 3.8);
- FIPER: `/data0/ldx/uv-envs/fiper-r0` (Python 3.11);
- uv cache: `/data0/ldx/uv-cache`;
- uv-managed Python installs: `/data0/ldx/uv-python`.

Exact resolved packages and imports are recorded in
`experiments/safe_fiper_r0_env/resolved_environments.json`. The requirements
files in the same directory are reconstruction inputs, not instructions to
reinstall an already validated environment.

## Source ownership

The ignored `upstream/` directory contains three isolated, clean checkouts:

- SAFE: `b6036abe07b2b2bb9996afb2c07f13d6a9f507c0`;
- SAFE OpenPI: `9c99ed53f6a0c9be93a1c63cee5792620777d96b`;
- FIPER: `13d79c5c3069def843e454787ff128defc249838`.

Merging this branch into the main repository does not move the large assets,
rewrite those source trees, or stop an already running process. Keep the
dedicated worktree until both runs have reached a terminal, validated state.

## Read-only preflight

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

## Terminal handoff checklist

After each process exits:

1. require a terminal `run_manifest.json` and preserve every earlier failed
   attempt;
2. rerun `baseline_reproduction_preflight.py` without mutation;
3. run the target-specific record/schema/result validator;
4. freeze output-tree hashes and exact hardware/software provenance;
5. update the project status with `reproduced_upstream` or
   `blocked_upstream`, never from a partial log;
6. only after an upstream pass, begin any pi0.5 adapter or unified fallback
   work as a separate, preregistered experiment.
