"""Fail-closed evaluators for canonical CTDA wire requests."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Protocol

from proofalign.ctda_wire import (
    CTDAWireRequest,
    SCHEMA_VERSION,
    WireMonitorVerdict,
    WireStage,
    WireStaticVerdict,
    WireValidationError,
    canonical_wire_bytes,
    decode_wire_request,
    reference_wire_verdict,
)


class CTDAEvaluatorMode(str, Enum):
    PYTHON_REFERENCE = "ctda-python-reference"
    LEAN_KERNEL = "ctda-lean-kernel"
    SHADOW = "ctda-shadow"


@dataclass(frozen=True)
class CTDAEvaluationArtifact:
    mode: CTDAEvaluatorMode
    stage: WireStage
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
class CTDAEvaluationResult:
    verdict: WireStaticVerdict | WireMonitorVerdict
    artifact: CTDAEvaluationArtifact

    @property
    def proven(self) -> bool:
        return self.verdict is WireStaticVerdict.PROVEN and self.artifact.proof_verified


class CTDAEvaluator(Protocol):
    mode: CTDAEvaluatorMode
    checker_version_digest: str

    def evaluate(self, request: CTDAWireRequest | bytes) -> CTDAEvaluationResult:
        ...


class PythonReferenceEvaluator:
    mode = CTDAEvaluatorMode.PYTHON_REFERENCE

    def __init__(self, checker_version_digest: str) -> None:
        self.checker_version_digest = checker_version_digest

    def evaluate(self, request: CTDAWireRequest | bytes) -> CTDAEvaluationResult:
        started = time.perf_counter_ns()
        decoded = _decode_for_evaluator(request, self.checker_version_digest)
        verdict = reference_wire_verdict(decoded)
        elapsed = time.perf_counter_ns() - started
        cache_key = _cache_key(
            decoded,
            self.mode,
            self.checker_version_digest,
            self.checker_version_digest,
        )
        return CTDAEvaluationResult(
            verdict,
            CTDAEvaluationArtifact(
                mode=self.mode,
                stage=decoded.stage,
                request_id=decoded.request_id,
                verdict=verdict.value,
                proof_verified=False,
                elapsed_ns=elapsed,
                canonical_request_utf8=decoded.canonical_bytes().decode("utf-8"),
                generated_lean_source="",
                checker_source_digest=self.checker_version_digest,
                checker_build_digest=self.checker_version_digest,
                cache_key=cache_key,
            ),
        )


class LeanKernelEvaluator:
    mode = CTDAEvaluatorMode.LEAN_KERNEL

    def __init__(
        self,
        *,
        lean_root: Path | None = None,
        artifact_root: Path | None = None,
        lean_command: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.lean_root = lean_root or Path(__file__).resolve().parents[2] / "lean"
        self.artifact_root = artifact_root
        self.lean_command = lean_command or "lean"
        self.timeout_seconds = timeout_seconds
        if timeout_seconds <= 0:
            raise ValueError("Lean evaluator timeout must be positive")
        self.checker_source = self.lean_root / "ProofAlign" / "CTDAWire.lean"
        self.checker_source_digest = _digest_files((self.checker_source,))
        self.checker_build_digest = _digest_files(
            (
                self.checker_source,
                self.lean_root / "ProofAlign.lean",
                self.lean_root / "lean-toolchain",
                self.lean_root / "lakefile.lean",
                self.lean_root / "lake-manifest.json",
                self.lean_root
                / ".lake"
                / "build"
                / "lib"
                / "lean"
                / "ProofAlign"
                / "CTDAWire.olean",
            )
        )
        self.checker_version_digest = sha256(
            canonical_wire_bytes(
                {
                    "schema_version": SCHEMA_VERSION,
                    "checker_source_digest": self.checker_source_digest,
                    "checker_build_digest": self.checker_build_digest,
                }
            )
        ).hexdigest()
        self._cache: dict[str, CTDAEvaluationResult] = {}
        self._project_built = False

    @property
    def available(self) -> bool:
        return _resolve_command(self.lean_command) is not None and _resolve_command("lake") is not None

    def evaluate(self, request: CTDAWireRequest | bytes) -> CTDAEvaluationResult:
        started = time.perf_counter_ns()
        try:
            decoded = _decode_for_evaluator(request, self.checker_version_digest)
        except WireValidationError as exc:
            return self._failure_result(
                request,
                started,
                f"wire serialization/validation failure: {exc}",
            )
        expected = reference_wire_verdict(decoded)
        source = generate_lean_replay_source(decoded, expected)
        key = _cache_key(
            decoded,
            self.mode,
            self.checker_source_digest,
            self.checker_build_digest,
        )
        cached = self._cache.get(key)
        if cached is not None:
            artifact = replace(
                cached.artifact,
                elapsed_ns=time.perf_counter_ns() - started,
                cache_hit=True,
            )
            return CTDAEvaluationResult(cached.verdict, artifact)
        artifact_dir = self._artifact_dir(decoded.request_id)
        if artifact_dir is not None:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "request.json").write_bytes(decoded.canonical_bytes())
            (artifact_dir / "Replay.lean").write_text(source, encoding="utf-8")
        if not self.available:
            return self._failure_result(
                decoded,
                started,
                "Lean or lake executable is unavailable; authorization failed closed",
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
                f"Lean evaluator execution failed: {exc}",
                source=source,
                cache_key=key,
                artifact_dir=artifact_dir,
            )
        elapsed = time.perf_counter_ns() - started
        proof_verified = proc.returncode == 0
        verdict: WireStaticVerdict | WireMonitorVerdict = (
            expected
            if proof_verified
            else (
                WireMonitorVerdict.INCONSISTENT
                if decoded.stage is WireStage.MONITOR_STEP
                else WireStaticVerdict.INCONSISTENT
            )
        )
        artifact = CTDAEvaluationArtifact(
            mode=self.mode,
            stage=decoded.stage,
            request_id=decoded.request_id,
            verdict=verdict.value,
            proof_verified=proof_verified,
            elapsed_ns=elapsed,
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
        result = CTDAEvaluationResult(verdict, artifact)
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
        request: CTDAWireRequest | bytes,
        started: int,
        stderr: str,
        *,
        source: str = "",
        stdout: str = "",
        cache_key: str = "",
        artifact_dir: Path | None = None,
    ) -> CTDAEvaluationResult:
        stage = request.stage if isinstance(request, CTDAWireRequest) else WireStage.SEMANTIC
        request_id = request.request_id if isinstance(request, CTDAWireRequest) else "invalid-request"
        canonical = (
            request.canonical_bytes().decode("utf-8")
            if isinstance(request, CTDAWireRequest)
            else bytes(request).decode("utf-8", errors="replace")
        )
        verdict: WireStaticVerdict | WireMonitorVerdict = (
            WireMonitorVerdict.INCONSISTENT
            if stage is WireStage.MONITOR_STEP
            else WireStaticVerdict.INCONSISTENT
        )
        artifact = CTDAEvaluationArtifact(
            mode=self.mode,
            stage=stage,
            request_id=request_id,
            verdict=verdict.value,
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
        return CTDAEvaluationResult(verdict, artifact)

    @staticmethod
    def _persist_result(artifact_dir: Path | None, artifact: CTDAEvaluationArtifact) -> None:
        if artifact_dir is None:
            return
        artifact_dir.mkdir(parents=True, exist_ok=True)
        payload = asdict(artifact)
        payload["mode"] = artifact.mode.value
        payload["stage"] = artifact.stage.value
        (artifact_dir / "result.json").write_bytes(canonical_wire_bytes(payload))
        (artifact_dir / "stdout.txt").write_text(artifact.stdout, encoding="utf-8")
        (artifact_dir / "stderr.txt").write_text(artifact.stderr, encoding="utf-8")


class ShadowEvaluator:
    mode = CTDAEvaluatorMode.SHADOW

    def __init__(
        self,
        python_evaluator: PythonReferenceEvaluator,
        lean_evaluator: LeanKernelEvaluator,
    ) -> None:
        self.python_evaluator = python_evaluator
        self.lean_evaluator = lean_evaluator
        self.checker_version_digest = lean_evaluator.checker_version_digest

    def evaluate(self, request: CTDAWireRequest | bytes) -> CTDAEvaluationResult:
        started = time.perf_counter_ns()
        python_result = self.python_evaluator.evaluate(request)
        lean_result = self.lean_evaluator.evaluate(request)
        match = (
            lean_result.artifact.proof_verified
            and python_result.verdict.value == lean_result.verdict.value
        )
        verdict: WireStaticVerdict | WireMonitorVerdict = (
            python_result.verdict
            if match
            else (
                WireMonitorVerdict.INCONSISTENT
                if lean_result.artifact.stage is WireStage.MONITOR_STEP
                else WireStaticVerdict.INCONSISTENT
            )
        )
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
                    + "\nPython/Lean parity mismatch or Lean proof failure"
                ).strip()
            ),
        )
        return CTDAEvaluationResult(verdict, artifact)


def generate_lean_replay_source(
    request: CTDAWireRequest,
    expected: WireStaticVerdict | WireMonitorVerdict,
) -> str:
    payload = request.payload
    if request.stage is WireStage.SEMANTIC:
        type_name = "SemanticPayload"
        check = "checkSemantic"
        fields = _semantic_lean_fields(payload)
        expected_term = _static_result_term(expected)
    elif request.stage is WireStage.PREFIX_PRE:
        type_name = "PrefixPrePayload"
        check = "checkPrefixPre"
        fields = _prefix_lean_fields(payload)
        expected_term = _static_result_term(expected)
    elif request.stage is WireStage.OBSERVED_PREFIX:
        type_name = "ObservedPrefixPayload"
        check = "checkObservedPrefix"
        fields = _observed_lean_fields(payload)
        expected_term = _static_result_term(expected)
    else:
        type_name = "MonitorPayload"
        check = "checkMonitor"
        fields = _monitor_lean_fields(payload)
        expected_term = _monitor_result_term(expected)
    assignments = "\n".join(f"    {name} := {value}" for name, value in fields)
    return (
        "import ProofAlign.CTDAWire\n\n"
        "open ProofAlign.WireV1\n\n"
        f"def replayRequest : {type_name} :=\n"
        "  {\n"
        f"{assignments}\n"
        "  }\n\n"
        f"example : {check} replayRequest = {expected_term} := by decide\n"
    )


def _semantic_lean_fields(payload: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("missionDigest", _lean_string(payload["mission_digest"])),
        ("contractSpecDigest", _lean_string(payload["contract_spec_digest"])),
        ("contractDigest", _lean_string(payload["contract_digest"])),
        ("activePhase", _lean_string(payload["active_phase"])),
        ("contractPhase", _lean_string(payload["contract_phase"])),
        ("enabledObligationIds", _lean_string_list(payload["enabled_obligation_ids"])),
        ("contractObligationIds", _lean_string_list(payload["contract_obligation_ids"])),
        ("contractTarget", _lean_optional_string(payload["contract_target"])),
        ("obligationTarget", _lean_optional_string(payload["obligation_target"])),
        ("contractPart", _lean_optional_string(payload["contract_part"])),
        ("obligationPart", _lean_optional_string(payload["obligation_part"])),
        ("contractRegion", _lean_optional_string(payload["contract_region"])),
        ("obligationRegion", _lean_optional_string(payload["obligation_region"])),
        ("missionIntegrity", _lean_bool(payload["mission_integrity"])),
        ("contractIntegrity", _lean_bool(payload["contract_integrity"])),
        ("issuedAtNs", str(payload["issued_at_ns"])),
        ("deadlineNs", str(payload["deadline_ns"])),
        ("nowNs", str(payload["now_ns"])),
        ("guarantee", _lean_formula(payload["guarantee"])),
    ]


def _prefix_lean_fields(payload: dict[str, Any]) -> list[tuple[str, str]]:
    mapping = [
        ("semanticRequestId", "semantic_request_id", "text"),
        ("semanticVerdict", "semantic_verdict", "static"),
        ("missionDigest", "mission_digest", "text"),
        ("contractSpecDigest", "contract_spec_digest", "text"),
        ("contractDigest", "contract_digest", "text"),
        ("binderVerdict", "binder_verdict", "static"),
        ("stateDigest", "state_digest", "text"),
        ("authorizationStateDigest", "authorization_state_digest", "text"),
        ("monitorDigest", "monitor_digest", "text"),
        ("authorizationMonitorDigest", "authorization_monitor_digest", "text"),
        ("episodeNonce", "episode_nonce", "text"),
        ("authorizationNonce", "authorization_nonce", "text"),
        ("proposalIndex", "proposal_index", "nat"),
        ("authorizationProposalIndex", "authorization_proposal_index", "nat"),
        ("monitorLastProposalIndex", "monitor_last_proposal_index", "int"),
        ("proposalDigest", "proposal_digest", "text"),
        ("authorizationProposalDigest", "authorization_proposal_digest", "text"),
        ("commandDigest", "command_digest", "text"),
        ("authorizationCommandDigest", "authorization_command_digest", "text"),
        ("timeBaseDigest", "time_base_digest", "text"),
        ("authorizationTimeBaseDigest", "authorization_time_base_digest", "text"),
        ("nowNs", "now_ns", "nat"),
        ("issuedAtNs", "issued_at_ns", "nat"),
        ("validUntilNs", "valid_until_ns", "nat"),
        ("durationNs", "duration_ns", "nat"),
    ]
    return [(lean, _lean_scalar(payload[key], kind)) for lean, key, kind in mapping]


def _observed_lean_fields(payload: dict[str, Any]) -> list[tuple[str, str]]:
    mapping = [
        ("prefixRequestId", "prefix_request_id", "text"),
        ("prefixVerdict", "prefix_verdict", "static"),
        ("plantVerdict", "plant_verdict", "static"),
        ("authorizationDigest", "authorization_digest", "text"),
        ("receiptAuthorizationDigest", "receipt_authorization_digest", "text"),
        ("episodeNonce", "episode_nonce", "text"),
        ("receiptEpisodeNonce", "receipt_episode_nonce", "text"),
        ("authorizedCommandDigest", "authorized_command_digest", "text"),
        ("dispatchedCommandDigest", "dispatched_command_digest", "text"),
        ("receiptCommandDigest", "receipt_command_digest", "text"),
        ("missionTimeBaseDigest", "mission_time_base_digest", "text"),
        ("plantTimeBaseDigest", "plant_time_base_digest", "text"),
        ("dispatchNs", "dispatch_ns", "nat"),
        ("observedNs", "observed_ns", "nat"),
        ("receiptDigest", "receipt_digest", "text"),
        ("plantTraceDigest", "plant_trace_digest", "text"),
        ("eventTraceDigest", "event_trace_digest", "text"),
    ]
    return [(lean, _lean_scalar(payload[key], kind)) for lean, key, kind in mapping]


def _monitor_lean_fields(payload: dict[str, Any]) -> list[tuple[str, str]]:
    mapping = [
        ("observedRequestId", "observed_request_id", "text"),
        ("observedVerdict", "observed_verdict", "static"),
        ("missionDigest", "mission_digest", "text"),
        ("contractSpecDigest", "contract_spec_digest", "text"),
        ("episodeNonce", "episode_nonce", "text"),
        ("monitorEpisodeNonce", "monitor_episode_nonce", "text"),
        ("contractDigest", "contract_digest", "text"),
        ("monitorContractDigest", "monitor_contract_digest", "text"),
        ("activePhase", "active_phase", "text"),
        ("monitorPhase", "monitor_phase", "text"),
        ("previousMonitorDigest", "previous_monitor_digest", "text"),
        ("recordMonitorBeforeDigest", "record_monitor_before_digest", "text"),
        ("previousLastTimestampNs", "previous_last_timestamp_ns", "int"),
    ]
    fields = [(lean, _lean_scalar(payload[key], kind)) for lean, key, kind in mapping]
    fields.extend(
        [
            ("eventTimestampsNs", _lean_nat_list(payload["event_timestamps_ns"])),
            ("previousObservedAtoms", _lean_string_list(payload["previous_observed_atoms"])),
            ("currentObservedAtoms", _lean_string_list(payload["current_observed_atoms"])),
            ("guarantee", _lean_formula(payload["guarantee"])),
            ("invariant", _lean_formula(payload["invariant"])),
            ("expectedPhase", _lean_string(payload["expected_phase"])),
            ("terminalPhaseEvent", _lean_bool(payload["terminal_phase_event"])),
            ("completionWitness", _lean_bool(payload["completion_witness"])),
            ("postEvidence", _lean_bool(payload["post_evidence"])),
            ("nowNs", str(payload["now_ns"])),
            ("deadlineNs", str(payload["deadline_ns"])),
            ("nextProposalIndex", str(payload["next_proposal_index"])),
            ("recordProposalIndex", str(payload["record_proposal_index"])),
        ]
    )
    return fields


def _lean_formula(value: dict[str, Any]) -> str:
    tag = value["tag"]
    if tag == "atom":
        return f"Formula.atom {_lean_string(value['name'])} {_lean_bool(value['expected'])}"
    if tag in {"all", "any"}:
        items = ", ".join(_lean_formula(item) for item in value["items"])
        return f"Formula.{tag} [{items}]"
    if tag == "not":
        return f"Formula.not ({_lean_formula(value['item'])})"
    return f"Formula.eventually ({_lean_formula(value['item'])}) {value['deadline_ns']}"


def _lean_string(value: str) -> str:
    # Character constructors keep arbitrary UTF-8 and control characters out of
    # Lean source syntax, preventing quote/backslash/newline injection.
    return "(String.mk [" + ", ".join(f"Char.ofNat {ord(char)}" for char in value) + "])"


def _lean_optional_string(value: str | None) -> str:
    return "none" if value is None else f"some ({_lean_string(value)})"


def _lean_string_list(values: list[str]) -> str:
    return "[" + ", ".join(_lean_string(value) for value in values) + "]"


def _lean_nat_list(values: list[int]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def _lean_bool(value: bool) -> str:
    return "true" if value else "false"


def _lean_scalar(value: Any, kind: str) -> str:
    if kind == "text":
        return _lean_string(value)
    if kind == "static":
        return _static_result_term(WireStaticVerdict(value))
    return str(value) if value >= 0 else f"({value})"


def _static_result_term(value: WireStaticVerdict | WireMonitorVerdict) -> str:
    if not isinstance(value, WireStaticVerdict):
        raise TypeError("static Lean replay received a monitor verdict")
    return f"StaticResult.{value.value}"


def _monitor_result_term(value: WireStaticVerdict | WireMonitorVerdict) -> str:
    if not isinstance(value, WireMonitorVerdict):
        raise TypeError("monitor Lean replay received a static verdict")
    names = {"safe_pending": "safePending"}
    return f"MonitorResult.{names.get(value.value, value.value)}"


def _decode_for_evaluator(
    request: CTDAWireRequest | bytes,
    checker_version_digest: str,
) -> CTDAWireRequest:
    decoded = decode_wire_request(request.canonical_bytes() if isinstance(request, CTDAWireRequest) else request)
    if decoded.checker_version_digest != checker_version_digest:
        raise WireValidationError("request checker_version_digest does not match the consumer")
    return decoded


def _cache_key(
    request: CTDAWireRequest,
    mode: CTDAEvaluatorMode,
    checker_source_digest: str,
    checker_build_digest: str,
) -> str:
    return sha256(
        canonical_wire_bytes(
            {
                "mode": mode.value,
                "schema_version": SCHEMA_VERSION,
                "request": request.to_dict(),
                "checker_source_digest": checker_source_digest,
                "checker_build_digest": checker_build_digest,
            }
        )
    ).hexdigest()


def _digest_files(paths: tuple[Path, ...]) -> str:
    digest = sha256()
    for path in paths:
        digest.update(str(path.name).encode("utf-8"))
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
    "CTDAEvaluationArtifact",
    "CTDAEvaluationResult",
    "CTDAEvaluator",
    "CTDAEvaluatorMode",
    "LeanKernelEvaluator",
    "PythonReferenceEvaluator",
    "ShadowEvaluator",
    "generate_lean_replay_source",
]
