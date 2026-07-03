from __future__ import annotations

from pathlib import Path

from proofalign.lean_bridge import LeanBridge


def test_boolean_claim_cache_reuses_identical_expression(tmp_path: Path):
    count_path = tmp_path / "count.txt"
    lean_path = tmp_path / "fake_lean"
    lean_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'run\\n' >> {str(count_path)!r}\n"
        "exit 0\n",
        encoding="utf-8",
    )
    lean_path.chmod(0o755)

    bridge = LeanBridge(command=str(lean_path))

    first = bridge.check_boolean_claim("claim", "true")
    second = bridge.check_boolean_claim("claim", "true")
    third = bridge.check_boolean_claim("other_claim", "Bool.not false")

    assert first.passed
    assert second.passed
    assert third.passed
    assert count_path.read_text(encoding="utf-8").splitlines() == ["run", "run", "run"]


def test_missing_lean_still_uses_mock_without_cache_error(tmp_path: Path):
    missing = tmp_path / "missing_lean"
    bridge = LeanBridge(command=str(missing))

    check = bridge.check_boolean_claim("claim", "true")

    assert check.mode == "mock"
    assert check.passed
