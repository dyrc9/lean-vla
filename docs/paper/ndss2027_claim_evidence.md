# NDSS 2027 claim--evidence and artifact map

Last audited: 2026-08-07. This file is local project material and is not part of
the Overleaf synchronization manifest.

The executable check is `scripts/audit_ndss2027_paper_claims.py`. It derives
the final per-arm risk table from frozen episode traces instead of trusting
numbers transcribed into prose.

## Claim map

| Paper claim | Frozen or executable evidence | Audit status |
|---|---|---|
| SABER attack-risk measurement: 240/240 valid, 39/86 risk transitions, 45.35%, cluster CI [32.93%, 57.78%]. Historical protocol classification: 50% preregistered gate non-pass (`confirmatory_attack_foundation_nonpass`). | `experiments/saber_confirmatory_preregistration_v1.json`, the M2 producer/victim protocols, and `docs/current_status_and_roadmap.md` | The active paper reports the observed ASR as a measured baseline rather than a binary reproduction claim; this audit row preserves the historical reproduction protocol and classification. The raw M2 fresh roots are not present in this checkout and must be restored before offering an artifact for RQ1. |
| L1 checker-relative authorization and advisory progress semantics | `src/proofalign/semantic_integrity.py`, semantic qualification protocols/results, and the negative integrity tests | Bound in the design/implementation text; no complete-semantic-verifier claim. |
| L2a nonce/digest/receipt/effect transaction invariants | `lean/ProofAlign.lean`, `lean/ProofAlign/IntegrityCore.lean`, `lean/ProofAlign/SemanticIntegrityCore.lean`, and Python negative integrity tests | Appendix A lists the exact `ProofAlign.SemanticIntegrityCore` theorem names. Lean proves whole-command and typed ordered-step authorization binding, one-use consumption, same-authorization receipts, indexed applied-step equality, fail-closed evidence, and phase advance. Python additionally checks contiguous receipt indices against `authorization.action_at(i)`. Python canonical tuple/serializer refinement and guard/controller configuration remain outside the typed Lean identity. |
| Canonical action identity | `src/proofalign/digests.py` and `src/proofalign/integrity_v4_models.py` | Paper now states the implemented domain exactly: finite Python-float values plus proposal shape in schema-tagged, key-sorted, whitespace-free UTF-8 JSON. It does not claim preservation of raw ndarray dtype, endianness, or memory bytes. |
| L2a focused runtime fault injection: 69/69 tests pass | `uv run pytest -q tests/test_integrity_v4_runtime.py tests/test_l2_online_arm_runtime.py tests/test_integrity_prototype.py tests/test_recovery_runtime_v12.py tests/test_semantic_online_runner.py` | Re-executed locally on 2026-08-06. Covers stale bindings, command/sink substitution, replay, receipts/effects, incomplete transactions, phase advance, and trusted-sink limitations. |
| Final clean task success and official-unsafe counts | v15.14 clean protocol and `results/...20260807_fresh1/pilot_evidence.json` | Executably checked. |
| Final attacked task success, official unsafe, violation episodes, crossing steps, and joint-limit steps | v15.14 attacked fresh2 protocol, `attacked_qualification_evidence.json`, and all 72 frozen episode JSON traces | Executably re-derived per arm and checked. |
| Attack forwarding, prompt digest, pair identity, force, prediction error, latency, deadlines, and 76 checksums | attacked fresh2 evidence plus `SHA256SUMS` | Executably checked. |
| Fresh1 run-integrity non-pass and fresh2-only forwarding fix | attacked fresh1/fresh2 protocols, manifests, and evidence | Disclosed in the evaluation; fresh1 outcomes are excluded from the result table. |
| Final population and attack-record transplant: six pairs per suite; exact same original task; different initialization; task-text-only transplant; no victim outcome or best-of-$N$ used in record generation | v15.14 clean fresh1 and attacked fresh2 protocols | Executably checked against all 18 workloads and attack records; disclosed in the final-study setup. |
| ActionBlock interface ablations: nested-prefix availability H=2/5/10 is 0/45, 17/45, 36/45; fixed-H10 cumulative K=1/2/4 availability is 35/45, 35/45, 36/45 | `experiments/proofalign_four_arm_v4_l1_block10_terminal_summary.json` and `experiments/proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json` | Frozen auxiliary evidence. Both studies are matched, zero-dispatch, and no-task-outcome; they support only initial checker-availability claims and are not pooled with final four-arm outcomes. The two terminal summaries and protocol/checksum bindings are present, but their raw result roots are absent from this checkout and must be restored for row-level artifact reproduction. |
| Execution platform and screening-latency boundary | clean/attacked `run_manifest.json`, frozen episode constants, and `scripts/run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery.py` | Two distinct 48-GiB RTX 6000 Ada GPUs and driver are recorded.  The paper defines screening latency as mechanism-only and excludes policy inference and actual dispatch. |
| Four MuJoCo QACC warnings on one pair, one per arm | `attacked_qualification_evidence.json:mujoco_warning_audit` | Retained and disclosed; no episode was removed. |

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
