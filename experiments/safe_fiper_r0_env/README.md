# SAFE / FIPER R0 isolated environments

These environments follow `docs/remote_execution.md`: the Conda-provided uv is
the only environment manager, caches and environments live under `/data0/ldx`,
and frozen source checkouts remain under the main repository's ignored
`external/{SAFE,SAFE-openpi,fiper}` directories. The temporary reproduction
worktree has been removed.

Canonical locations:

- uv: `/home/ldx/.conda/envs/proofalign-libero/bin/uv` (0.11.25)
- uv cache/Python installs: `/data0/ldx/uv-cache`, `/data0/ldx/uv-python`
- SAFE detector: `/data0/ldx/uv-envs/safe-r0` (Python 3.10.20)
- SAFE OpenPI server: `/data0/ldx/uv-envs/safe-r0-openpi` (locked Python 3.11.15)
- SAFE LIBERO client: `/data0/ldx/uv-envs/safe-r0-libero-client` (Python 3.8.20)
- FIPER: `/data0/ldx/uv-envs/fiper-r0` (Python 3.11.15)
- official SAFE π0: `/data0/ldx/safe-fiper-r0/openpi/openpi-assets/checkpoints/pi0_libero`
- official FIPER data: `/data0/ldx/safe-fiper-r0/fiper/extracted/data_all`

The pre-existing π0.5 models under `/data0/ldx/saber-cache/.../pi05_libero`
and `/data0/ldx/libero_safety_models/pi05_libero_safety` are different assets
and are intentionally left untouched.

```bash
source scripts/env_vla.sh
export UV_PYTHON_INSTALL_DIR=/data0/ldx/uv-python

"$PROOFALIGN_UV" venv --python /home/ldx/.conda/envs/proofalign-libero/bin/python \
  /data0/ldx/uv-envs/safe-r0
"$PROOFALIGN_UV" pip install --index-strategy unsafe-best-match \
  --python /data0/ldx/uv-envs/safe-r0/bin/python \
  --requirement experiments/safe_fiper_r0_env/safe_requirements.txt
"$PROOFALIGN_UV" pip install --python /data0/ldx/uv-envs/safe-r0/bin/python \
  --no-deps --editable external/SAFE

"$PROOFALIGN_UV" venv --python 3.8 /data0/ldx/uv-envs/safe-r0-libero-client
"$PROOFALIGN_UV" pip sync --index-strategy unsafe-best-match \
  --python /data0/ldx/uv-envs/safe-r0-libero-client/bin/python \
  external/SAFE-openpi/examples/libero/requirements.txt \
  external/SAFE-openpi/third_party/libero/requirements.txt \
  --extra-index-url https://download.pytorch.org/whl/cu113
"$PROOFALIGN_UV" pip install \
  --python /data0/ldx/uv-envs/safe-r0-libero-client/bin/python \
  --editable external/SAFE-openpi/packages/openpi-client \
  --editable external/SAFE-openpi/third_party/libero

UV_PROJECT_ENVIRONMENT=/data0/ldx/uv-envs/safe-r0-openpi \
  GIT_LFS_SKIP_SMUDGE=1 \
  "$PROOFALIGN_UV" --project external/SAFE-openpi sync --frozen

"$PROOFALIGN_UV" venv --python 3.11.15 /data0/ldx/uv-envs/fiper-r0
"$PROOFALIGN_UV" pip install --index-strategy unsafe-best-match \
  --python /data0/ldx/uv-envs/fiper-r0/bin/python \
  --requirement experiments/safe_fiper_r0_env/fiper_requirements.txt
```

Do not use the existing pi0.5 checkpoints for SAFE R0.  The frozen upstream
protocol requires OpenPI `pi0_libero`, downloaded through the frozen
`external/SAFE-openpi` project.  FIPER R0 uses the official published rollout
archive and does not need an OpenPI checkpoint.

The SAFE client also needs `NUMBA_CACHE_DIR` on a writable filesystem and this
robosuite release expects the physical EGL id, for example
`CUDA_VISIBLE_DEVICES=2 MUJOCO_EGL_DEVICE_ID=2`. The audited launcher sets both.

FIPER runtime outputs must not be written into the frozen extracted-data tree.
The audited launcher creates `RUN/runtime_data`: each task directory contains
only a `rollouts` symlink to the official data, while processed tensors, RND
checkpoints, and results are written beside that link. Its temporary
`external/fiper/data` symlink is removed when the launcher exits.

SAFE's upstream instructions permit current compatible detector dependencies;
SciPy is pinned to 1.15.3 because the newer 1.17 line requires Python 3.11,
while the upstream SAFE detector environment is Python 3.10.
