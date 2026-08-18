# NDSS 2027 Fall submission metadata

Updated on 2026-08-07 from the canonical LaTeX source.  This is a local
copy/paste sheet, not part of the Overleaf synchronization manifest.  The
official CFP now states that the Fall site opens on 15 August 2026 and links
<https://ndss27-fall.hotcrp.com/>.  Confirm the actual field names once the
site opens.

## Submission type and title

- Cycle: Fall
- Type: Technical paper
- Title: **ProofAlign: Cross-Layer Runtime Integrity for Embodied Vision–Language–Action Systems**

## Plain-text abstract

Vision–language–action (VLA) systems map language and multimodal observations
to continuous robot actions. At deployment, an online action chunk crosses
from model output into the execution stack without inherent evidence that it
is admissible for the current task, that later software preserves it, or that
its realization is qualified for the current robot state. Existing defenses
typically stop at model input or candidate selection, or begin from an already
trusted command, program, or reference trajectory.

We present ProofAlign, an inline consumer-side reference monitor that makes
the exact source ActionBlock the protected object. Under an explicit
trusted-task and observation assumption, L1 attaches a checker-relative
assessment to the block. L2a carries its identity through a fresh one-use
authorization, ordered dispatch, receipts, effects, and task-phase advance.
When a registered joint boundary triggers, L2b qualifies at most two temporary
virtual-guard configurations without changing or resampling the source
action. We formalize the composition as ProofAligned—checker-relative
eligibility, transaction alignment, and conditional containment—and use Lean
to machine-check its finite authorization, ordered-action, receipt, evidence,
and phase-transition relations.

Using SABER on a complete 120-unit attack-evaluation protocol, we measure 39 of
86 clean-eligible units as new risk transitions (45.35%, 95% base-pair
cluster-bootstrap CI: [32.93%, 57.78%]). A separate 144-episode paired four-arm
study contains 18 task/initialization pairs. Under attack, VLA-only
and L2-only succeed on 11/18 tasks, while L1-only and Dual succeed on 13/18;
their joint-limit violation-episode counts are 4/18, 1/18, 0/18, and 0/18,
respectively. Maximum screening latency is 39.79 ms (18.30 ms p95), with no
100 ms miss. The empirical studies run in LIBERO-Safety simulation; they do
not establish hardware attestation, hard-real-time operation, or general robot
safety.

## Recommended topics

Use the official topic wording where the form permits ranked selections:

1. **Primary:** Security and privacy of systems based on machine learning,
   federated learning, AI, and large language models.
2. **Secondary:** Security for cyber-physical systems (e.g., autonomous
   vehicles, industrial control systems).
3. **Additional:** Trustworthy computing software and hardware to secure
   networks and systems.
4. **If a fourth selection is useful:** Special problems and case studies,
   including tradeoffs between security, efficiency, cost, and ethics.

Suggested keywords: `vision-language-action`, `robot security`, `reference
monitor`, `execution integrity`, `trusted task`, `prompt injection`,
`cyber-physical systems`, `runtime verification`.

## Topic-fit statement

ProofAlign is a systems-security paper about the lifecycle of an online VLA
ActionBlock as it crosses into embodied execution. Its contribution is a
consumer-side reference monitor with an explicit TCB, a top-level
ProofAligned property, fail-closed transaction semantics, negative integrity
tests, and runtime physical containment. Machine learning supplies the
untrusted action proposal; the contribution is not a new VLA architecture or
training objective. The implementation, paired attack evaluation, and
Lean-checked transaction model directly address practical AI-system and
cyber-physical security.

## Ethics summary

The study evaluates a published instruction attack only in simulation and
does not issue adversarial commands to a physical robot. It retains the
observed attack ASR, severe residual L1 risk steps, all simulator warnings, and
the frozen reproducibility audit. The prototype is a research reference monitor, not a
replacement for certified machinery safeguards. No human-subject data or
high-impact undisclosed vulnerability is involved.

## Generative-AI disclosure summary

OpenAI Codex desktop app (GPT-5 model family; accessed August 2026) assisted
across all manuscript sections with drafting and editing prose and generated
the LaTeX/TikZ diagrams for Figs. 1--4 from author-supplied
system designs, experiment protocols, frozen results, and claim boundaries. It
did not conduct the reported experiments or select their outcomes. The authors
reviewed the generated text and diagrams and remain responsible for every
claim, number, citation, and artifact.

If the interface exposes a more precise model label at submission time, add it
here and in `sections/ai_disclosure.tex`. Do not infer an internal build label
that the product does not expose.

## Author and conflict freeze — required human input

The author list cannot be inferred from the anonymous repository.  Before the
deadline, the authors must provide and jointly verify:

- [ ] final author names, ordering, email addresses, affiliations, and
      countries;
- [ ] confirmation that no author exceeds the six-submission Fall-cycle cap;
- [ ] perpetual advisor/advisee conflicts for every author;
- [ ] current institutional conflicts;
- [ ] professional collaborations from the preceding two years;
- [ ] close personal relationships and any grey-area conflicts raised with
      the PC chairs;
- [ ] confirmation that no author will need to be added after the deadline;
- [ ] confirmation of no prohibited concurrent submission or major overlap
      with an NDSS 2027 Summer rejection; and
- [ ] agreement not to broadly advertise the paper during review.

Do not copy author or conflict data into the anonymous PDF.

## Submission-time identifiers

- HotCRP submission number: **pending**
- First-page DOI suffix: replace `24xxxx` with `24` followed by the Fall paper
  number padded with leading zeros as specified by the NDSS template.
- PDF filename for upload: choose a neutral identifier after HotCRP creates the
  submission; do not include author or institution names.

After these fields and any more precise visible AI label are filled, run:

```sh
python3 scripts/check_ndss2027_submission.py --final
```

The anonymous experiment artifact remains a separate last-stage task.  NDSS
artifact evaluation occurs after paper notification, so it is not a blocker
for the Fall paper upload.
