# CPU handoff notes — 2026-07-13

Scope: fallback observation-completeness repair and non-GPU verification from
`docs/gpu_handoff_20260713.md`.

Starting revision: `1e355d4f25109d7c867e87baf054cfb5d322e0a7`.

## Repair

- Fallback postconditions now record the exact observations required by the active
  `SafetySpec` and mission hard invariants.
- Unknown human/obstacle clearance signals are ignored only when those signals are
  irrelevant to the active mission.
- Human-safety and obstacle-avoidance missions still fail closed when their required
  clearance observation is unavailable.
- The typed fallback evaluation digest and switch-receipt integrity check bind the
  required-observation set.

## Verification

- Targeted regression: `59 passed`.
- Full pytest: `203 passed, 1 skipped` in 109.52 seconds.
- Lean: `lake build ProofAlign` completed successfully (12 jobs).
- `git diff --check`: passed.
- Python: 3.12.9.
- Lean: 4.24.0; Lake: 5.0.0-src+797c613.

## GPU boundary

No GPU rollout or calibration was run. The user explicitly narrowed this handoff to
work that does not require a GPU after the configured remote GPU hosts proved
unavailable. In particular, this directory does not satisfy or replace:

- the 10 Hz single-prefix Lean GPU probe;
- fallback receipt `succeeded=true` on a real LIBERO-Safety rollout;
- the 3--5 prefix clean calibration;
- GPU policy/EGL placement or latency measurements.

No 60-episode, SABER, Phantom, or 20 Hz deadline-relaxation experiment was started.
