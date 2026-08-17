# NDSS 2027 Fall submission metadata

Updated on 2026-08-07 from the canonical LaTeX source.  This is a local
copy/paste sheet, not part of the Overleaf synchronization manifest.  The
official CFP now states that the Fall site opens on 15 August 2026 and links
<https://ndss27-fall.hotcrp.com/>.  Confirm the actual field names once the
site opens.

## Submission type and title

- Cycle: Fall
- Type: Technical paper
- Title: **ProofAlign: Trusted-Task Monitoring and Cross-Layer Execution Integrity for Action-Only Vision–Language–Action Systems**

## Plain-text abstract

Vision–language–action (VLA) controllers translate instructions and
observations directly into continuous robot-action chunks. A compromised
prompt or observation can therefore become physical behavior. Yet an
action-only deployment exposes neither a trustworthy model-supplied plan nor
evidence that a checked numerical action is the one later dispatched and
observed. This leaves an authorization gap between a trusted task and a
concrete action, and a realization gap between an authorized action and
physical execution.

We present ProofAlign, a consumer-side reference monitor that leaves the VLA
unchanged. A trusted branch derives a structured subtask from an authoritative
task and pre-attack observation; an untrusted policy branch proposes one
continuous ActionBlock. L1 binds a local checker verdict to that exact block,
rejects covered hard failures, and records uncertain task progress for
next-block replanning. L2a carries the runtime identity through a one-use
authorization, dispatch receipts, and effects; Lean checks abstract finite
binding and phase relations. Near joint boundaries, L2b screens at most two
temporary virtual-guard
configurations under a common force envelope. This is checker-relative,
simulator-qualified integrity—not latent-intent recovery or complete robot
safety.

We first reproduce SABER’s constraint-violation instruction attack: 39 of 86
clean-eligible units exhibit a new risk transition (45.35%, 95% base-pair
cluster-bootstrap CI: [32.93%, 57.78%]), successfully reproducing its
physical-risk effect in our victim/benchmark path. We then evaluate 18
held-out pairs in a 144-episode, paired four-arm study. Under attack, VLA-only
and L2-only succeed on 11/18 tasks, while L1-only and Dual succeed on 13/18;
their joint-limit violation-episode counts are 4/18, 1/18, 0/18, and 0/18,
respectively. Maximum screening latency is 39.79 ms (18.30 ms p95), with no
100 ms miss. The results support a cross-layer runtime-integrity mechanism for
the frozen attack family and simulator setting, not hardware attestation,
hard-real-time operation, or general robot safety.

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

ProofAlign is a systems-security paper about the authorization and realization
boundary between an attacked machine-learning controller and physical robot
execution. Its contribution is a consumer-side reference monitor with an
explicit TCB, fail-closed transaction semantics, negative integrity tests, and
simulator-qualified physical containment. Machine learning supplies the
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
