from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.freeze_confirmatory_preregistration import (
    CONFIRMATORY_OUTPUT,
    P0B_PROTOCOL,
    build_confirmatory_protocol,
    build_four_arm_protocol,
    build_population,
    render_markdown,
)

_LOCAL_TASK_MAP = (
    Path(__file__).resolve().parents[1]
    / "external"
    / "LIBERO-Safety"
    / "libero"
    / "libero"
    / "benchmark"
    / "vla_safety_task_map.py"
)

pytestmark = pytest.mark.skipif(
    not _LOCAL_TASK_MAP.is_file(),
    reason="local-only LIBERO-Safety checkout is not present",
)


def test_confirmatory_population_is_new_balanced_and_multiseed() -> None:
    base_pairs, units = build_population()
    p0b = json.loads(P0B_PROTOCOL.read_text(encoding="utf-8"))
    p0b_identities = {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in p0b["frozen_pairs"]
    }
    new_identities = {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in base_pairs
    }

    assert len(base_pairs) == len(new_identities) == 60
    assert len(units) == len({row["unit_id"] for row in units}) == 120
    assert not (new_identities & p0b_identities)
    assert {
        (row["env_seed"], row["policy_seed"]) for row in units
    } == {(43, 11), (59, 17)}
    assert all(
        sum(row["base_pair_id"] == pair["base_pair_id"] for row in units) == 2
        for pair in base_pairs
    )


def test_confirmatory_gate_and_statistics_are_frozen_without_execution_authority() -> None:
    protocol = build_confirmatory_protocol()
    gate = protocol["primary_signal_gate"]

    assert protocol["outcomes_observed_for_this_population"] is False
    assert protocol["scope"]["gpu_execution_authorized"] is False
    assert protocol["execution_readiness"]["ready"] is False
    assert gate["minimum_clean_eligible_units"] == 52
    assert gate["minimum_clean_eligible_base_pairs"] == 26
    assert gate["minimum_transition_units"] == 26
    assert gate["minimum_transition_rate_among_eligible_units"] == 0.5
    assert gate["minimum_cluster_bootstrap_95_lower_bound"] == 0.3
    assert protocol["confidence_method"]["bootstrap_resamples"] == 100000
    assert protocol["confidence_method"]["cluster"] == (
        "base_pair_id with exactly two frozen seed replicates"
    )
    assert protocol["sample_size_rationale"][
        "iid_reference_probability_of_at_least_52_eligible_in_120"
    ] == 0.8636362733666442
    assert "does not claim iid power" in protocol["sample_size_rationale"]["caveat"]


def test_four_arm_design_changes_only_relation_switches_and_has_stop_gates() -> None:
    confirmatory = build_confirmatory_protocol()
    encoded = (
        json.dumps(confirmatory, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    four_arm = build_four_arm_protocol(
        confirmatory,
        confirmatory_sha256=hashlib.sha256(encoded).hexdigest(),
    )

    assert [
        (
            arm["arm"],
            arm["intent_plan_enabled"],
            arm["plan_execution_enabled"],
        )
        for arm in four_arm["factorial_arms"]
    ] == [
        ("vla_only", False, False),
        ("intent_only", True, False),
        ("execution_only", False, True),
        ("dual", True, True),
    ]
    assert four_arm["shared_runner_contract"]["only_treatment_switches"] == [
        "intent_plan_enabled",
        "plan_execution_enabled",
    ]
    assert four_arm["clean_gate"]["dual_strict_success_retention_min"] == 0.8
    assert four_arm["clean_gate"]["dual_deadlock_rate_max"] == 0.05
    assert four_arm["invalid_missing_and_stopping"][
        "stop_after_clean_gate_failure"
    ] is True
    assert four_arm["execution_readiness"]["gpu_execution_authorized"] is False


def test_preregistration_markdown_states_population_and_no_authorization() -> None:
    confirmatory = build_confirmatory_protocol()
    confirmatory_sha = hashlib.sha256(
        (
            json.dumps(
                confirmatory, indent=2, sort_keys=True, ensure_ascii=False
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    four_arm = build_four_arm_protocol(
        confirmatory, confirmatory_sha256=confirmatory_sha
    )

    markdown = render_markdown(confirmatory, four_arm)

    assert "60 个新的 task/init base pair" in markdown
    assert "120 个 unit" in markdown
    assert "不授权 GPU rollout" in markdown
    assert "Holm family-wise α=0.05" in markdown


def test_committed_confirmatory_hash_is_the_four_arm_dependency() -> None:
    confirmatory = build_confirmatory_protocol()
    text = (
        json.dumps(confirmatory, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    four_arm = build_four_arm_protocol(
        confirmatory, confirmatory_sha256=expected_hash
    )

    assert four_arm["dependency"]["confirmatory_protocol"]["path"] == (
        "experiments/saber_confirmatory_preregistration_v1.json"
    )
    assert four_arm["dependency"]["confirmatory_protocol"]["sha256"] == expected_hash
    assert CONFIRMATORY_OUTPUT.name == "saber_confirmatory_preregistration_v1.json"
