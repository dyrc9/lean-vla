from __future__ import annotations

from pathlib import Path

import pytest

from scripts.generate_v15_system_overhead_analysis import (
    ATTACKED_TERMINAL_PATH,
    CLEAN_TERMINAL_PATH,
    build_analysis,
    render_markdown,
)


pytestmark = pytest.mark.skipif(
    not CLEAN_TERMINAL_PATH.is_file() or not ATTACKED_TERMINAL_PATH.is_file(),
    reason="local frozen v15.3 task terminal summaries are absent",
)


def _bound_result_files_are_local() -> bool:
    if not CLEAN_TERMINAL_PATH.is_file() or not ATTACKED_TERMINAL_PATH.is_file():
        return False
    # The committed terminal summaries bind ignored runtime roots.  The test
    # remains portable by skipping when those local result bundles are absent.
    import json

    clean = json.loads(CLEAN_TERMINAL_PATH.read_text(encoding="utf-8"))
    attacked = json.loads(ATTACKED_TERMINAL_PATH.read_text(encoding="utf-8"))
    paths = (
        clean["bindings"]["evidence"]["path"],
        attacked["bindings"]["attacked_evidence"]["path"],
    )
    root = Path(__file__).resolve().parents[1]
    return all((root / path).is_file() for path in paths)


@pytest.mark.skipif(
    not _bound_result_files_are_local(),
    reason="local frozen v15.3 task result bundles are absent",
)
def test_system_overhead_recomputes_frozen_task_rollouts() -> None:
    payload = build_analysis()

    clean = payload["conditions"]["clean"]
    attacked = payload["conditions"]["attacked"]
    assert clean["verified_episode_artifact_count"] == 72
    assert attacked["verified_episode_artifact_count"] == 72
    assert clean["combined_l2_screen_latency_seconds"]["count"] == 11801
    assert attacked["combined_l2_screen_latency_seconds"]["count"] == 13827
    assert clean["by_arm"]["execution_only"]["screen_category_counts"] == {
        "deadlock": 1,
        "recovery_intervention": 512,
        "standard_intervention": 8,
        "untriggered": 5495,
    }
    assert clean["by_arm"]["dual"]["screen_category_counts"] == {
        "recovery_intervention": 207,
        "standard_intervention": 17,
        "untriggered": 5561,
    }
    assert attacked["by_arm"]["execution_only"]["screen_category_counts"] == {
        "recovery_intervention": 106,
        "standard_intervention": 6,
        "untriggered": 7193,
    }
    assert attacked["by_arm"]["dual"]["screen_category_counts"] == {
        "recovery_intervention": 15,
        "standard_intervention": 3,
        "untriggered": 6504,
    }
    assert all(
        payload["explicit_nonclaims"][key] is False
        for key in (
            "causal_cross_arm_wall_time_overhead",
            "hard_real_time",
            "hardware",
            "attacked_nonpass_superseded",
        )
    )


@pytest.mark.skipif(
    not _bound_result_files_are_local(),
    reason="local frozen v15.3 task result bundles are absent",
)
def test_system_overhead_markdown_keeps_deadline_boundary_visible() -> None:
    markdown = render_markdown(build_analysis())

    assert "50 ms 是控制周期诊断" in markdown
    assert "100 ms" in markdown
    assert "不能把 cross-arm wall time 差直接解释为因果 overhead" in markdown
