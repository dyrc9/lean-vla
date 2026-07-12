from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_reproduction_targets_are_unique_versioned_and_fail_closed() -> None:
    payload = json.loads(
        (ROOT / "experiments" / "reproduction_targets.json").read_text(encoding="utf-8")
    )
    targets = payload["targets"]
    ids = [target["id"] for target in targets]
    allowed_statuses = {
        "planned",
        "environment_ready",
        "reproduced_upstream",
        "adapter_ready",
        "main_evaluated",
        "blocked_upstream",
    }

    assert payload["schema"] == "proofalign.reproduction-targets.v1"
    assert len(ids) == len(set(ids))
    assert {"saber", "phantom-menace", "safe-failure-detector", "fiper"} <= set(ids)
    assert any(target["priority"] == "P0" and "attack" in target["role"] for target in targets)
    assert any(
        target["priority"] == "P0" and target["role"] == "runtime_defense"
        for target in targets
    )
    for target in targets:
        assert target["status"] in allowed_statuses
        assert target["priority"] in {"P0", "P1"}
        assert target["paper"].startswith("https://")
        assert target["repository"].startswith("https://github.com/")
        commit = target["upstream_commit"]
        assert commit is None or re.fullmatch(r"[0-9a-f]{40}", commit)
        if target["status"] != "planned":
            assert commit is not None
