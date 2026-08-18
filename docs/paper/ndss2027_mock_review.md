# NDSS 2027 simulated Round-1 review

Last updated: 2026-08-18.  This is an internal submission audit, not part of
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

Indicative Round-1 scores:

| Dimension | Score | Basis |
|---|---:|---|
| NDSS topic fit | 4/5 | Concrete reference monitor, explicit TCB, implementation, attack evaluation, and CPS execution boundary |
| Novelty | 3/5 | Novelty is the protected object and cross-layer composition, not any individual checker, nonce, shield, or attestation primitive |
| Technical correctness | 4/5 | Claims are conditional and evidence-bound; the Python-to-Lean and guard/controller refinement gap is disclosed |
| Evaluation | 3/5 | Strong paired/frozen protocol and integrity suite, but one checkpoint, one benchmark, one non-adaptive attack family, and 18 final pairs |
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
family, and 18 paired mechanism workloads.  The attack is not defense-aware.  The paper
therefore claims simulator-qualified containment for this frozen setting and
uses the complete 240-episode protocol as a separate attack-risk measurement.  More
policies, attacks, seeds, trusted perception, and real robots are required to
expand the claim beyond the present one.

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
transition (45.35%, cluster-bootstrap CI [32.93%, 57.78%]).  This is the
observed attack-risk baseline under the stated protocol.  The paired mechanism
study uses a different population and violation endpoint, so the two results
are not pooled or subtracted.  A defense-effect claim aligned to 45.35% requires
the planned 120-unit clean/attacked four-arm run.

### 8. “The utility noninferiority margin is too permissive.”

The -0.20 margin was frozen before final outcomes as a mechanism-qualification
tolerance of at most a 20-percentage-point task-success loss.  It is now
described as such and explicitly not treated as a deployment-derived utility
standard.  The observed registered contrasts are both zero in the frozen
paired sample; the paper avoids a population-level zero-utility-cost claim.

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
