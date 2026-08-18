# ProofAlign anonymous artifact

This directory defines the reviewer-facing artifact for the NDSS 2027
submission. The repository itself is the private source of truth; do not
upload a raw result directory because frozen episode metadata contains local
machine paths.

## What the artifact supports

- Lean-checked transaction identity and phase-advance properties for L2a;
- the frozen clean and SABER-attacked final four-arm study;
- re-derivation of task success, official-unsafe counts, violation episodes,
  crossing steps, joint-limit steps, paired transitions, integrity checks,
  force, prediction error, and latency;
- the retained frozen run-validity evidence;
- the M2 SABER attack-foundation study once its immutable producer and victim
  roots are restored.

It does not establish real-robot safety, arbitrary-attack robustness,
hard-real-time behavior, or a complete semantic verifier.

## Readiness check

From the repository root:

```sh
python3 scripts/build_ndss2027_anonymous_artifact.py --check-only
```

The command fails closed if a required result root is absent, a protocol-bound
file is missing, or an unhandled local absolute path would survive redaction.
During local preparation only, `--allow-incomplete-m2` reports the current
partial state without declaring the release ready.

## Build

Choose a new, empty destination outside the repository result roots:

```sh
python3 scripts/build_ndss2027_anonymous_artifact.py \
  --output /path/to/proofalign-ndss2027-artifact
```

The builder never overwrites or deletes an existing destination. It replaces
only recognized local path prefixes, records source and packaged SHA-256
digests in `REDACTION_MAP.json`, preserves original frozen checksum lists as
`*.frozen`, and writes a new package-wide `SHA256SUMS`.

## Reviewer verification

```sh
python3 scripts/audit_ndss2027_paper_claims.py
cd lean
lake build ProofAlign.IntegrityCore ProofAlign.SemanticIntegrityCore ProofAlign
cd ..
python3 -m pytest -q \
  tests/test_v15_14_unified_force_envelope_attacked_task_utility_qualification.py \
  tests/test_v15_bounded_state_triggered_task_utility_qualification.py \
  tests/test_v15_bounded_state_triggered_recovery.py
```

The full robot-policy rerun additionally requires the externally pinned OpenPI,
LIBERO-Safety, and SABER repositories/checkpoint described by the frozen
protocols. Those third-party assets are not redistributed here.

## Current private-checkout blocker

The M2 producer and victim fresh roots are not currently present in this
checkout. Until they are restored and their frozen checksums pass, the builder
must not produce a release artifact and the paper must not promise an
RQ1-complete package.
