from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from scripts import freeze_predictive_virtual_brake_v13_clean_fresh3 as freezer
from scripts import run_l2_predictive_virtual_brake_v13 as predecessor
from scripts import run_l2_predictive_virtual_brake_v13_fresh3 as runner
from scripts import run_predictive_virtual_brake_v13_clean_fresh3 as clean


class _NoObservationGetter:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"unexpected environment read: {name}")


@pytest.mark.parametrize(
    ("template", "expected"),
    (
        (({"pixels": "shadow"}, 7.0, False, {"source": "four"}), 4),
        (
            (
                {"pixels": "shadow"},
                7.0,
                False,
                True,
                {"source": "five"},
            ),
            5,
        ),
    ),
)
def test_terminal_deadlock_uses_existing_shadow_observation_only(
    template: tuple[Any, ...],
    expected: int,
) -> None:
    transition = (
        runner._terminal_shadow_observation_deadlock_transition(
            _NoObservationGetter(),
            template,
            reason="no_safe_guard_candidate",
        )
    )

    assert len(transition) == expected
    assert transition[0] is template[0]
    assert transition[1] == 0.0
    assert transition[2] is True
    if expected == 5:
        assert transition[3] is False
    info = transition[-1]
    assert info[runner.DEADLOCK_INFO_KEY] == (
        "no_safe_guard_candidate"
    )
    assert info["proofalign_deadlock_observation_source"] == (
        "discarded_shadow_transition_terminal_only"
    )


def test_deadlock_patch_is_scoped_and_restored() -> None:
    original = predecessor._deadlock_transition

    with runner._patched_deadlock_transition():
        assert predecessor._deadlock_transition is (
            runner._terminal_shadow_observation_deadlock_transition
        )

    assert predecessor._deadlock_transition is original


def test_fresh3_episode_annotation_does_not_change_science(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_deadlock = predecessor._deadlock_transition
    persisted: list[dict[str, Any]] = []

    def fake_run_episode(**_kwargs: Any) -> dict[str, Any]:
        assert predecessor._deadlock_transition is (
            runner._terminal_shadow_observation_deadlock_transition
        )
        return {
            "metadata": {"existing": True},
            "trace": [
                {
                    "predictive_virtual_brake": {
                        "deadlock": True,
                    }
                }
            ],
        }

    monkeypatch.setattr(
        predecessor,
        "run_episode",
        fake_run_episode,
    )
    monkeypatch.setattr(
        runner.v1,
        "_persist_annotated_episode",
        lambda payload: persisted.append(payload),
    )

    payload = runner.run_episode(args=object())

    assert predecessor._deadlock_transition is original_deadlock
    assert payload["metadata"]["runner_variant"] == (
        runner.RUNNER_VARIANT
    )
    assert payload["metadata"][
        "fresh3_scientific_parameters_changed"
    ] is False
    assert payload["metadata"][
        "deadlock_observation_policy_consumed"
    ] is False
    audit = payload["trace"][0]["predictive_virtual_brake"]
    assert audit["deadlock_observation_source"] == (
        "discarded_shadow_transition_terminal_only"
    )
    assert audit["deadlock_observation_policy_consumed"] is False
    assert persisted == [payload]


def test_clean_wrapper_patch_is_scoped_and_restored() -> None:
    original = (
        clean.predecessor.PROTOCOL_SCHEMA,
        clean.predecessor.EVIDENCE_SCHEMA,
        clean.predecessor.EXPECTED_RUNNER,
        clean.predecessor.AUTHORIZED_STATUS,
        clean.predecessor.DEFAULT_PROTOCOL,
        clean.predecessor.online,
    )

    with clean._patched_predecessor():
        assert clean.predecessor.PROTOCOL_SCHEMA == clean.PROTOCOL_SCHEMA
        assert clean.predecessor.EVIDENCE_SCHEMA == clean.EVIDENCE_SCHEMA
        assert clean.predecessor.EXPECTED_RUNNER == runner.RUNNER_VARIANT
        assert clean.predecessor.AUTHORIZED_STATUS == (
            clean.AUTHORIZED_STATUS
        )
        assert clean.predecessor.DEFAULT_PROTOCOL == (
            clean.DEFAULT_PROTOCOL
        )
        assert clean.predecessor.online is runner

    assert (
        clean.predecessor.PROTOCOL_SCHEMA,
        clean.predecessor.EVIDENCE_SCHEMA,
        clean.predecessor.EXPECTED_RUNNER,
        clean.predecessor.AUTHORIZED_STATUS,
        clean.predecessor.DEFAULT_PROTOCOL,
        clean.predecessor.online,
    ) == original


def test_fresh3_freezer_preserves_fresh2_scientific_design(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fresh2 = load_json_object(freezer.FRESH2_PROTOCOL_PATH)
    failure = load_json_object(freezer.FRESH2_FAILURE_PATH)
    captured: dict[str, Any] = {}

    def fake_build_protocol(**_kwargs: Any) -> dict[str, Any]:
        return {
            **fresh2,
            "required_bindings": [],
            "selection": dict(fresh2["selection"]),
            "stop_rule": dict(fresh2["stop_rule"]),
        }

    def fake_binding(
        path: Path,
        *,
        classification: str | None = None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {"path": str(path), "sha256": "bound"}
        if classification is not None:
            row["classification"] = classification
        return row

    def fake_git(*args: str) -> str:
        captured.setdefault("git", []).append(args)
        if args[0] == "rev-parse" and args[1].endswith("^{tree}"):
            return "tree"
        if args[0] == "rev-parse":
            return "commit"
        return ""

    monkeypatch.setattr(
        freezer.predecessor,
        "build_protocol",
        fake_build_protocol,
    )
    monkeypatch.setattr(
        freezer.predecessor,
        "_binding",
        fake_binding,
    )
    monkeypatch.setattr(freezer, "_git", fake_git)
    monkeypatch.setattr(
        freezer,
        "SOURCE_PATHS",
        ("source.py",),
    )
    monkeypatch.setattr(
        freezer,
        "SELF_PATH",
        freezer.REPO_ROOT / "scripts" / "freezer.py",
    )
    monkeypatch.setattr(
        freezer,
        "file_sha256",
        lambda _path: "source-sha",
    )

    protocol = freezer.build_protocol(source_commit="commit")

    for field in (
        "workloads",
        "schedule",
        "design",
        "analysis",
        "v13_gates",
        "stage",
    ):
        assert protocol[field] == fresh2[field]
    assert protocol["fresh_output_root"].endswith(
        "20260731_fresh3"
    )
    assert protocol["outcomes_observed_for_selection"] is True
    assert protocol["outcome_conditioned_engineering_regression"] is True
    assert protocol["selection"][
        "fresh2_completed_episode_count"
    ] == failure["terminal_state"]["completed_episode_count"]
    assert protocol["retry_disclosure"]["workloads_changed"] is False
    assert protocol["retry_disclosure"]["seeds_changed"] is False
    assert protocol["retry_disclosure"]["guard_changed"] is False
    assert protocol["retry_disclosure"]["thresholds_changed"] is False
    assert protocol["retry_disclosure"]["estimands_changed"] is False
    assert protocol["retry_disclosure"]["gates_changed"] is False
