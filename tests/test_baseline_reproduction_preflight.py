from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from scripts.baseline_reproduction_preflight import (
    FIPER_PROTOCOL,
    PHANTOM_R1_PROTOCOL,
    SAFE_PROTOCOL,
    ProtocolError,
    check_fiper_assets,
    check_python_environment,
    collect_preflight,
    load_json,
    validate_fiper_protocol,
    validate_phantom_r1_protocol,
    validate_safe_protocol,
)


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_baseline_protocols_validate() -> None:
    validate_safe_protocol(load_json(SAFE_PROTOCOL))
    validate_fiper_protocol(load_json(FIPER_PROTOCOL))
    validate_phantom_r1_protocol(load_json(PHANTOM_R1_PROTOCOL))


def test_reduced_smoke_cannot_be_promoted_to_official_reproduction() -> None:
    safe = load_json(SAFE_PROTOCOL)
    mutated_safe = deepcopy(safe)
    mutated_safe["detector_reproduction"]["reduced_smoke_can_satisfy_r0"] = True
    with pytest.raises(ProtocolError, match="smoke"):
        validate_safe_protocol(mutated_safe)

    fiper = load_json(FIPER_PROTOCOL)
    mutated_fiper = deepcopy(fiper)
    mutated_fiper["official_pipeline"]["full_default_pipeline_required_for_r0_claim"] = False
    with pytest.raises(ProtocolError, match="full-pipeline"):
        validate_fiper_protocol(mutated_fiper)


def test_phantom_r1_rejects_init0_and_task_failure_signal() -> None:
    protocol = load_json(PHANTOM_R1_PROTOCOL)
    init0 = deepcopy(protocol)
    init0["episode_config"]["init_state_id"] = 0
    with pytest.raises(ProtocolError, match="held out"):
        validate_phantom_r1_protocol(init0)

    task_failure = deepcopy(protocol)
    task_failure["primary_signal_gate"]["task_failure_alone_counts_as_signal"] = True
    with pytest.raises(ProtocolError, match="task failure"):
        validate_phantom_r1_protocol(task_failure)


def test_fiper_asset_check_counts_each_task_and_split(tmp_path: Path) -> None:
    protocol = load_json(FIPER_PROTOCOL)
    for task in protocol["dataset"]["tasks_in_order"]:
        for split in ("calibration", "test"):
            folder = tmp_path / task / "rollouts" / split
            folder.mkdir(parents=True)
            for index in range(5):
                (folder / f"episode_{index}.pkl").write_bytes(b"not-unpickled")

    report = check_fiper_assets(protocol, data_root=tmp_path)

    assert all(
        counts == {"calibration": 5, "test": 5}
        for counts in report["counts"].values()
    )
    assert any("count differs from trusted inspection" in blocker for blocker in report["blockers"])


def test_python_environment_check_records_runtime_import_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_command(argv, *, cwd):
        calls.append((tuple(argv), cwd))
        return 0, "Python test version", ""

    monkeypatch.setattr("scripts.baseline_reproduction_preflight.command", fake_command)
    environment = Path(sys.executable).resolve().parents[1]
    source_path = tmp_path / "source"

    report = check_python_environment(
        environment,
        modules=("example_package",),
        pythonpath=(source_path,),
        env={"EXAMPLE_SETTING": "enabled"},
        cwd=tmp_path,
    )

    assert report["blockers"] == []
    assert report["cwd"] == str(tmp_path.resolve())
    assert report["pythonpath"] == [str(source_path.resolve())]
    assert calls[0][1] == tmp_path
    program = calls[0][0][-1]
    assert str(source_path.resolve()) in program
    assert "EXAMPLE_SETTING" in program
    assert "import example_package" in program


def test_current_preflight_is_read_only_and_blocks_gpu_execution() -> None:
    source_root = ROOT / "external"
    source_checkouts_present = all(
        (source_root / name / ".git").exists()
        for name in ("SAFE", "SAFE-openpi", "fiper")
    )
    report = collect_preflight(
        ROOT,
        source_root=source_root if source_checkouts_present else None,
    )

    assert report["schema"] == "proofalign.baseline-reproduction-preflight.v1"
    assert report["ready"] is False
    assert report["gpu_execution_authorized"] is False
    assert report["safe_assets"]["checkpoint_ready"] is True
    assert report["safe_assets"]["rollout_ready"] is False
    assert any("SAFE official pi0-libero_10 rollout root" in blocker for blocker in report["blockers"])
    if source_checkouts_present:
        assert report["source_ready"] is True
        assert not any("submodule" in blocker for blocker in report["blockers"])
        assert report["input_readiness"]["safe_rollout"] is True
        assert report["input_readiness"]["safe_detector"] is False
        assert report["input_readiness"]["fiper"] is True
        assert all(
            not environment["blockers"]
            for environment in report["environments"].values()
        )
        assert report["git"]["safe"]["clean"] is True
        assert report["git"]["fiper"]["clean"] is True
    else:
        # A clean clone intentionally omits the ignored external checkouts.
        assert report["source_ready"] is False
        assert report["input_readiness"]["fiper"] is False
        assert report["git"]["safe"]["clean"] is None
        assert report["git"]["fiper"]["clean"] is None
        assert any("checkout missing" in blocker for blocker in report["blockers"])


def test_protocol_json_is_canonical_parseable() -> None:
    for path in (SAFE_PROTOCOL, FIPER_PROTOCOL, PHANTOM_R1_PROTOCOL):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema"].startswith("proofalign.")
