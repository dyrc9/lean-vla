# NDSS 2027 claim--evidence and artifact map

Last audited: 2026-08-19. This file is local project material and is not part of
the Overleaf synchronization manifest.

The executable check is `scripts/audit_ndss2027_paper_claims.py`. It derives
the final per-arm risk table from frozen episode traces instead of trusting
numbers transcribed into prose.

## Claim map

| Paper claim | Frozen or executable evidence | Audit status |
|---|---|---|
| SABER attack-risk measurement: 240/240 valid, 39/86 risk transitions, 45.35%, cluster CI [32.93%, 57.78%]. The outcome-blind producer uses seed 83, one record per base pair, at most eight tool turns and 200 edited characters, no replacement, and no best-of-$N$. Historical protocol classification: 50% preregistered gate non-pass (`confirmatory_attack_foundation_nonpass`). | `experiments/saber_confirmatory_preregistration_v1.json`, the M2 producer/victim protocols, and `docs/current_status_and_roadmap.md` | The active paper reports successful reproduction through the observed 39/86 transition count and 45.35% attack-success rate. This audit row preserves the historical 50% gate classification. The archived raw M2 roots remain part of the artifact-restoration checklist for RQ1. |
| Final complete-population four-arm experiment: 960/960 artifacts present and 475/480 valid per condition; terminal classification `four_arm_terminal_invalid_conservative`. Clean/attacked task-success counts for VLA/L1/L2/Dual are 85/73, 78/64, 86/73, and 78/64 out of 120. The common 75-unit clean-safe complete-case cohort has 38/42/36/43 risk transitions; arm-specific estimates are 45/85, 42/78, 43/86, and 43/78. The minimum exact paired McNemar $p$ is 0.3833. Valid attacked rows are 119/119/119/118, with 4,960/2,452/0/0 joint-limit steps. | `results/proofalign_remote_full120_llm_analysis_20260818_fresh2/{clean_terminal_analysis.json,attacked_terminal_analysis.json,risk_transition_analysis.json,clean_episodes_ledger.jsonl,attacked_episodes_ledger.jsonl,SHA256SUMS}` and the ledger-derived checks in `scripts/audit_ndss2027_paper_claims.py` | This is the only four-arm result used by the active paper. The preregistered all-valid dependency failed, so it is nonconfirmatory. The common 75-unit comparison aligns denominators but conditions on clean outcomes in all arms and is not a population-wide causal effect. All 237 valid attacked L2-on rows have zero joint-limit steps, while the broader four-channel endpoint does not fall. |
| Full-population L2 runtime diagnostics: 78,434 performed screens over 237 valid attacked L2-on runs; maximum 458.99 ms, linear-interpolation p95 23.47 ms, and 323/78,434 (0.41%) above 100 ms. Maximum post-step force proxy is 229.5709 and maximum prediction/execution margin error is $2.41\times10^{-5}$ rad. | Checksum-verified raw episode paths bound by `attacked_episodes_ledger.jsonl`; protocol in `experiments/proofalign_remote_full120_llm_attacked_protocol_20260818.json`; derived fact pack in `docs/paper/full120_four_arm_result_integration.md` | The active paper reports the full distribution, including the long-tail maximum, and does not claim hard-real-time compliance. Threshold classifications remain in audit material. |
| L1 checker-relative authorization and advisory progress semantics | `src/proofalign/semantic_integrity.py`, semantic qualification protocols/results, and the negative integrity tests | Bound in the design/implementation text; no complete-semantic-verifier claim. |
| L2a nonce/digest/receipt/effect transaction invariants | `lean/ProofAlign.lean`, `lean/ProofAlign/IntegrityCore.lean`, `lean/ProofAlign/SemanticIntegrityCore.lean`, and Python negative integrity tests | The executable audit checks the frozen theorem inventory directly against `ProofAlign.SemanticIntegrityCore`. Lean proves whole-command and typed ordered-step authorization binding, one-use consumption, same-authorization receipts, indexed applied-step equality, fail-closed evidence, and phase advance. Python additionally checks contiguous receipt indices against `authorization.action_at(i)`. Python canonical tuple/serializer refinement and guard/controller configuration remain outside the typed Lean identity. |
| Canonical action identity | `src/proofalign/digests.py` and `src/proofalign/integrity_v4_models.py` | Paper now states the implemented domain exactly: finite Python-float values plus proposal shape in schema-tagged, key-sorted, whitespace-free UTF-8 JSON. It does not claim preservation of raw ndarray dtype, endianness, or memory bytes. |
| L2a focused runtime fault injection: 69/69 tests pass | `uv run pytest -q tests/test_integrity_v4_runtime.py tests/test_l2_online_arm_runtime.py tests/test_integrity_prototype.py tests/test_recovery_runtime_v12.py tests/test_semantic_online_runner.py` | Re-executed locally on 2026-08-06. Covers stale bindings, command/sink substitution, replay, receipts/effects, incomplete transactions, phase advance, and trusted-sink limitations. |
| ActionBlock interface ablations: nested-prefix availability H=2/5/10 is 0/45, 17/45, 36/45; fixed-H10 cumulative K=1/2/4 availability is 35/45, 35/45, 36/45 | `experiments/proofalign_four_arm_v4_l1_block10_terminal_summary.json` and `experiments/proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json` | Frozen auxiliary evidence. Both studies are matched, zero-dispatch, and no-task-outcome; they support only initial checker-availability claims and are not pooled with final four-arm outcomes. The two terminal summaries and protocol/checksum bindings are present, but their raw result roots are absent from this checkout and must be restored for row-level artifact reproduction. |
| Execution platform and screening-latency boundary | Full-population clean/attacked raw manifests, frozen episode constants, and `scripts/run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery.py` | Two distinct 48-GiB RTX 6000 Ada GPUs and driver are recorded.  The paper defines screening latency as mechanism-only and excludes policy inference and actual dispatch. |

## Anonymous artifact package

An artifact submission should contain only reviewer-safe paths and metadata:

1. the three Lean sources, `lakefile.lean`, and `lean-toolchain`;
2. the semantic checker/contract/receipt implementation and focused tests;
3. frozen clean and attacked fresh2 protocols, manifests, terminal evidence,
   episode traces, and checksum files;
4. the attacked fresh1 non-pass protocol/evidence needed to explain run validity;
5. the M2 producer/victim protocols and restored raw M2 fresh roots;
6. a one-command verifier that runs Lean tests, checksum validation, and
   `scripts/audit_ndss2027_paper_claims.py` without network access.

Before packaging, rewrite or remove machine-specific checkpoint and BDDL paths
embedded in episode metadata and verify that
the rewrite does not alter frozen scientific fields. Do not publish the
current raw result tree as an anonymous artifact without that scrub.

## Remaining artifact blocker

The locally referenced directories
`results/saber_confirmatory_producer_m2_20260727_fresh1` and
`results/saber_confirmatory_victim_m2_20260727_fresh1` are absent from this
checkout. The paper can be compiled and its final-study claims can be audited,
but an RQ1-complete artifact cannot be released until those immutable roots
are restored and their checksums revalidated.
