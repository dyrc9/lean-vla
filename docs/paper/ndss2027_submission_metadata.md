# NDSS 2027 Fall submission metadata

Updated on 2026-08-20 from the canonical LaTeX source.  This local copy/paste
sheet sits outside the Overleaf synchronization manifest.  The
official CFP now states that the Fall site opens on 15 August 2026 and links
<https://ndss27-fall.hotcrp.com/>.  Confirm the actual field names once the
site opens.

## Submission type and title

- Cycle: Fall
- Type: Technical paper
- Title: **ProofAlign: Cross-Layer Runtime Integrity for Embodied Vision–Language–Action Systems**

## Plain-text abstract

Vision–language–action (VLA) systems turn language and observations into
continuous robot actions. Surveyed defenses protect different parts of this
path without jointly binding independently anchored task authority to the exact
newly generated ActionBlock, its ordered dispatch, and registered execution
evidence. This leaves an intent–action authorization gap and an
action–execution realization gap.

ProofAlign closes these gaps at the action-only consumer boundary through two
alignment stages. L1 assesses the exact online ActionBlock against trusted task
intent. L2 carries an admitted block to execution. Its L2a component binds a
one-use ordered transaction and its evidence, while L2b qualifies the same
source action under a registered joint-boundary trigger. The ProofAligned
property composes issuance, dispatch, evidence closure, phase advance, and
triggered-guard obligations. Lean checks selected abstract transaction and
phase relations.

An independent study reproduces the SABER constraint-violation instruction
attack on OpenPI π0.5 in LIBERO-Safety. Among 86 clean-eligible units, 39 develop
a new physical-risk transition under attack; the observed ASR is 45.35%. A
separate paired four-arm study covers 120 fixed units and 960 episode attempts.
Each condition yields 98.96% valid traces (475/480), leaving the registered
all-valid requirement unmet; the comparisons remain nonconfirmatory. On the
common 75-unit cohort, risk-transition rates are 50.67%, 56.00%, 48.00%, and
57.33% for VLA-only, L1-only, L2-only, and Dual. The paired sensitivity tests
provide no evidence of a broad reduction. Under attack, Dual task success is
53.33%, compared with 60.83% for VLA-only. Among 237 valid attacked L2-enabled
traces, 0.00% contain a joint-limit step. The claims are checker-relative and
limited to the exercised transaction faults, registered joint boundary, frozen
attack family, checkpoint, and simulator.

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
ProofAligned property, fail-closed transaction semantics, focused integrity
fault tests, and registered joint-side screening diagnostics. Machine learning
supplies the untrusted action proposal. The contribution centers on
consumer-side authorization, execution evidence, and state-conditioned guard
qualification. The implementation, paired attack evaluation, and Lean-checked
transaction model directly address practical AI-system and cyber-physical
security.

## Ethics summary

The study evaluates a published instruction attack entirely in simulation.
Its evidence consists of benchmark tasks, simulator traces, observed attack
and four-arm outcomes, focused integrity tests, and frozen reproducibility
records. The prototype's scope is supervised research on action-boundary
monitoring. Certified machinery safeguards remain the applicable deployment
control for physical robots.

## Generative-AI disclosure summary

OpenAI Codex desktop app (GPT-5 model family; accessed August 2026) assisted
across all manuscript sections with drafting and editing prose and generated
the LaTeX/TikZ diagrams for Figs. 2--4 and raster artwork for Fig. 1 from author-supplied
system designs, experiment protocols, frozen results, and claim boundaries. It
supported manuscript and diagram production. The reported experiments and
outcome selection remain author-conducted. The authors reviewed the generated
text and diagrams and remain responsible for every claim, number, citation,
and artifact.

At submission time, use the most precise model label visible in the interface
here and in `sections/ai_disclosure.tex`.

## Author and conflict freeze — required human input

Before the deadline, the authors jointly verify:

- [ ] final author names, ordering, email addresses, affiliations, and
      countries;
- [ ] compliance with the six-submission Fall-cycle cap for every author;
- [ ] perpetual advisor/advisee conflicts for every author;
- [ ] current institutional conflicts;
- [ ] professional collaborations from the preceding two years;
- [ ] close personal relationships and any grey-area conflicts raised with
      the PC chairs;
- [ ] a stable author list for the post-deadline period;
- [ ] absence of a prohibited concurrent submission or major overlap
      with an NDSS 2027 Summer rejection; and
- [ ] compliance with the review-period publicity policy.

Keep author and conflict data in the submission system and outside the
anonymous PDF.

## Submission-time identifiers

- HotCRP submission number: **pending**
- First-page DOI suffix: replace `24xxxx` with `24` followed by the Fall paper
  number padded with leading zeros as specified by the NDSS template.
- PDF filename for upload: choose a neutral identifier after HotCRP creates the
  submission, using the submission number and an anonymous label.

After these fields and any more precise visible AI label are filled, run:

```sh
python3 scripts/check_ndss2027_submission.py --final
```

Prepare the anonymous experiment artifact as a separate last-stage task.  NDSS
artifact evaluation follows paper notification, while the Fall paper upload
uses the manuscript package described above.
