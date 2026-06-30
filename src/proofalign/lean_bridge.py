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

    Lean is treated as a trusted checker for symbolic contracts. If Lean is not
    available, the caller still receives a stable interface in explicit mock
    fallback mode.
    """

    def __init__(self, lean_root: Path | None = None, command: str = "lean") -> None:
        self.lean_root = lean_root or Path(__file__).resolve().parents[2] / "lean"
        self.command = command
        self.lake_command = "lake"
        self._cached_project_check: LeanCheck | None = None

    @property
    def available(self) -> bool:
        return shutil.which(self.command) is not None

    def check_project(self) -> LeanCheck:
        if self._cached_project_check is not None:
            return self._cached_project_check
        if not self.available:
            self._cached_project_check = LeanCheck(
                False, True, "mock", stderr="Lean executable not found; using prototype mock mode."
            )
            return self._cached_project_check
        if shutil.which(self.lake_command):
            proc = subprocess.run(
                [self.lake_command, "build", "ProofAlign"],
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

        if not self.available:
            return LeanCheck(False, True, "mock", stderr="Lean executable not found; using prototype mock mode.")
        self.check_project()
        snippet = f'import ProofAlign.Examples\n\nexample : {expression} = true := by decide\n'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{name}.lean"
            path.write_text(snippet, encoding="utf-8")
            if shutil.which(self.lake_command):
                cmd = [self.lake_command, "env", self.command, str(path)]
            else:
                cmd = [self.command, str(path)]
            proc = subprocess.run(cmd, cwd=str(self.lean_root), text=True, capture_output=True, check=False)
        return LeanCheck(True, proc.returncode == 0, "lean", proc.stdout, proc.stderr)
