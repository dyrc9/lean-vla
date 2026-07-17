from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.run_proofalign_e1_clean_utility import (
    ProtocolError,
    build_summary,
    make_episode_args,
    validate_probe_pairs,
)
from scripts.run_proofalign_e1_paired import expected_specs, failure_labels


def _protocol() -> dict:
    return {
        "pilot_units": [
            {
                "suite": "affordance",
                "task_id": 0,
                "init_state_id": 0,
                "env_seed": 7,
                "policy_seed": 1,
                "workload": "clean",
            }
        ],
        "pairing": {"method_order": ["vla_only", "full_ctda"]},
        "initial_state_digests": {"0": "initial"},
        "fallback_bindings": [
            {
                "suite": "affordance",
                "task_id": 0,
                "init_state_id": 0,
                "path": "experiments/fallback/e0_v2_affordance_task00_init0.json",
                "sha256": "fallback",
                "task_manifest_digest": "manifest",
            }
        ],
        "task_manifest_registry": {"path": "registry", "sha256": "registry"},
        "victim": {
            "checkpoint": "/checkpoint",
            "openpi_config": "pi05_libero",
            "policy_plugin": "experiments.libero_openpi_plugin:create_policy",
            "policy_config": {
                "checkpoint_dir": "/checkpoint",
                "openpi_config": "pi05_libero",
                "policy_seed": 1,
            },
        },
        "execution": {
            "max_raw_steps": 600,
            "max_chunk_steps": 1,
            "abstractor_plugin": "experiments.libero_vla_plugin:create_abstractor",
            "camera_names": ["agentview", "robot0_eye_in_hand"],
            "camera_height": 256,
            "camera_width": 256,
            "control_freq_hz": 20,
            "environment_horizon": 1000,
            "action_dim": 7,
            "lean_timeout_seconds": 10.0,
            "warmup_steps": 0,
        },
        "analysis": {"paired_bootstrap_resamples": 10, "bootstrap_seed": 7},
        "claim_boundary": "fixture",
    }


def _probe_rows() -> list[dict]:
    common = {
        "pair_id": "affordance_task00_init0_env7_policy1",
        "task_manifest_digest": "manifest",
        "contact_query_digest": "query",
        "initial_state_digest": "initial",
        "first_policy_chunk_digest": "chunk",
        "env_step_count": 0,
    }
    return [
        {**common, "method": "vla_only"},
        {**common, "method": "full_ctda"},
    ]


def test_probe_requires_shared_manifest_digest_query_state_chunk_and_zero_dispatch() -> None:
    pairs = validate_probe_pairs(_protocol(), _probe_rows())

    assert pairs[0]["shared_initial_state_digest"] == "initial"
    assert pairs[0]["shared_first_policy_chunk_digest"] == "chunk"
    assert pairs[0]["env_step_count"] == 0


@pytest.mark.parametrize(
    "field",
    [
        "task_manifest_digest",
        "contact_query_digest",
        "initial_state_digest",
        "first_policy_chunk_digest",
        "env_step_count",
    ],
)
def test_probe_manifest_query_state_chunk_or_dispatch_difference_fails_closed(
    field: str,
) -> None:
    rows = _probe_rows()
    rows[1][field] = 1 if field == "env_step_count" else "different"

    with pytest.raises(ProtocolError):
        validate_probe_pairs(_protocol(), rows)


def test_probe_full_ctda_digest_must_match_frozen_e0_digest() -> None:
    protocol = _protocol()
    protocol["initial_state_digests"]["0"] = "frozen-e0"

    with pytest.raises(ProtocolError, match="E0 frozen initial digest"):
        validate_probe_pairs(protocol, _probe_rows())


def test_make_episode_args_binds_real_policy_seed_and_same_pair_config(
    monkeypatch, tmp_path
) -> None:
    protocol = _protocol()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    vla, full = expected_specs(protocol)

    vla_args = make_episode_args(protocol, vla, tmp_path / "vla.json", tmp_path / "a")
    full_args = make_episode_args(protocol, full, tmp_path / "full.json", tmp_path / "b")

    assert '"policy_seed": 1' in vla_args.policy_config
    assert vla_args.paired_execution_config_digest == full_args.paired_execution_config_digest
    assert vla_args.ctda is False
    assert full_args.ctda is True
    assert vla_args.ctda_task_manifest_registry == full_args.ctda_task_manifest_registry
    assert vla_args.render_gpu_device_id == full_args.render_gpu_device_id == 3


def _record(spec, *, task_success: bool, safe_success: bool) -> dict:
    labels = failure_labels(spec.method, "fixture")
    labels.update(
        {
            "task_success": task_success,
            "safe_success": safe_success,
            "episode_unknown": False,
            "deadlock": spec.method == "full_ctda" and not task_success,
            "phase_completion": False if spec.method == "full_ctda" else None,
            "collision_cost_coverage_complete": True,
            "required_dispatch_observations": 1,
            "observed_dispatch_observations": 1,
            "closed_loop_block_count": 1 if spec.method == "full_ctda" else 0,
        }
    )
    return {
        "episode_id": spec.episode_id,
        "pair_id": spec.pair_id,
        "method": spec.method,
        "valid": True,
        "labels": labels,
    }


def test_summary_reports_coverage_blocks_loss_and_no_false_positive_claim() -> None:
    protocol = _protocol()
    vla, full = expected_specs(protocol)
    summary = build_summary(
        protocol,
        [
            _record(vla, task_success=True, safe_success=True),
            _record(full, task_success=False, safe_success=False),
        ],
    )

    assert summary["paired"]["valid_pairs"] == 1
    assert summary["paired"]["method_attributable_utility_loss"] == 1
    assert summary["methods"]["full_ctda"]["collision_cost_coverage"] == 1.0
    assert summary["methods"]["full_ctda"]["closed_loop_block_count"] == 1
    assert summary["closed_loop_block_label"].startswith("intervention_only")


def test_zero_valid_pairs_remains_not_evaluated() -> None:
    protocol = _protocol()
    records = []
    for spec in expected_specs(protocol):
        record = _record(spec, task_success=False, safe_success=False)
        record["valid"] = False
        records.append(record)

    summary = build_summary(protocol, records)

    assert summary["status"] == "terminal_invalid"
    assert summary["paired"]["valid_pairs"] == 0
    assert summary["inference"]["status"] == "not_evaluated_no_valid_pairs"
