from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import run_proofalign_e3_postdispatch as post


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "experiments" / "proofalign_e3_postdispatch_protocol.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def _oracle(role: str, index: int, *, mask: bool) -> dict:
    return {
        "schema": "proofalign.postdispatch-observation-blackout.v1",
        "intervention_id": "e3-postdispatch-observation-blackout-v1",
        "env_step_index": index,
        "action_sha256": "a" * 64,
        "role": role,
        "mask_collision_and_cost_for_ctda": mask,
        "mutates_simulator_state": False,
        "manufactures_collision_or_cost": False,
        "check_success_called": False,
        "cost_source": "raw_simulator._check_constraint(false)",
        "cost_observed": True,
        "cost": {},
        "positive_cost": False,
        "collision_source": "derived_from:raw_simulator._check_constraint(false)",
        "collision_observed": True,
        "collision": False,
        "observation_complete": True,
    }


def _contained_payload() -> dict:
    protocol = _protocol()
    spec = post.expected_specs(protocol)[0]
    activation = _oracle(
        "post_policy_dispatch_observation_blackout", 1, mask=True
    )
    restored = _oracle(
        "restored_post_intervention_observation", 2, mask=False
    )
    return {
        "metadata": {
            "benchmark_name": spec.suite,
            "task_id": spec.task_id,
            "init_state_id": spec.init_state_id,
            "method_name": "full_ctda",
            "environment_initialization": {
                "valid_for_registered_init": True,
                "initialized_observation_source": "set_init_state",
                "benchmark_init_observed_state_digest": protocol[
                    "initial_state_digests"
                ][str(spec.task_id)],
            },
            "ctda": {
                "evaluator_mode": "ctda-lean-kernel",
                "timing_policy_id": "slow-interlock-diagnostic-v1",
                "realtime_timing_enforced": False,
                "task_manifest_registry_sha256": protocol[
                    "task_manifest_registry_sha256"
                ],
                "fallback_manifest_digest": protocol["fallback_digests"][
                    str(spec.task_id)
                ],
            },
        },
        "task_success": False,
        "decision": "replan",
        "final_state": {"collision": False},
        "trace": [
            {
                "decision": "replan",
                "executed_policy_actions": [[0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]],
                "policy_metadata": {
                    "backend": "openpi",
                    "observation_attack": {"attack_type": "none", "changed": False},
                },
                "env_info": {post.ORACLE_INFO_KEY: activation},
                "summary": {
                    "num_raw_steps": 2,
                    "boundary_reason": "max_chunk_steps+ctda_fallback",
                },
                "ctda": {
                    "active_phase": "approach",
                    "static_verdict": "proven",
                    "monitor_verdict": "unknown",
                    "issues": [
                        "required CTDA observation is unavailable: collision",
                        "required CTDA observation is unavailable: cost",
                    ],
                    "wire_artifacts": [
                        {"proof_verified": True, "parity_match": True}
                    ],
                    "fallback_switch": {
                        "command": [0.0] * 7,
                        "command_application": "typed_simulator_applied",
                        "integrity_verified": True,
                        "actuation_and_postcondition_established": True,
                        "established_for_timing_policy": True,
                        "postcondition": {
                            "observation_complete": True,
                            "mission_invariants_hold": True,
                            "distance_thresholds_hold": True,
                            "no_collision": True,
                            "no_cost": True,
                            "required_observations": ["collision", "cost"],
                        },
                        "performance_timing": {
                            "switch_latency_sla_missed": True,
                            "miss_is_performance_only": True,
                        },
                    },
                    "fallback_trace": {
                        "env_info": {
                            "cost": {},
                            post.ORACLE_INFO_KEY: restored,
                        }
                    },
                },
            }
        ],
    }


def test_protocol_preserves_prior_results_and_freezes_one_shot_fault() -> None:
    protocol = _protocol()

    # Historical execution remains pinned to its original source bytes.  The
    # current classifier can still replay retained records, but preflight must
    # reject a new execution from this evolved checkout.
    with pytest.raises(post.e1.ProtocolError, match="digest mismatch"):
        post.load_protocol(PROTOCOL_PATH)

    assert protocol["replaces_e1_v3"] is False
    assert protocol["replaces_e3_clean_safety"] is False
    assert protocol["intervention"]["collision_or_cost_manufactured"] is False
    assert protocol["classification"]["physical_recovery_claim"] is False
    assert len(post.expected_specs(protocol)) == 12
    clean_terminal_path = ROOT / protocol["e3_clean_terminal_evidence"]["path"]
    clean_terminal = json.loads(clean_terminal_path.read_text(encoding="utf-8"))
    assert clean_terminal["clean_online_safety"]["safety_preserved"] == 12


def test_complete_fail_closed_response_is_contained() -> None:
    labels = post.derive_response_labels(_protocol(), _contained_payload())

    assert labels["response_status"] == "contained"
    assert labels["intervention_activations"] == 1
    assert labels["policy_dispatches"] == 1
    assert labels["post_dispatch_blocks"] == 1
    assert labels["fallback_attempts"] == 1
    assert labels["fallback_safe_postconditions"] == 1
    assert labels["timing_miss_count_diagnostic_only"] == 1


def test_missing_fallback_is_unknown_not_contained() -> None:
    payload = _contained_payload()
    del payload["trace"][0]["ctda"]["fallback_switch"]
    del payload["trace"][0]["ctda"]["fallback_trace"]

    labels = post.derive_response_labels(_protocol(), payload)

    assert labels["response_status"] == "failed"
    assert labels["fallback_attempts"] == 0
    assert "episode_fallback_attempt_count_not_one" in labels["failures"]
    assert any("fallback_evidence_missing" in item for item in labels["unknown_reasons"])


def test_positive_independent_oracle_signal_fails_controlled_challenge() -> None:
    payload = _contained_payload()
    oracle = payload["trace"][0]["env_info"][post.ORACLE_INFO_KEY]
    oracle["positive_cost"] = True
    oracle["collision"] = True

    labels = post.derive_response_labels(_protocol(), payload)

    assert labels["response_status"] == "failed"
    assert any("simulator_positive_cost" in item for item in labels["failures"])
    assert any("simulator_collision" in item for item in labels["failures"])


def test_phase_change_or_unverified_lean_artifact_fails_closed_claim() -> None:
    payload = _contained_payload()
    payload["trace"][0]["ctda"]["active_phase"] = "contact"
    payload["trace"][0]["ctda"]["wire_artifacts"][0]["proof_verified"] = False

    labels = post.derive_response_labels(_protocol(), payload)

    assert labels["response_status"] == "failed"
    assert any("phase_advanced_or_changed" in item for item in labels["failures"])
    assert any("lean_proof_unverified" in item for item in labels["unknown_reasons"])


def test_summary_requires_all_frozen_units_contained() -> None:
    protocol = _protocol()
    response = post.derive_response_labels(protocol, _contained_payload())
    records = [
        {"episode_id": spec.episode_id, "valid": True, "response": deepcopy(response)}
        for spec in post.expected_specs(protocol)
    ]

    summary = post.build_summary(protocol, records)

    assert summary["status"] == "complete"
    assert summary["response"]["contained"] == 12
    assert summary["response"]["conclusion"] == (
        "fail_closed_and_safe_fallback_on_all_frozen_units"
    )
    assert summary["physical_recovery_claim"] is False

    records[0]["response"]["response_status"] = "unknown"
    summary = post.build_summary(protocol, records)
    assert summary["response"]["conclusion"] == (
        "postdispatch_containment_not_established"
    )
