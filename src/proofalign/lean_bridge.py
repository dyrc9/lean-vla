from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LeanCheck:
    available: bool
    passed: bool
    mode: str
    stdout: str = ""
    stderr: str = ""


class LeanBridge:
    """Small bridge to Lean 4.

    Lean is treated as a trusted checker for symbolic contracts. Safety checks
    fail closed when Lean is unavailable or the project does not compile.
    ``allow_mock`` exists only for explicit diagnostics and demonstrations; it
    must never be enabled on an execution-authorisation path.
    """

    def __init__(
        self,
        lean_root: Path | None = None,
        command: str | None = None,
        *,
        allow_mock: bool = False,
    ) -> None:
        self.lean_root = lean_root or Path(__file__).resolve().parents[2] / "lean"
        bundled = Path("/home/ldx/.local/lean-4.24.0/bin/lean")
        self.command = command or (str(bundled) if bundled.exists() else "lean")
        self.allow_mock = allow_mock
        self.lake_command = "lake"
        self._cached_project_check: LeanCheck | None = None
        self._cached_boolean_checks: dict[str, LeanCheck] = {}

    @property
    def available(self) -> bool:
        return Path(self.command).exists() or shutil.which(self.command) is not None

    def _lake_command(self) -> str | None:
        bundled = Path(self.command).with_name("lake")
        if bundled.exists():
            return str(bundled)
        return shutil.which(self.lake_command)

    def check_project(self) -> LeanCheck:
        if self._cached_project_check is not None:
            return self._cached_project_check
        if not self.available:
            self._cached_project_check = self._unavailable_check()
            return self._cached_project_check
        lake = self._lake_command()
        if lake:
            proc = subprocess.run(
                [lake, "build", "ProofAlign"],
                cwd=str(self.lean_root),
                text=True,
                capture_output=True,
                check=False,
            )
            self._cached_project_check = LeanCheck(True, proc.returncode == 0, "lean", proc.stdout, proc.stderr)
            return self._cached_project_check
        core = self.lean_root / "ProofAlign" / "Examples.lean"
        proc = subprocess.run(
            [self.command, str(core)],
            cwd=str(self.lean_root),
            text=True,
            capture_output=True,
            check=False,
        )
        self._cached_project_check = LeanCheck(True, proc.returncode == 0, "lean", proc.stdout, proc.stderr)
        return self._cached_project_check

    def check_boolean_claim(self, name: str, expression: str) -> LeanCheck:
        """Ask Lean to check a generated proposition of shape `example : expr = true`."""

        cached = self._cached_boolean_checks.get(expression)
        if cached is not None:
            return cached
        if not self.available:
            check = self._unavailable_check()
            self._cached_boolean_checks[expression] = check
            return check
        project_check = self.check_project()
        if not project_check.passed:
            check = LeanCheck(
                available=True,
                passed=False,
                mode="lean",
                stdout=project_check.stdout,
                stderr=(
                    "Lean project build failed; generated safety claim was not executed.\n"
                    f"{project_check.stderr}"
                ).strip(),
            )
            self._cached_boolean_checks[expression] = check
            return check
        snippet = f'import ProofAlign.Examples\n\nexample : {expression} = true := by decide\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{name}.lean"
            path.write_text(snippet, encoding="utf-8")
            lake = self._lake_command()
            if lake:
                cmd = [lake, "env", self.command, str(path)]
            else:
                cmd = [self.command, str(path)]
            proc = subprocess.run(cmd, cwd=str(self.lean_root), text=True, capture_output=True, check=False)
        check = LeanCheck(True, proc.returncode == 0, "lean", proc.stdout, proc.stderr)
        self._cached_boolean_checks[expression] = check
        return check

    def _unavailable_check(self) -> LeanCheck:
        if self.allow_mock:
            return LeanCheck(
                available=False,
                passed=True,
                mode="mock",
                stderr="Lean executable not found; explicit diagnostic mock mode is enabled.",
            )
        return LeanCheck(
            available=False,
            passed=False,
            mode="unavailable",
            stderr="Lean executable not found; safety check failed closed.",
        )
