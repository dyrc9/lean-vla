# GPU smoke notes — 2026-07-13

Environment: RTX 6000 Ada; policy GPU 4; MuJoCo EGL GPU 5; OpenPI
`pi05_libero`; checkpoint `/data0/ldx/libero_safety_models/pi05_libero_safety`.

## Verification

- Python: 199 passed, 1 skipped.
- Lean 4.24.0: `lake build ProofAlign` completed successfully (12 jobs).
- Diagnostic preflight: ready=true with `--allow-dirty`. This is not the clean-checkout
  reproducibility gate.

## Clean smoke

- Condition: affordance/task 2/init 0, seed 7, policy seed 0, 30 policy steps plus
  10 wait steps.
- Result: 1 completed episode, 0 runner failures, 0 cost/collision, max-steps stop.
- Artifact: `clean_v2/`.

## CTDA 20 Hz slow-interlock smoke

- One prefix was semantically and pre-dispatch verified by Lean and dispatched.
- `semantic=proven`, `prefix_pre=proven`, both parity-match and proof-verified.
- The observed-prefix request was refuted because the measured MuJoCo step exceeded
  the 50 ms authorized duration (about 77 ms in the final 20 Hz probe).
- This is a deadline miss and does not support a real-time enforcement claim.
- Artifact: `ctda_lean_v9/`, replay requests in `ctda_kernel_artifacts_v9/`.

## CTDA 10 Hz wiring probe

- This condition is a diagnostic slow-interlock probe, not the primary 20 Hz protocol.
- `semantic=proven` (1.107 s), `prefix_pre=proven` (0.910 s),
  `observed_prefix=proven` (0.818 s), `monitor_step=safe_pending` (0.784 s).
- All four requests have `proof_verified=true` and `parity_match=true`.
- The episode ended after one prefix with a pending mission obligation, so fail-closed
  termination invoked zero-hold fallback. The fallback remains over-conservative for
  absent affordance-suite human/obstacle observations and did not establish its typed
  postcondition.
- Artifact: `ctda_lean_v10_10hz/`, replay requests in
  `ctda_kernel_artifacts_v10_10hz/`.

## Current gate

Do not start the 60-episode batch yet. First calibrate the 20 Hz timing policy and
fallback observation completeness on clean episodes, then run a small multi-prefix
clean pilot to measure false block, unknown/deadlock, and stage latency.
