from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofalign.benchmark.semantic_four_arm_runner import (
    SemanticFixedTraceError,
    SharedSemanticV4ShadowRunner,
)
from scripts.generate_semantic_v4_equivalence_evidence import (
    OUTPUT_PATH as EQUIVALENCE_PATH,
    THEOREM_NAMES,
    build_evidence as build_equivalence_evidence,
    canonical_text as equivalence_canonical_text,
)
from scripts.run_semantic_v4_fixed_trace_gate import (
    C5GateError,
    CASE_IDS,
    EVIDENCE_PATH,
    PROTOCOL_PATH,
    _trace_case,
    build_evidence as build_fixed_trace_evidence,
    build_protocol,
    canonical_text as fixed_trace_canonical_text,
    validate_protocol,
)
from scripts.validate_semantic_v4_c5_readiness import (
    DEFAULT_PACKET,
    build_report,
    canonical_report,
)


ROOT = Path(__file__).resolve().parents[1]


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_c5_protocol_and_generated_artifacts_are_canonical() -> None:
    protocol = _protocol()
    validate_protocol(protocol)
    assert PROTOCOL_PATH.read_text(
        encoding="utf-8"
    ) == fixed_trace_canonical_text(build_protocol())

    fixed_trace = build_fixed_trace_evidence(protocol)
    assert EVIDENCE_PATH.read_text(
        encoding="utf-8"
    ) == fixed_trace_canonical_text(fixed_trace)

    equivalence = build_equivalence_evidence()
    assert EQUIVALENCE_PATH.read_text(
        encoding="utf-8"
    ) == equivalence_canonical_text(equivalence)


def test_c5_four_arm_truth_table_shares_identity_and_never_dispatches() -> None:
    evidence = build_fixed_trace_evidence(_protocol())

    assert evidence["classification"] == "c5_no_dispatch_identity_pass"
    assert evidence["case_count"] == len(CASE_IDS) == 8
    assert evidence["row_count"] == 32
    assert evidence["identity_pass"] is True
    assert evidence["dispatch_attempt_count"] == 0
    assert evidence["simulator_created"] is False
    assert evidence["sink_created"] is False
    assert evidence["policy_loaded"] is False
    assert evidence["outcomes_observed"] is False
    assert all(
        len(identity["proposal_digests"]) == 1
        and len(identity["assessment_digests"]) == 1
        and len(identity["execution_contract_digests"]) == 1
        for identity in evidence[
            "artifact_identity_across_arms"
        ].values()
    )


def test_c5_negative_cases_are_isolated_to_the_enabled_layer() -> None:
    rows = build_fixed_trace_evidence(_protocol())["runner_result"][
        "rows"
    ]
    verdicts = {
        (row["case_id"], row["arm"]): row["core_verdict"]
        for row in rows
    }

    assert verdicts[("semantic_mismatch", "vla_only")] == "allow"
    assert verdicts[("semantic_mismatch", "execution_only")] == "allow"
    assert verdicts[("semantic_mismatch", "semantic_only")] == "reject"
    assert verdicts[("semantic_mismatch", "dual")] == "reject"
    assert verdicts[("command_substitution", "semantic_only")] == "allow"
    assert verdicts[("command_substitution", "execution_only")] == "reject"
    assert verdicts[("command_substitution", "dual")] == "reject"
    assert verdicts[("unknown_assessment", "semantic_only")] == "unknown"
    assert verdicts[("stale_state", "execution_only")] == "unknown"


def test_shadow_runner_rejects_noncontiguous_proposal_indices() -> None:
    with pytest.raises(
        SemanticFixedTraceError,
        match="proposal indices must be contiguous",
    ):
        SharedSemanticV4ShadowRunner().evaluate(
            unit_id="noncontiguous",
            proposals=[_trace_case(1, "nominal")],
        )


def test_protocol_rejects_dispatch_or_fresh_root_mutation() -> None:
    protocol = _protocol()
    with pytest.raises(C5GateError, match="permits dispatch"):
        validate_protocol({**protocol, "dispatch": True})
    with pytest.raises(C5GateError, match="fresh roots changed"):
        validate_protocol(
            {
                **protocol,
                "future_fresh_roots": {
                    **protocol["future_fresh_roots"],
                    "selector_qualification": "results/reused",
                },
            }
        )


def test_semantic_v4_equivalence_keeps_scoped_claim_boundary() -> None:
    evidence = build_equivalence_evidence()

    assert evidence["classification"] == "c5_scoped_equivalence_pass"
    assert evidence["all_scoped_cases_match"] is True
    assert evidence["truth_table_case_count"] == 32
    assert len(THEOREM_NAMES) == 14
    assert evidence["bindings"]["lean_source"]["theorems"] == THEOREM_NAMES
    assert (
        evidence["scope"]["machine_checked_full_refinement_complete"]
        is False
    )


def test_c5_readiness_packet_is_current_and_does_not_authorize_rollout() -> None:
    report = build_report()

    assert report["c5_component_closure_complete"] is True
    assert report["next_qualification_stage_ready"] is False
    assert report["efficacy_rollout_ready"] is False
    assert report["efficacy_rollout_authorized"] is False
    assert report["simulator_steps"] == 0
    roots = report["components"]["future_fresh_roots"]["roots"]
    assert roots["no_attack_smoke"]["absent"] is True
    assert all(
        row["absent"] is False
        for name, row in roots.items()
        if name != "no_attack_smoke"
    )
    assert DEFAULT_PACKET.read_text(
        encoding="utf-8"
    ) == canonical_report(report)
