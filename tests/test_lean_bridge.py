from __future__ import annotations

from pathlib import Path

from proofalign.lean_bridge import LeanBridge, LeanCheck


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
    bridge._cached_project_check = LeanCheck(True, True, "lean")

    first = bridge.check_boolean_claim("claim", "true")
    second = bridge.check_boolean_claim("claim", "true")
    third = bridge.check_boolean_claim("other_claim", "Bool.not false")

    assert first.passed
    assert second.passed
    assert third.passed
    assert count_path.read_text(encoding="utf-8").splitlines() == ["run", "run"]


def test_missing_lean_fails_closed_by_default(tmp_path: Path):
    missing = tmp_path / "missing_lean"
    bridge = LeanBridge(command=str(missing))

    check = bridge.check_boolean_claim("claim", "true")

    assert check.mode == "unavailable"
    assert not check.available
    assert not check.passed
    assert "failed closed" in check.stderr


def test_missing_lean_allows_only_explicit_diagnostic_mock(tmp_path: Path):
    missing = tmp_path / "missing_lean"
    bridge = LeanBridge(command=str(missing), allow_mock=True)

    check = bridge.check_boolean_claim("claim", "true")

    assert check.mode == "mock"
    assert not check.available
    assert check.passed
    assert "explicit diagnostic mock" in check.stderr


def test_project_compile_failure_fails_before_generated_claim(tmp_path: Path):
    count_path = tmp_path / "count.txt"
    lean_path = tmp_path / "failing_lean"
    lean_path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf 'run\\n' >> {str(count_path)!r}\n"
        "printf 'compile failed' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    lean_path.chmod(0o755)
    bridge = LeanBridge(command=str(lean_path))
    bridge._lake_command = lambda: None  # type: ignore[method-assign]

    check = bridge.check_boolean_claim("claim", "true")

    assert check.mode == "lean"
    assert check.available
    assert not check.passed
    assert "project build failed" in check.stderr
    assert count_path.read_text(encoding="utf-8").splitlines() == ["run"]
