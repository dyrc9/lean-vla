from __future__ import annotations

import json
import os

import pytest

from proofalign.benchmark import libero_online_wrapper as wrapper_module
from proofalign.benchmark.libero_e1_policy_audit import frozen_policy_value_copy
from proofalign.benchmark.libero_online_wrapper import (
    LiberoOnlineIntegrationError,
    _policy_action_audit,
)
from proofalign.benchmark.libero_e1_runner import UnguardedObservationChecker
from proofalign.models import Decision
from scripts.run_proofalign_e1_paired import (
    ProtocolError,
    assert_protocol_consistency,
    build_summary,
    derive_labels,
    expected_specs,
    failure_labels,
    mcnemar_exact,
    paired_bootstrap,
    repo_path,
)
from scripts.run_proofalign_e1_paired_v2 import (
    DEFAULT_PROTOCOL as V2_PROTOCOL,
    corrected_make_episode_args,
    load_effective_protocol,
)
from scripts import run_proofalign_e1_paired_v3 as v3
from scripts.run_proofalign_e1_paired_v3 import (
    DEFAULT_PROTOCOL as V3_PROTOCOL,
    load_effective_protocol as load_v3_effective_protocol,
)


def _step(*, cost: dict[str, int] | None, method: str = "vla_only") -> dict:
    info = {} if cost is None else {"cost": cost}
    ctda = {}
    if method == "full_ctda":
        ctda = {
            "active_phase": "contact",
            "static_verdict": "proven",
            "monitor_verdict": "complete",
            "wire_artifacts": [
                {
                    "proof_verified": True,
                    "parity_match": None,
                }
            ],
        }
    return {
        "decision": "allow",
        "env_info": info,
        "executed_policy_actions": [[0.0] * 7],
        "policy_call_id": "openpi:000000",
        "summary": {"num_raw_steps": 1, "boundary_reason": "max_chunk_steps"},
        "ctda": ctda,
    }


def _payload(*, cost: dict[str, int] | None, method: str = "vla_only") -> dict:
    return {
        "task_success": True,
        "decision": "allow",
        "final_state": {"notes": []},
        "trace": [_step(cost=cost, method=method)],
    }


def test_zero_cost_dictionary_is_complete_safe_evidence() -> None:
    labels = derive_labels(
        _payload(cost={"checkcontact": 0}, method="vla_only"),
        "vla_only",
        600,
    )

    assert labels["collision_cost_coverage_complete"] is True
    assert labels["unsafe_episode"] is False
    assert labels["safe_success"] is True
    assert labels["episode_unknown"] is False


def test_missing_raw_cost_signal_is_unknown_not_safe() -> None:
    labels = derive_labels(
        _payload(cost=None, method="vla_only"),
        "vla_only",
        600,
    )

    assert labels["collision_cost_coverage_complete"] is False
    assert labels["safe_success"] is False
    assert labels["episode_unknown"] is True


def test_fallback_nonzero_cost_marks_episode_unsafe() -> None:
    payload = _payload(cost={"checkcontact": 0}, method="full_ctda")
    payload["trace"][0]["ctda"]["fallback_trace"] = {
        "env_info": {"cost": {"checkcontact": 1}},
        "receipt": {
            "postcondition": {"no_collision": True, "no_cost": False}
        },
    }

    labels = derive_labels(payload, "full_ctda", 600)

    assert labels["unsafe_episode"] is True
    assert labels["safe_success"] is False
    assert labels["required_dispatch_observations"] == 2
    assert labels["observed_dispatch_observations"] == 2


def test_unguarded_checker_never_blocks() -> None:
    checker = UnguardedObservationChecker()

    for result in (
        checker.check_intent_alignment(),
        checker.check_effect_alignment(),
        checker.check_chunk_effect_alignment(),
    ):
        assert result.passed is True
        assert result.suggested_decision is Decision.ALLOW
        assert result.lean_mode == "disabled-vla-only"


def test_openpi_policy_metadata_is_deep_frozen_before_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(
        wrapper_module, "_frozen_action_copy", frozen_policy_value_copy
    )
    metadata = {
        "backend": "openpi",
        "checkpoint": "/data0/ldx/checkpoints/pi05_libero",
        "openpi_config": "pi05_libero",
        "sample_steps": 10,
        "max_actions_per_call": 1,
        "rng_reset_mode": "checkpoint-initial-per-episode",
        "action_clip": [-1.0, 1.0],
        "observation_attack_type": "none",
        "observation_attack_strength": None,
        "observation_attack": {
            "attack_type": "none",
            "changed": False,
            "clean_frame_sha256": "clean",
            "attacked_frame_sha256": "clean",
            "policy_call_index": 0,
        },
    }
    raw_policy_output = {
        "raw_action": [[0.0] * 7],
        "policy_action_chunk": [[0.0] * 7, [0.1] * 7],
        "policy_call_id": "openpi:000000",
        "vla_metadata": metadata,
    }

    call_id, chunk, frozen = _policy_action_audit(
        raw_policy_output, default_call_id="fallback:000000"
    )
    metadata["action_clip"][0] = 99.0
    metadata["observation_attack"]["changed"] = True

    assert call_id == "openpi:000000"
    assert len(chunk) == 2
    assert frozen["action_clip"] == (-1.0, 1.0)
    assert frozen["observation_attack"]["changed"] is False
    assert json.loads(json.dumps(frozen))["observation_attack"]["attack_type"] == "none"


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), object()])
def test_policy_action_audit_rejects_unsafe_nested_metadata_before_dispatch(
    invalid, monkeypatch
) -> None:
    monkeypatch.setattr(
        wrapper_module, "_frozen_action_copy", frozen_policy_value_copy
    )
    with pytest.raises(LiberoOnlineIntegrationError):
        _policy_action_audit(
            {
                "raw_action": [[0.0] * 7],
                "vla_metadata": {"backend": "openpi", "nested": {"value": invalid}},
            },
            default_call_id="openpi:000000",
        )


def _protocol() -> dict:
    return {
        "pilot_units": [
            {
                "suite": "affordance",
                "task_id": 0,
                "init_state_id": 0,
                "env_seed": 7,
                "policy_seed": 0,
            }
        ],
        "pairing": {"method_order": ["vla_only", "full_ctda"]},
        "analysis": {
            "paired_bootstrap_resamples": 100,
            "bootstrap_seed": 17,
        },
    }


def _record(spec, *, task_success: bool, safe_success: bool, deadlock: bool = False):
    labels = failure_labels(spec.method, "fixture")
    labels.update(
        {
            "task_success": task_success,
            "safe_success": safe_success,
            "episode_unknown": False,
            "deadlock": deadlock,
            "phase_completion": spec.method == "full_ctda" and task_success,
        }
    )
    return {
        "episode_id": spec.episode_id,
        "pair_id": spec.pair_id,
        "method": spec.method,
        "valid": True,
        "labels": labels,
    }


def test_summary_reports_method_attributable_deadlock_and_no_false_block_rate() -> None:
    protocol = _protocol()
    vla, full = expected_specs(protocol)
    ledger = [
        _record(vla, task_success=True, safe_success=True),
        _record(full, task_success=False, safe_success=False, deadlock=True),
    ]

    summary = build_summary(protocol, ledger)

    assert summary["status"] == "complete"
    assert summary["artifact_set"]["all_pairs_valid"] is True
    assert summary["paired"]["valid_pairs"] == 1
    assert summary["paired"]["method_attributable_deadlocks"] == 1
    assert summary["inference"]["status"] == "evaluated_all_frozen_pairs"
    assert summary["inference"]["task_success_retention"] == 0.0
    assert summary["false_block"]["status"] == "not_evaluated_closed_loop_counterfactual"
    assert summary["timing_and_resource_metrics"].endswith("reserved_for_E4")


def test_terminal_invalid_pair_does_not_enter_inference() -> None:
    protocol = _protocol()
    vla, full = expected_specs(protocol)
    invalid_vla = _record(vla, task_success=False, safe_success=False)
    invalid_full = _record(full, task_success=False, safe_success=False)
    invalid_vla["valid"] = False
    invalid_full["valid"] = False

    summary = build_summary(protocol, [invalid_vla, invalid_full])

    assert summary["status"] == "terminal_invalid"
    assert summary["artifact_set"] == {
        "terminal": True,
        "all_pairs_valid": False,
    }
    assert summary["paired"]["recorded_pairs"] == 1
    assert summary["paired"]["valid_pairs"] == 0
    assert summary["paired"]["rows"] == []
    assert summary["paired"]["excluded_rows"][0]["exclusion_reason"] == (
        "one_or_both_episodes_invalid"
    )
    assert summary["inference"] == {
        "status": "not_evaluated_no_valid_pairs",
        "valid_pairs": 0,
        "expected_pairs": 1,
    }


def test_frozen_binary_statistics_are_deterministic() -> None:
    pairs = [(1, 0), (1, 1), (0, 1)]

    assert paired_bootstrap(pairs, resamples=50, seed=9) == paired_bootstrap(
        pairs, resamples=50, seed=9
    )
    exact = mcnemar_exact(pairs)
    assert exact["discordant"] == 2
    assert exact["two_sided_exact_p"] == 1.0


def test_frozen_e1_v3_protocol_exactly_matches_e0_supported_slice() -> None:
    amendment, protocol = load_v3_effective_protocol(V3_PROTOCOL)

    # E1-v3 is an immutable historical execution protocol.  The later
    # policy-seed-1 utility runner intentionally changed the shared runner
    # bytes, so current-source execution must fail closed without weakening
    # the historical protocol pins.
    with pytest.raises(ProtocolError, match="frozen E1 input digest mismatch"):
        assert_protocol_consistency(protocol, V3_PROTOCOL)
    e0_ref = protocol["e0_protocol"]
    e0 = json.loads(repo_path(e0_ref["path"]).read_text(encoding="utf-8"))

    assert amendment["prior_failed_runs"][0]["resume"] is False
    assert amendment["prior_failed_runs"][1]["resume"] is False
    assert protocol["pilot_units"] == e0["e1"]["pilot_units"]
    assert len(protocol["pilot_units"]) == 12
    assert len(expected_specs(protocol)) == 24


def test_e1_v2_preserves_units_and_uses_physical_egl_id(
    monkeypatch, tmp_path
) -> None:
    amendment, protocol = load_effective_protocol(V2_PROTOCOL)
    spec = expected_specs(protocol)[0]
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    monkeypatch.setenv("MUJOCO_EGL_DEVICE_ID", "0")

    args = corrected_make_episode_args(
        protocol, spec, tmp_path / "episode.json", tmp_path / "artifacts"
    )

    assert amendment["prior_failed_run"]["replacement_or_overwrite"] is False
    assert len(protocol["pilot_units"]) == 12
    assert args.render_gpu_device_id == 3
    assert os.environ["MUJOCO_EGL_DEVICE_ID"] == "3"


def test_e1_v3_preflight_requires_no_dispatch_policy_output_probe(
    monkeypatch, tmp_path
) -> None:
    base_report = {
        "ready": True,
        "issues": [],
        "gpu": {"eligible_physical_ids": [3], "selected_physical_id": 3},
    }
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        v3.v2,
        "corrected_preflight",
        lambda _protocol, _path, *, selected_gpu: base_report,
    )

    def probe(path, protocol, gpu):
        observed.update({"path": path, "protocol": protocol, "gpu": gpu})
        return {"env_step_called": False, "audited_action_count": 5}

    monkeypatch.setattr(v3, "_policy_output_probe", probe)
    protocol = {"pilot_units": ["frozen"]}

    report = v3.corrected_preflight(
        protocol, tmp_path / "protocol.json", selected_gpu=3
    )

    assert report["ready"] is True
    assert observed["gpu"] == 3
    assert report["gpu"]["policy_output_audit_probe"] == {
        "env_step_called": False,
        "audited_action_count": 5,
    }
