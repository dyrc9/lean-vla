from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_v14_multijoint_stress_qualification as freezer
from scripts import run_v14_multijoint_stress_qualification as runner


def test_held_out_selection_is_deterministic_balanced_and_unseen() -> None:
    workloads = load_json_object(freezer.V14_PROTOCOL_PATH)["workloads"]
    prior = {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in workloads
    }

    first = freezer._select_environments(workloads)
    second = freezer._select_environments(workloads)

    assert first == second
    assert len(first) == 18
    assert Counter(row["suite"] for row in first) == {
        suite: 6 for suite in freezer.SUITES
    }
    for suite in freezer.SUITES:
        assert len(
            {
                row["task_id"]
                for row in first
                if row["suite"] == suite
            }
        ) == 6
    assert not any(
        (row["suite"], row["task_id"], row["init_state_id"])
        in prior
        for row in first
    )
    assert all(row["environment_seed"] == 1509 for row in first)


def _rows(matrix: np.ndarray) -> list[dict[str, float | int]]:
    return runner.development.pilot._margin_rows(matrix)


def test_threshold_identity_separates_numeric_drift_from_risk_labels() -> None:
    direct = np.full((7, 2), 1.0)
    shadow = direct.copy()
    shadow[6, 0] += 0.04
    direct[2, 1] = 0.14
    shadow[2, 1] = 0.141
    lane = {
        "baselines": {
            "no_guard": {"actual_joint_side_margins": [_rows(direct)]},
            "shadow_only": {"actual_joint_side_margins": [_rows(shadow)]},
        }
    }

    report = runner._threshold_identity(
        [lane],
        thresholds=[0.0, 0.15, 0.16, 0.22, 0.30],
    )

    assert report["maximum_all_side_error_rad"] == pytest.approx(0.04)
    assert report["maximum_near_limit_error_rad"] == pytest.approx(0.001)
    assert report["trace_length_mismatch_count"] == 0
    assert not any(
        report["threshold_classification_disagreement_count"].values()
    )


def test_threshold_identity_detects_boundary_disagreement() -> None:
    direct = np.full((7, 2), 1.0)
    shadow = direct.copy()
    direct[1, 0] = 0.149
    shadow[1, 0] = 0.151
    lane = {
        "baselines": {
            "no_guard": {"actual_joint_side_margins": [_rows(direct)]},
            "shadow_only": {"actual_joint_side_margins": [_rows(shadow)]},
        }
    }

    report = runner._threshold_identity([lane], thresholds=[0.15])

    assert report["threshold_classification_disagreement_count"] == {
        "0.15": 1
    }


def test_frozen_qualification_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return

    retained = load_json_object(freezer.OUTPUT_PATH)
    rebuilt = freezer.build_protocol(
        created_at=str(retained["created_at"]),
        source_commit=str(retained["source"]["repository_commit"]),
    )

    assert rebuilt == retained
