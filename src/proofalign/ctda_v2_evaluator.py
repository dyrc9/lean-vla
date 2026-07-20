"""Fail-closed Python/Lean parity evaluators for ``ctda-wire-v2``.

The evaluator is an offline/no-dispatch boundary.  A successful result proves
only that Lean evaluated the canonical normalized payload to the same verdict as
the independent Python reference; it never sends a command to an environment or
actuator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping

from proofalign.ctda_v2_wire import (
    V2WireEnvelope,
    V2WireStage,
    V2WireValidationError,
    V2WireVerdict,
    canonical_v2_wire_bytes,
    decode_v2_wire_envelope,
    reference_v2_wire_verdict,
)


class CTDAV2EvaluatorMode(str, Enum):
    PYTHON_REFERENCE = "ctda-v2-python-reference"
    LEAN_KERNEL = "ctda-v2-lean-kernel"
    SHADOW = "ctda-v2-shadow"


@dataclass(frozen=True)
class CTDAV2EvaluationArtifact:
    mode: CTDAV2EvaluatorMode
    stage: V2WireStage
    request_id: str
    verdict: str
    proof_verified: bool
    elapsed_ns: int
    canonical_request_utf8: str
    generated_lean_source: str
    checker_source_digest: str
    checker_build_digest: str
    cache_key: str
    stdout: str = ""
    stderr: str = ""
    artifact_dir: str | None = None
    cache_hit: bool = False
    parity_match: bool | None = None


@dataclass(frozen=True)
class CTDAV2EvaluationResult:
    verdict: V2WireVerdict
    artifact: CTDAV2EvaluationArtifact

    @property
    def proven(self) -> bool:
        return self.verdict is V2WireVerdict.PROVEN and self.artifact.proof_verified


class CTDAV2PythonReferenceEvaluator:
    mode = CTDAV2EvaluatorMode.PYTHON_REFERENCE

    def __init__(self, checker_version_digest: str) -> None:
        self.checker_version_digest = checker_version_digest

    def evaluate(self, request: V2WireEnvelope | bytes | str) -> CTDAV2EvaluationResult:
        started = time.perf_counter_ns()
        decoded = _decode_for_evaluator(request, self.checker_version_digest)
        verdict = reference_v2_wire_verdict(decoded)
        return CTDAV2EvaluationResult(
            verdict,
            CTDAV2EvaluationArtifact(
                mode=self.mode,
                stage=decoded.stage,
                request_id=decoded.request_id,
                verdict=verdict.value,
                proof_verified=False,
                elapsed_ns=time.perf_counter_ns() - started,
                canonical_request_utf8=decoded.canonical_bytes().decode("utf-8"),
                generated_lean_source="",
                checker_source_digest=self.checker_version_digest,
                checker_build_digest=self.checker_version_digest,
                cache_key=_cache_key(
                    decoded,
                    self.mode,
                    self.checker_version_digest,
                    self.checker_version_digest,
                ),
            ),
        )


class CTDAV2LeanKernelEvaluator:
    mode = CTDAV2EvaluatorMode.LEAN_KERNEL

    def __init__(
        self,
        *,
        lean_root: Path | None = None,
        artifact_root: Path | None = None,
        lean_command: str = "lean",
        timeout_seconds: float = 15.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Lean evaluator timeout must be positive")
        self.lean_root = lean_root or Path(__file__).resolve().parents[2] / "lean"
        self.artifact_root = artifact_root
        self.lean_command = lean_command
        self.timeout_seconds = timeout_seconds
        self.checker_source = self.lean_root / "ProofAlign" / "CTDAV2Wire.lean"
        self.kernel_source = self.lean_root / "ProofAlign" / "CTDAV2.lean"
        self.checker_source_digest = _digest_files((self.checker_source, self.kernel_source))
        self.checker_build_digest = _digest_files(
            (
                self.checker_source,
                self.kernel_source,
                self.lean_root / "ProofAlign.lean",
                self.lean_root / "lean-toolchain",
                self.lean_root / "lakefile.lean",
                self.lean_root
                / ".lake"
                / "build"
                / "lib"
                / "lean"
                / "ProofAlign"
                / "CTDAV2Wire.olean",
            )
        )
        self.checker_version_digest = sha256(
            canonical_v2_wire_bytes(
                {
                    "schema_version": "ctda-wire-v2",
                    "method_id": "ctda-v2",
                    "checker_source_digest": self.checker_source_digest,
                    "checker_build_digest": self.checker_build_digest,
                }
            )
        ).hexdigest()
        self._cache: dict[str, CTDAV2EvaluationResult] = {}
        self._project_built = False

    @property
    def available(self) -> bool:
        return _resolve_command(self.lean_command) is not None and _resolve_command("lake") is not None

    def evaluate(self, request: V2WireEnvelope | bytes | str) -> CTDAV2EvaluationResult:
        started = time.perf_counter_ns()
        try:
            decoded = _decode_for_evaluator(request, self.checker_version_digest)
        except V2WireValidationError as exc:
            return self._failure_result(
                request,
                started,
                f"v2 wire serialization/validation failure: {exc}",
            )
        expected = reference_v2_wire_verdict(decoded)
        source = generate_v2_lean_replay_source(decoded, expected)
        key = _cache_key(
            decoded,
            self.mode,
            self.checker_source_digest,
            self.checker_build_digest,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return CTDAV2EvaluationResult(
                cached.verdict,
                replace(
                    cached.artifact,
                    elapsed_ns=time.perf_counter_ns() - started,
                    cache_hit=True,
                ),
            )
        artifact_dir = self._artifact_dir(decoded.request_id)
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "request.json").write_bytes(decoded.canonical_bytes())
            (artifact_dir / "Replay.lean").write_text(source, encoding="utf-8")
        if not self.available:
            return self._failure_result(
                decoded,
                started,
                "Lean or lake executable is unavailable; v2 authorization failed closed",
                source=source,
                cache_key=key,
                artifact_dir=artifact_dir,
            )
        try:
            build = self._ensure_project_build()
            if build.returncode != 0:
                return self._failure_result(
                    decoded,
                    started,
                    "Lean project build failed",
                    source=source,
                    stdout=build.stdout,
                    stderr=build.stderr,
                    cache_key=key,
                    artifact_dir=artifact_dir,
                )
            with tempfile.TemporaryDirectory() as temporary:
                replay = Path(temporary) / "Replay.lean"
                replay.write_text(source, encoding="utf-8")
                proc = subprocess.run(
                    ["lake", "env", self.lean_command, str(replay)],
                    cwd=self.lean_root,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.timeout_seconds,
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return self._failure_result(
                decoded,
                started,
                f"Lean v2 evaluator execution failed: {exc}",
                source=source,
                cache_key=key,
                artifact_dir=artifact_dir,
            )
        proof_verified = proc.returncode == 0
        verdict = expected if proof_verified else V2WireVerdict.INCONSISTENT
        artifact = CTDAV2EvaluationArtifact(
            mode=self.mode,
            stage=decoded.stage,
            request_id=decoded.request_id,
            verdict=verdict.value,
            proof_verified=proof_verified,
            elapsed_ns=time.perf_counter_ns() - started,
            canonical_request_utf8=decoded.canonical_bytes().decode("utf-8"),
            generated_lean_source=source,
            checker_source_digest=self.checker_source_digest,
            checker_build_digest=self.checker_build_digest,
            cache_key=key,
            stdout=proc.stdout,
            stderr=proc.stderr,
            artifact_dir=str(artifact_dir) if artifact_dir is not None else None,
            parity_match=proof_verified,
        )
        result = CTDAV2EvaluationResult(verdict, artifact)
        self._persist_result(artifact_dir, artifact)
        if proof_verified:
            self._cache[key] = result
        return result

    def _ensure_project_build(self) -> subprocess.CompletedProcess[str]:
        if self._project_built:
            return subprocess.CompletedProcess([], 0, "cached project build", "")
        proc = subprocess.run(
            ["lake", "build", "ProofAlign"],
            cwd=self.lean_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=max(self.timeout_seconds, 30.0),
        )
        self._project_built = proc.returncode == 0
        return proc

    def _artifact_dir(self, request_id: str) -> Path | None:
        return self.artifact_root / request_id if self.artifact_root is not None else None

    def _failure_result(
        self,
        request: V2WireEnvelope | bytes | str,
        started: int,
        stderr: str,
        *,
        source: str = "",
        stdout: str = "",
        cache_key: str = "",
        artifact_dir: Path | None = None,
    ) -> CTDAV2EvaluationResult:
        if isinstance(request, V2WireEnvelope):
            stage = request.stage
            request_id = request.request_id
            canonical = request.canonical_bytes().decode("utf-8")
        else:
            stage = V2WireStage.SEMANTIC_CERTIFICATE
            request_id = "invalid-v2-request"
            canonical = (
                request.decode("utf-8", errors="replace")
                if isinstance(request, bytes)
                else str(request)
            )
        artifact = CTDAV2EvaluationArtifact(
            mode=self.mode,
            stage=stage,
            request_id=request_id,
            verdict=V2WireVerdict.INCONSISTENT.value,
            proof_verified=False,
            elapsed_ns=time.perf_counter_ns() - started,
            canonical_request_utf8=canonical,
            generated_lean_source=source,
            checker_source_digest=self.checker_source_digest,
            checker_build_digest=self.checker_build_digest,
            cache_key=cache_key,
            stdout=stdout,
            stderr=stderr,
            artifact_dir=str(artifact_dir) if artifact_dir is not None else None,
            parity_match=False,
        )
        self._persist_result(artifact_dir, artifact)
        return CTDAV2EvaluationResult(V2WireVerdict.INCONSISTENT, artifact)

    @staticmethod
    def _persist_result(
        artifact_dir: Path | None, artifact: CTDAV2EvaluationArtifact
    ) -> None:
        if artifact_dir is None:
            return
        artifact_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(artifact)
        payload["mode"] = artifact.mode.value
        payload["stage"] = artifact.stage.value
        (artifact_dir / "result.json").write_bytes(canonical_v2_wire_bytes(payload))
        (artifact_dir / "stdout.txt").write_text(artifact.stdout, encoding="utf-8")
        (artifact_dir / "stderr.txt").write_text(artifact.stderr, encoding="utf-8")


class CTDAV2ShadowEvaluator:
    """Diagnostic parity mode; a matching shadow result never authorizes."""

    mode = CTDAV2EvaluatorMode.SHADOW

    def __init__(
        self,
        python_evaluator: CTDAV2PythonReferenceEvaluator,
        lean_evaluator: CTDAV2LeanKernelEvaluator,
    ) -> None:
        self.python_evaluator = python_evaluator
        self.lean_evaluator = lean_evaluator
        self.checker_version_digest = lean_evaluator.checker_version_digest

    def evaluate(self, request: V2WireEnvelope | bytes | str) -> CTDAV2EvaluationResult:
        started = time.perf_counter_ns()
        python_result = self.python_evaluator.evaluate(request)
        lean_result = self.lean_evaluator.evaluate(request)
        match = (
            lean_result.artifact.proof_verified
            and python_result.verdict is lean_result.verdict
        )
        verdict = python_result.verdict if match else V2WireVerdict.INCONSISTENT
        artifact = replace(
            lean_result.artifact,
            mode=self.mode,
            verdict=verdict.value,
            proof_verified=False,
            elapsed_ns=time.perf_counter_ns() - started,
            parity_match=match,
            stderr=(
                lean_result.artifact.stderr
                if match
                else (
                    lean_result.artifact.stderr
                    + "\nCTDA v2 Python/Lean parity mismatch or Lean proof failure"
                ).strip()
            ),
        )
        return CTDAV2EvaluationResult(verdict, artifact)


_STAGE_REPLAY = {
    V2WireStage.SEMANTIC_CERTIFICATE: (
        "SemanticCertificatePayload",
        "checkSemanticCertificate",
    ),
    V2WireStage.STATE_REBIND: ("StateRebindPayload", "checkStateRebind"),
    V2WireStage.PREFIX_DECISION: ("PrefixDecisionPayload", "checkPrefixDecision"),
    V2WireStage.PREFIX_AUTHORIZATION: (
        "PrefixAuthorizationPayload",
        "checkPrefixAuthorization",
    ),
    V2WireStage.DISPATCH_RECEIPT: ("DispatchReceiptPayload", "checkDispatchReceipt"),
    V2WireStage.PROGRESS_UPDATE: ("ProgressUpdatePayload", "checkProgressUpdate"),
}

_VERDICT_FIELDS = {
    "certificate_verdict",
    "lease_verdict",
    "decision_verdict",
    "authorization_verdict",
}


def generate_v2_lean_replay_source(
    request: V2WireEnvelope,
    expected: V2WireVerdict,
) -> str:
    type_name, check = _STAGE_REPLAY[request.stage]
    fields = []
    for name, value in request.payload.items():
        if name in {"method_id", "schema_version"}:
            continue
        fields.append((_snake_to_camel(name), _lean_value(name, value)))
    assignments = "\n".join(f"    {name} := {value}" for name, value in fields)
    return (
        "import ProofAlign.CTDAV2Wire\n\n"
        "open ProofAlign.CTDAV2\n"
        "open ProofAlign.WireV2\n\n"
        f"def replayRequest : {type_name} :=\n"
        "  {\n"
        f"{assignments}\n"
        "  }\n\n"
        f"example : {check} replayRequest = {_lean_verdict(expected)} := by decide\n"
    )


def _lean_value(name: str, value: Any) -> str:
    if name in _VERDICT_FIELDS:
        return _lean_verdict(V2WireVerdict(value))
    if name == "intervention":
        return {
            "pass": "Intervention.pass",
            "project_or_brake": "Intervention.projectOrBrake",
            "replan": "Intervention.replan",
            "hard_block": "Intervention.hardBlock",
        }[value]
    if value is None:
        return "none"
    if name in {"distance_before_um", "distance_after_um"}:
        return f"some {value}"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_lean_string(item) for item in value) + "]"
    if isinstance(value, str):
        text = _lean_string(value)
        if name in {
            "adjusted_command_digest",
            "filter_application_digest",
            "filter_nominal_command_digest",
            "filter_adjusted_command_digest",
            "membership_attestation_subject_digest",
            "decision_adjusted_command_digest",
        }:
            return f"some ({text})"
        return text
    raise TypeError(f"unsupported normalized v2 wire value for {name}")


def _lean_string(value: str) -> str:
    return "(String.mk [" + ", ".join(f"Char.ofNat {ord(char)}" for char in value) + "])"


def _lean_verdict(verdict: V2WireVerdict) -> str:
    names = {
        V2WireVerdict.PROVEN: "proven",
        V2WireVerdict.REFUTED: "refuted",
        V2WireVerdict.REPLAN: "replan",
        V2WireVerdict.HARD_BLOCK: "hardBlock",
        V2WireVerdict.INCONSISTENT: "inconsistent",
    }
    return f"V2Result.{names[verdict]}"


def _snake_to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item[:1].upper() + item[1:] for item in tail)


def _decode_for_evaluator(
    request: V2WireEnvelope | bytes | str,
    checker_version_digest: str,
) -> V2WireEnvelope:
    decoded = decode_v2_wire_envelope(
        request.canonical_bytes() if isinstance(request, V2WireEnvelope) else request
    )
    if decoded.checker_version_digest != checker_version_digest:
        raise V2WireValidationError(
            "v2 request checker_version_digest does not match the consumer"
        )
    return decoded


def _cache_key(
    request: V2WireEnvelope,
    mode: CTDAV2EvaluatorMode,
    checker_source_digest: str,
    checker_build_digest: str,
) -> str:
    return sha256(
        canonical_v2_wire_bytes(
            {
                "mode": mode.value,
                "schema_version": "ctda-wire-v2",
                "request": request.to_dict(),
                "checker_source_digest": checker_source_digest,
                "checker_build_digest": checker_build_digest,
            }
        )
    ).hexdigest()


def _digest_files(paths: tuple[Path, ...]) -> str:
    digest = sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
    return digest.hexdigest()


def _resolve_command(command: str) -> str | None:
    path = Path(command)
    if path.is_absolute():
        return str(path) if path.exists() else None
    return shutil.which(command)


__all__ = [
    "CTDAV2EvaluationArtifact",
    "CTDAV2EvaluationResult",
    "CTDAV2EvaluatorMode",
    "CTDAV2LeanKernelEvaluator",
    "CTDAV2PythonReferenceEvaluator",
    "CTDAV2ShadowEvaluator",
    "generate_v2_lean_replay_source",
]
