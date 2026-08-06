from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import file_sha256, load_json_object


REPO_ROOT = Path(__file__).resolve().parents[1]
ABORT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh1_abort.json"
)


def test_fresh1_abort_is_bound_and_has_no_evidence_root() -> None:
    abort = load_json_object(ABORT_PATH)

    assert abort["integrity"] == {
        "evidence_artifact_created": False,
        "qualification_metrics_observed": False,
        "registered_population_changed": False,
        "registered_thresholds_changed": False,
        "result_reclassified": False,
    }
    assert abort["repair_scope_authorized"] == {
        "analysis_compatibility_aliases_only": True,
        "mechanism_parameter_change": False,
        "population_change": False,
        "random_seed_change": False,
        "registered_gate_change": False,
        "registered_threshold_change": False,
        "retry_requires_fresh_output_root": True,
        "versioned_successor_protocol_required": True,
    }
    protocol_path = REPO_ROOT / abort["protocol"]["path"]
    runner_path = REPO_ROOT / abort["runner"]["path"]
    assert file_sha256(protocol_path) == abort["protocol"]["sha256"]
    assert file_sha256(runner_path) == abort["runner"]["sha256"]
    assert not (REPO_ROOT / abort["fresh_output_root"]["path"]).exists()
