# L1 task-conditioned successor held-out handoff

- Source commit at finalization: `2846e2350cfe705710e0963058e7c9aa39cb9410`
- Held-out analysis: `results/proofalign_l1_task_conditioned_v4_heldout_analysis_20260819.json` (`febff26f4689fb179f6b08487cb705518be50f975f93b7d759f272da3c1f2f40`)
- Clean protocol: `experiments/proofalign_l1_task_conditioned_v4_heldout_clean_protocol_20260819.json` (`3747c23b0d6c64d1b587e431f770ba1052d509bf519160ab4ff92aca1792ce02`)
- Attacked protocol: `experiments/proofalign_l1_task_conditioned_v4_heldout_attacked_protocol_20260819.json` (`1ef28d4d68dc3eccf9872cc7eccb8304d2c086ada93777e464b391d14c25f49b`)
- Raw clean root: `results/proofalign_l1_task_conditioned_v4_heldout_clean_20260819_fresh1`
- Raw attacked root: `results/proofalign_l1_task_conditioned_v4_heldout_attacked_20260819_fresh1`
- Episode count: `960`
- Clean/attacked pairs: `480`
- Terminal exceptions retained conservatively: `0`
- Qualified no-dispatch aborts: `60` (zero rejected ActionBlock dispatches by construction and qualification).
- Generated artifact root: `results/proofalign_l1_task_conditioned_v4_heldout_handoff_20260819`
- Risk rule: unchanged from the 45.35% SABER baseline.
- Historical fixed-86 cohort overlap: `0`; fixed-cohort estimate available: `False`.
- Outcome handling: no held-out tuning, filtering, retry, or sample removal.
- Paper/Overleaf: not modified by this experiment handoff.

Use `generated_tables.md` for the reported values and `summary.json` / the bound analysis for machine-readable evidence. Verify `SHA256SUMS` before integration.
