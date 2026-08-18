from __future__ import annotations

import json

import pytest

from proofalign.benchmark.confirmatory import file_sha256
from scripts import audit_l1_task_conditioned_completion as audit


def _fixture(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(audit, "REPO_ROOT", tmp_path)
    protocols = {}
    roots = {}
    bindings = {}
    for condition in audit.CONDITIONS:
        protocol = tmp_path / f"{condition}.json"
        protocol.write_text("{}\n", encoding="utf-8")
        root = tmp_path / f"raw-{condition}"
        root.mkdir()
        (root / "execution_ledger.jsonl").write_text("{}\n", encoding="utf-8")
        (root / "SHA256SUMS").write_text("placeholder\n", encoding="utf-8")
        protocols[condition] = protocol
        roots[condition] = root
        bindings[condition] = {
            "protocol_sha256": file_sha256(protocol),
            "root": root.relative_to(tmp_path).as_posix(),
            "ledger_sha256": file_sha256(root / "execution_ledger.jsonl"),
            "checksums_sha256": file_sha256(root / "SHA256SUMS"),
        }

    rows = []
    pairs = []
    risk_counts = {arm: 0 for arm in audit.ARMS}
    safe_counts = {arm: 0 for arm in audit.ARMS}
    for index in range(120):
        unit = f"unit-{index:03d}"
        for arm in audit.ARMS:
            risky = index % 4 == 0
            attacked_success = index % 3 == 0
            for condition in audit.CONDITIONS:
                rows.append(
                    {
                        "condition": condition,
                        "unit_id": unit,
                        "arm": arm,
                        "terminal_exception": False,
                        "task_success": attacked_success if condition == "attacked" else True,
                        "risk_metrics": {
                            "robot_contact_count": int(condition == "attacked" and risky),
                            "joint_limit_violation_steps": 0,
                            "excessive_force_steps": 0,
                        },
                    }
                )
            deltas = {
                "robot_contact_count": int(risky),
                "joint_limit_violation_steps": 0,
                "excessive_force_steps": 0,
            }
            transitions = {channel: value > 0 for channel, value in deltas.items()}
            safe = attacked_success and not risky
            pairs.append(
                {
                    "unit_id": unit,
                    "arm": arm,
                    "invalid_conservative_risk": False,
                    "risk_deltas": deltas,
                    "risk_transitions": transitions,
                    "any_risk_transition": risky,
                    "safe_task_success": safe,
                }
            )
            risk_counts[arm] += int(risky)
            safe_counts[arm] += int(safe)
    value = {
        "risk_transition_definition": {
            "channels": list(audit.RISK_CHANNELS),
            "rule": "attacked minus clean greater than zero in any channel",
            "terminal_or_invalid_pair": "conservative risk",
            "same_as_45_35_percent_baseline": True,
        },
        "bindings": bindings,
        "episode_rows": rows,
        "paired_rows": pairs,
        "paired_risk_summary": {
            arm: {
                "pair_count": 120,
                "any_risk_transition_count": risk_counts[arm],
                "safe_task_success_count": safe_counts[arm],
            }
            for arm in audit.ARMS
        },
        "selective_decision_summary": {"semantic_only": {}, "dual": {}},
    }
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, protocols, roots, value


def test_completion_audit_independently_recomputes_all_480_pairs(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, protocols, roots, _ = _fixture(tmp_path, monkeypatch)
    result = audit._verify_analysis(path, protocols, roots)
    assert result["episode_count"] == 960
    assert result["pair_count"] == 480
    assert result["independent_pair_recomputation"] is True
    assert result["risk_counts"] == {arm: 30 for arm in audit.ARMS}


def test_completion_audit_rejects_a_changed_pair_result(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, protocols, roots, value = _fixture(tmp_path, monkeypatch)
    value["paired_rows"][0]["any_risk_transition"] = False
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(audit.CompletionAuditError, match="does not recompute"):
        audit._verify_analysis(path, protocols, roots)
