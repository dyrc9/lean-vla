#!/usr/bin/env bash
set -euo pipefail

# One clean pi0.5 episode followed by one CTDA Lean slow-interlock episode.
# The CTDA run is deliberately not described as real-time enforcement.

WORKSPACE="${WORKSPACE:-$(pwd)}"
OPENPI_ROOT="${OPENPI_ROOT:-$WORKSPACE/external/openpi}"
LIBERO_SAFETY_ROOT="${LIBERO_SAFETY_ROOT:-$WORKSPACE/external/LIBERO-Safety}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-/data0/ldx/libero_safety_models/pi05_libero_safety}"
PROOFALIGN_UV="${PROOFALIGN_UV:-uv}"
LIBERO_CONFIG_PATH="${LIBERO_CONFIG_PATH:-$HOME/.libero}"
LIBERO_CONFIG_FILE="$LIBERO_CONFIG_PATH/config.yaml"
VLA_GPU="${VLA_GPU:?set VLA_GPU to the physical policy GPU id}"
EGL_GPU="${EGL_GPU:?set EGL_GPU to the physical MuJoCo EGL GPU id}"

SUITE="${SUITE:-affordance}"
TASK_ID="${TASK_ID:-2}"
INIT_STATE_ID="${INIT_STATE_ID:-0}"
SEED="${SEED:-7}"
POLICY_SEED="${POLICY_SEED:-0}"
MAX_STEPS="${MAX_STEPS:-30}"
MAX_CHUNK_STEPS="${MAX_CHUNK_STEPS:-5}"
CONTROL_FREQ="${CONTROL_FREQ:-20}"
CTDA_LEAN_TIMEOUT_SECONDS="${CTDA_LEAN_TIMEOUT_SECONDS:-10}"
RUN_ROOT="${RUN_ROOT:-$WORKSPACE/results/remote_gpu_smoke}"
SMOKE_MODE="${SMOKE_MODE:-both}"

case "$SMOKE_MODE" in
  clean|ctda-lean-kernel|both) ;;
  *) echo "SMOKE_MODE must be clean, ctda-lean-kernel, or both" >&2; exit 2 ;;
esac

mkdir -p "$RUN_ROOT"
export LIBERO_SAFETY_ROOT
export LIBERO_CONFIG_PATH
export PYTHONPATH="$WORKSPACE:$WORKSPACE/src:$LIBERO_SAFETY_ROOT:$OPENPI_ROOT/src:$OPENPI_ROOT/packages/openpi-client/src"
export CUDA_VISIBLE_DEVICES="$VLA_GPU,$EGL_GPU"
export MUJOCO_EGL_DEVICE_ID="$EGL_GPU"

preflight_args=(
  python3 "$WORKSPACE/scripts/remote_gpu_preflight.py"
  --workspace "$WORKSPACE"
  --openpi-root "$OPENPI_ROOT"
  --libero-safety-root "$LIBERO_SAFETY_ROOT"
  --checkpoint-dir "$CHECKPOINT_DIR"
  --libero-config "$LIBERO_CONFIG_FILE"
  --uv "$PROOFALIGN_UV"
  --vla-gpu "$VLA_GPU"
  --egl-gpu "$EGL_GPU"
  --run-verification
  --output "$RUN_ROOT/preflight.json"
)
"${preflight_args[@]}"

if [[ "$SMOKE_MODE" == "clean" || "$SMOKE_MODE" == "both" ]]; then
  CUDA_VISIBLE_DEVICES="$VLA_GPU,$EGL_GPU" \
  MUJOCO_EGL_DEVICE_ID="$EGL_GPU" \
  "$PROOFALIGN_UV" --project "$OPENPI_ROOT" run python \
    "$WORKSPACE/scripts/run_liberosafety_pi05_openpi_eval.py" \
    --checkpoint-dir "$CHECKPOINT_DIR" \
    --openpi-config pi05_libero \
    --suites "$SUITE" \
    --task-ids "$TASK_ID" \
    --init-state-ids "$INIT_STATE_ID" \
    --max-steps "$MAX_STEPS" \
    --num-steps-wait 10 \
    --env-img-res 256 \
    --resize-size 224 \
    --replan-steps 5 \
    --sample-steps 10 \
    --seed "$SEED" \
    --policy-seed "$POLICY_SEED" \
    --render-gpu-device-id "$EGL_GPU" \
    --continue-on-error \
    --output-dir "$RUN_ROOT/clean"
fi

if [[ "$SMOKE_MODE" == "ctda-lean-kernel" || "$SMOKE_MODE" == "both" ]]; then
  CTDA_FALLBACK_WITNESS="${CTDA_FALLBACK_WITNESS:?set a live task-bound v2 fallback witness}"
  CTDA_FALLBACK_WITNESS_SHA256="${CTDA_FALLBACK_WITNESS_SHA256:?pin the fallback witness SHA-256}"
  if [[ -z "${POLICY_CONFIG:-}" ]]; then
    POLICY_CONFIG="$(python3 -c \
      'import json, sys; print(json.dumps({"checkpoint_dir": sys.argv[1], "openpi_root": sys.argv[2], "max_actions_per_call": 5}))' \
      "$CHECKPOINT_DIR" "$OPENPI_ROOT")"
  fi

  CUDA_VISIBLE_DEVICES="$VLA_GPU,$EGL_GPU" \
  MUJOCO_EGL_DEVICE_ID="$EGL_GPU" \
  "$PROOFALIGN_UV" --project "$OPENPI_ROOT" run python \
    "$WORKSPACE/scripts/run_libero_online_batch.py" \
    --suites "$SUITE" \
    --task-ids "$TASK_ID" \
    --init-state-ids "$INIT_STATE_ID" \
    --max-steps "$MAX_STEPS" \
    --max-chunk-steps "$MAX_CHUNK_STEPS" \
    --continue-on-replan \
    --ctda \
    --ctda-fallback-witness "$CTDA_FALLBACK_WITNESS" \
    --ctda-fallback-witness-sha256 "$CTDA_FALLBACK_WITNESS_SHA256" \
    --ctda-evidence-mode local-simulator-exact-allowlist \
    --ctda-evaluator ctda-lean-kernel \
    --ctda-artifact-dir "$RUN_ROOT/ctda_kernel_artifacts" \
    --ctda-lean-timeout-seconds "$CTDA_LEAN_TIMEOUT_SECONDS" \
    --policy experiments.libero_openpi_plugin:create_policy \
    --policy-config "$POLICY_CONFIG" \
    --warmup-steps 0 \
    --seed "$SEED" \
    --camera-height 256 \
    --camera-width 256 \
    --render-gpu-device-id "$EGL_GPU" \
    --control-freq "$CONTROL_FREQ" \
    --horizon 1000 \
    --output-dir "$RUN_ROOT/ctda_lean" \
    --summary "$RUN_ROOT/ctda_lean_summary.json" \
    --failure-jsonl "$RUN_ROOT/ctda_lean_failures.jsonl"
fi

(
  cd "$RUN_ROOT"
  find . -type f ! -name SHA256SUMS -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum > SHA256SUMS
)
echo "Remote GPU smoke artifacts: $RUN_ROOT"
