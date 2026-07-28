from __future__ import annotations

import json

from scripts.run_pick_up_prefix_progress_replay_qualification import (
    CHECKSUMS_PATH,
    PROTOCOL_PATH,
    RESULT_PATH,
    build_protocol,
    canonical_text,
    file_sha256,
    validate_protocol,
    validate_result,
)


def test_pick_up_prefix_progress_replay_is_current_and_qualified() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    validate_protocol(protocol)
    validate_result(protocol, result)
    assert PROTOCOL_PATH.read_text(
        encoding="utf-8"
    ) == canonical_text(build_protocol())
    assert CHECKSUMS_PATH.read_text(encoding="utf-8") == (
        f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
    )
    assert (
        result["classification"]
        == "pick_up_prefix_progress_replay_qualified"
    )
    assert result["summary"]["prior_allow_regression_count"] == 0
    assert (
        result["summary"]["recovered_prior_dual_reject_count"]
        == 12
    )
    assert result["summary"]["remaining_prior_dual_reject_count"] == 0
    assert result["summary"]["holding_target_synthesis_count"] == 0
    assert all(result["summary"]["gate_results"].values())
