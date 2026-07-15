from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.baseline_reproduction_preflight import (
    FIPER_PROTOCOL,
    SAFE_PROTOCOL,
    ProtocolError,
    check_fiper_assets,
    collect_preflight,
    load_json,
    validate_fiper_protocol,
    validate_safe_protocol,
)


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_baseline_protocols_validate() -> None:
    validate_safe_protocol(load_json(SAFE_PROTOCOL))
    validate_fiper_protocol(load_json(FIPER_PROTOCOL))


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


def test_current_preflight_is_read_only_and_blocks_gpu_execution() -> None:
    report = collect_preflight(ROOT)

    assert report["schema"] == "proofalign.baseline-reproduction-preflight.v1"
    assert report["ready"] is False
    assert report["source_ready"] is True
    assert report["gpu_execution_authorized"] is False
    assert not any("submodule" in blocker for blocker in report["blockers"])
    assert report["input_readiness"]["fiper"] is True
    assert report["safe_assets"]["checkpoint_ready"] is True
    assert report["safe_assets"]["rollout_ready"] is False
    assert any("SAFE official pi0-libero_10 rollout root" in blocker for blocker in report["blockers"])
    assert report["git"]["safe"]["clean"] is True
    assert report["git"]["fiper"]["clean"] is True


def test_protocol_json_is_canonical_parseable() -> None:
    for path in (SAFE_PROTOCOL, FIPER_PROTOCOL):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["schema"].startswith("proofalign.")
