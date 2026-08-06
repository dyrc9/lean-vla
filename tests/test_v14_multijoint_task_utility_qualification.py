from __future__ import annotations

from collections import Counter

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v14_multijoint_task_utility_qualification as freezer
from scripts import run_v14_multijoint_task_utility_qualification as runner


def test_utility_population_retains_every_stress_pair_with_new_seeds() -> None:
    v14 = load_json_object(freezer.V14_DEVELOPMENT_PROTOCOL_PATH)
    stress = load_json_object(freezer.STRESS_PROTOCOL_PATH)

    workloads = freezer._derive_workloads(v14, stress)

    observed = {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in workloads
    }
    expected = {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in stress["environments"]
    }
    assert observed == expected
    assert len(workloads) == 18
    assert all(row["environment_seed"] == 2509 for row in workloads)
    assert all(row["policy_seed"] == 1251 for row in workloads)


def test_utility_schedule_is_complete_paired_and_deterministic() -> None:
    v14 = load_json_object(freezer.V14_DEVELOPMENT_PROTOCOL_PATH)
    stress = load_json_object(freezer.STRESS_PROTOCOL_PATH)
    workloads = freezer._derive_workloads(v14, stress)

    first = freezer._build_schedule(workloads)
    second = freezer._build_schedule(workloads)

    assert first == second
    assert len(first) == 72
    assert [row["sequence_index"] for row in first] == list(range(72))
    assert Counter(row["arm"] for row in first) == {
        arm: 18 for arm in freezer.ARM_ORDER
    }
    by_pair: dict[str, set[str]] = {}
    for row in first:
        by_pair.setdefault(row["base_pair_id"], set()).add(row["arm"])
    assert len(by_pair) == 18
    assert all(set(freezer.ARM_ORDER) == arms for arms in by_pair.values())


def test_qualification_enrichment_requires_every_registered_gate(
    monkeypatch,
) -> None:
    protocol = {
        "pass_classification": "pass",
        "nonpass_classification": "nonpass",
    }
    gates = {
        "v9_execution_only_task_success_noninferiority": True,
        "v9_dual_task_success_noninferiority": True,
        "v9_execution_only_official_unsafe_nonincrease": True,
        "v9_dual_official_unsafe_nonincrease": True,
        "integrity": True,
    }
    monkeypatch.setattr(
        runner,
        "_BASE_ENRICH",
        lambda _protocol, _evidence: {
            "gate_results": dict(gates),
            "classification": "base",
        },
    )

    passed = runner._qualification_enrich(protocol, {})
    gates["integrity"] = False
    failed = runner._qualification_enrich(protocol, {})

    assert passed["qualification_pass"] is True
    assert passed["classification"] == "pass"
    assert passed["task_utility_qualification_claim_authorized"] is True
    assert failed["qualification_pass"] is False
    assert failed["classification"] == "nonpass"
    assert failed["task_utility_qualification_claim_authorized"] is False


def test_frozen_utility_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return

    retained = load_json_object(freezer.OUTPUT_PATH)
    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained


def test_qualification_preflight_removes_inherited_role_labels(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runner.base,
        "preflight",
        lambda *_args, **_kwargs: {
            "ready": True,
            "development_role": True,
            "development1_partial_outcomes_observed": True,
            "outcomes_observed_before_protocol_freeze": True,
        },
    )

    report = runner.preflight(
        {},
        protocol_path=runner.DEFAULT_PROTOCOL,
        policy_gpu=0,
        egl_gpu=1,
    )

    assert report["qualification_role"] is True
    assert "development_role" not in report
    assert "development1_partial_outcomes_observed" not in report
    assert "outcomes_observed_before_protocol_freeze" not in report
