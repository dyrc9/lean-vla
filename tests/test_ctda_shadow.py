from __future__ import annotations

from pathlib import Path

from proofalign.ctda_shadow import _load_fixture, golden_scenario, run_shadow_fixture
from proofalign.ctda_wire import make_wire_request


ROOT = Path(__file__).resolve().parents[1]


def test_golden_shadow_corpus_has_zero_python_lean_mismatch_and_audit_output(
    tmp_path: Path,
) -> None:
    report = run_shadow_fixture(
        ROOT / "tests" / "fixtures" / "ctda_golden.json",
        artifact_root=tmp_path / "artifacts",
        timeout_seconds=20,
    )

    assert report["mode"] == "ctda-shadow"
    assert report["parity_mismatch"] == 0
    assert report["expected_mismatch"] == 0
    assert report["supported"] == 27
    assert report["unknown"] == 3
    assert report["unique_catches"]["layer1_only"] >= 1
    assert report["unique_catches"]["layer2_only"] >= 1
    assert report["unique_catches"]["dual"] == 1
    assert report["monitor_verdicts"] == {
        "safe_pending": 2,
        "complete": 2,
        "violated": 1,
        "unknown": 0,
        "inconsistent": 3,
    }
    assert report["metrics"]["false_block_rate"] == "not_evaluated"
    assert report["metrics"]["detection_tpr"] == "not_evaluated"
    assert report["label_provenance"]["kind"] == "none"
    assert set(report["latency_ns"]) == {
        "semantic",
        "prefix_pre",
        "observed_prefix",
        "monitor_step",
    }
    for stage in report["latency_ns"].values():
        for evaluator in ("python_ns", "lean_ns"):
            assert set(stage[evaluator]) == {"p50", "p95", "p99"}
            assert all(isinstance(value, int) for value in stage[evaluator].values())
    assert report["digests"]["schema_digest"]
    assert report["digests"]["checker_version_digest"]
    assert report["digests"]["checker_source_digest"]
    assert report["digests"]["checker_build_digest"]
    assert report["digests"]["config_digest"]
    assert report["digests"]["git_digest"] != "unavailable"
    assert all(
        row["proof_verified"]
        for case in report["cases"]
        for row in case["verdicts"]
    )


def test_shadow_loader_accepts_saved_wire_jsonl(tmp_path: Path) -> None:
    stage, payload = golden_scenario("prefix_proven")
    request = make_wire_request(stage, "1" * 64, payload)
    path = tmp_path / "prefixes.jsonl"
    path.write_bytes(request.canonical_bytes() + b"\n")

    fixture = _load_fixture(path)

    assert fixture["cases"][0]["stage"] == "prefix_pre"
    assert fixture["cases"][0]["payload"]["episode_nonce"] == "episode"
    assert fixture["label_provenance"]["kind"] == "none"
