# NDSS 2027 simulated Round-1 review

Last updated: 2026-08-19.  This is an internal submission audit, not part of
the anonymous paper or the Overleaf synchronization manifest.

## Overall assessment

**Provisional recommendation: weak accept / minor revision, conditional on
the paper retaining its present claim scope.**  The work has a recognizable
systems-security object: an exact continuous VLA action block is assessed
against an independently trusted task context and then bound through one-use
authorization, dispatch receipts, effects, and state-triggered containment.
The implementation, negative integrity tests, Lean transaction model, and
paired simulator study support that narrow claim.  The evidence does not
support general VLA robustness, real-robot safety, hardware attestation, or a
complete semantic verifier.

**Second-pass content verdict.**  No unsupported central numerical claim or
internal security-property contradiction remains in the current draft.  The
attack setup now exposes the outcome-blind producer budget (one record per
base pair, seed 83, eight tool turns, 200 edited characters, no replacement or
best-of-$N$), and the complete-population stress states the positive covered
result quantitatively: all 237 valid attacked L2-on runs have zero joint-limit
steps, versus 4,960/2,452 steps in the valid VLA/L1 controls.  The broad
four-channel nonreduction remains visible, so this strengthens the
property-specific effectiveness claim without converting it into a general
safety claim.

Indicative Round-1 scores:

| Dimension | Score | Basis |
|---|---:|---|
| NDSS topic fit | 4/5 | Concrete reference monitor, explicit TCB, implementation, attack evaluation, and CPS execution boundary |
| Novelty | 3/5 | Novelty is the protected object and cross-layer composition, not any individual checker, nonce, shield, or attestation primitive |
| Technical correctness | 4/5 | Claims are conditional and evidence-bound; the Python-to-Lean and guard/controller refinement gap is disclosed |
| Evaluation | 3/5 | Full 120-unit rerun and integrity suite, but the all-valid dependency failed; evidence still covers one checkpoint, one benchmark, and one non-adaptive attack family |
| Presentation | 4/5 | Abstract/introduction expose the three obligations; figures and tables make the runtime order and evidence boundary inspectable |
| Reproducibility | 3/5 | Final-study claims are executable and checksum-bound; an RQ1-complete public artifact still needs the missing immutable M2 roots |

## Likely reviewer objections and current answer

### 1. “The components are individually known; where is the novelty?”

The paper locates novelty in the protected object and cross-layer preservation
chain, not in a first checker, nonce, shield, or attestation primitive.  Table I
compares that object and evidence boundary with StruQ/SecAlign,
AttriGuard/MATE, SEAL/CoVer, CaMeL/ACE/IsolateGPT/SAGA, CPS attestation, and
TAT.  The Design section also supplies the missing orthogonality argument:
the soda-to-plate versus farthest-fixture running example shows that L2a can
faithfully dispatch a task-divergent command, L2b can contain it without making
it task-compatible, and an L1 checker-relative verdict alone establishes
neither sink identity nor joint-side containment.

### 2. “Why are there no numerical comparisons with other VLA safety systems?”

Evaluation now states the baseline/ablation logic explicitly.  VLA-only is the
unchanged runtime baseline; L1-only and L2-only isolate mechanism roles; Dual
tests composition.  SafeVLA changes training, SAFE learns rollout failure,
and SEAL/CoVer require plan, candidate, or learned-score interfaces absent
from the registered single-proposal $K=1$ interface.  The paper does not
turn these interface differences into a leaderboard claim.

### 3. “The evaluation is too narrow.”

This is the principal residual acceptance risk.  The final evidence covers
one OpenPI pi0.5 checkpoint, LIBERO-Safety, one frozen SABER instruction attack
family, and 120 seed-specific units.  The attack is not defense-aware.  The
paper therefore claims simulator-qualified containment for this frozen setting
and uses the complete 240-episode protocol as a separate attack-risk
measurement.  The four-arm rerun attempts all 960 cells, but only 475/480 per
condition produce complete traces and the registered all-valid requirement is
not met.  Its comparisons are consequently nonconfirmatory.  More policies,
attacks, seeds, trusted perception, and real robots are required to expand the
claim beyond the present one.

### 4. “The trusted branch uses privileged geometry and is unrealistic.”

The threat model requires an independently protected task source and trusted
observation tap; without them the semantic claim does not apply.  The final
selector is expressly a privileged benchmark FSM qualified on a finite
corpus, not a camera-only perception contribution.  Deployment would need a
signed job artifact plus trusted capture or redundant/hardware-backed sensing.

### 5. “L2a and L2b are conflated.”

The four-arm experiment estimates their combined L2 treatment only.  Physical
SABER outcomes primarily exercise L2b.  L2a is separately supported by 69
focused fault-injection tests and Lean-checked transaction theorems.  The
paper does not claim an independent causal effect for either subcomponent from
the four-arm result.

### 6. “The formal claims do not cover the implementation or robot.”

Correct.  Lean checks finite authorization, receipt, effect, and phase
relations.  It now types the ordered action-digest list and proves that each
bound receipt's index resolves to its applied-step digest; Python additionally
checks index contiguity against `authorization.action_at(i)`.  Lean does not
validate Python canonical tuple/serializer refinement, language,
selector/checker correctness, sensing, simulator fidelity, or the current
guard/controller configuration.
The paper consistently says “Lean-checked execution transaction semantics,”
not “formally verified robot safety.”

### 7. “Why is the 45.35% attack-risk result reported separately?”

The complete protocol measures 39/86 clean-eligible units with a new risk
transition (45.35%, cluster-bootstrap CI [32.93%, 57.78%]) in a separate set of
rollouts.  The four-arm experiment reruns the same 120 population identities;
it does not reuse or backfill the 39/86 result.  Task success uses all 120 units,
the broad-risk comparison uses the common 75-unit clean-safe complete-case
cohort, and joint-limit steps use complete attacked traces.  These denominators
answer different questions and are not pooled.  On the common cohort, counts
are 38/42/36/43 and the minimum paired $p$-value is 0.3833.  All 237 complete
attacked L2-on traces nevertheless contain zero joint-limit steps, versus
4,960/2,452 in the complete VLA/L1 controls.  The latter is a property-specific
valid-trace diagnostic, not a repair of the failed all-valid dependency or a
general safety result.

### 8. “Does L1 improve semantic robustness?”

The final data do not support that claim.  Under attack, five VLA failures
become L1 successes, but 14 VLA successes become L1 failures, for a net loss of
nine tasks.  Nine losses terminate at an explicit checker rejection and five at
the episode step cap.  L1's supported property is narrower: all 17 attacked
checker rejections remain unauthorized and undispatched at the decision point.
The paper therefore reports checker-relative enforcement together with its
observed availability cost, not complete semantic verification or improved
task robustness.

## Submission decision checklist

The manuscript is technically ready for upload when all of the following are
true:

- the final HotCRP paper number replaces `24xxxx` in the first-page DOI;
- the Generative-AI Disclosure uses the exact product/model label visible at
  submission time;
- the complete author list and conflicts are frozen in HotCRP;
- `python3 scripts/check_ndss2027_submission.py --final` passes; and
- the uploaded PDF is re-downloaded and compared with the local SHA-256.

The anonymous experiment artifact is intentionally deferred until the paper
version is stable and does not block the Fall paper upload.
