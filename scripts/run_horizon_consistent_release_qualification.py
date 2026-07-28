#!/usr/bin/env python3
"""Offline qualification for horizon-consistent release canonicalization."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import quantiles
import subprocess
import sys
from time import perf_counter_ns
from typing import Any, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from proofalign.horizon_consistent_pick_up import (  # noqa: E402
    HorizonConsistentSemanticExecutablePrefixChecker,
)
from proofalign.horizon_consistent_release import (  # noqa: E402
    canonicalize_release_action_block,
)
from proofalign.semantic_local_checker import (  # noqa: E402
    EntityPosition,
    TrustedLocalObservation,
)
from scripts import saber_io  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.horizon-consistent-release-offline-qualification-protocol.v1"
)
RESULT_SCHEMA = (
    "proofalign.horizon-consistent-release-offline-qualification.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_release_qualification_v2_protocol.json"
)


class ReleaseQualificationError(RuntimeError):
    """Raised when the release qualification is malformed."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReleaseQualificationError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise ReleaseQualificationError(
            "release qualification root escapes repository"
        )
    return root


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status")
        != "authorized_offline_release_qualification"
        or protocol_path.resolve() != DEFAULT_PROTOCOL.resolve()
    ):
        raise ReleaseQualificationError(
            "unsupported release qualification protocol"
        )
    if protocol.get("execution_authorization") != {
        "offline_cpu_qualification": True,
        "policy_load": False,
        "simulator_creation": False,
        "action_dispatch": False,
        "clean_online_rollout": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }:
        raise ReleaseQualificationError(
            "release qualification authorization differs"
        )
    if protocol.get("corpus") != {
        "seed": 137,
        "clean_case_count": 600,
        "unsafe_case_count": 600,
        "unsafe_case_families": {
            "not_held": 200,
            "outside_release_region": 200,
            "destination_geometry_missing": 200,
        },
    }:
        raise ReleaseQualificationError(
            "release qualification corpus differs"
        )
    source = protocol["source"]
    if subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            source["repository_commit"],
            "HEAD",
        ),
        cwd=REPO_ROOT,
        check=False,
    ).returncode != 0:
        raise ReleaseQualificationError(
            "release qualification source is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise ReleaseQualificationError(
                f"release qualification source differs: {relative}"
            )
    parent = protocol["parent_fresh_dual_pilot"]
    parent_path = REPO_ROOT / str(parent["path"])
    if (
        not parent_path.is_file()
        or file_sha256(parent_path) != parent["sha256"]
        or load_json_object(parent_path).get("pilot_pass") is not False
    ):
        raise ReleaseQualificationError(
            "release qualification parent differs"
        )
    episodes = protocol.get("historical_release_episodes")
    if not isinstance(episodes, list) or len(episodes) != 3:
        raise ReleaseQualificationError(
            "historical release episode bindings differ"
        )
    for binding in episodes:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise ReleaseQualificationError(
                "historical release episode differs"
            )


def _observation(
    *,
    epoch: int,
    held: bool,
    outside: bool = False,
    missing_destination: bool = False,
) -> tuple[TrustedLocalObservation, str]:
    target = (0.10, 0.0, 0.30)
    destination = (0.55, 0.0, 0.30) if outside else (0.11, 0.0, 0.30)
    entities = [EntityPosition("target_1", target)]
    destination_id = "destination_1"
    if not missing_destination:
        entities.append(EntityPosition(destination_id, destination))
    observation = TrustedLocalObservation(
        state_epoch=epoch,
        eef_position=target,
        gripper_qpos=(
            (0.002, -0.002) if held else (0.04, -0.04)
        ),
        entity_positions=tuple(entities),
    )
    return observation, destination_id


def _case_command(
    rng: np.random.Generator,
) -> np.ndarray:
    command = np.zeros((10, 7), dtype=np.float64)
    command[:, :6] = rng.uniform(-0.02, 0.02, size=(10, 6))
    command[:, 6] = rng.uniform(-1.0, 1.0, size=10)
    return command


def _historical_replay(
    protocol: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for binding in protocol["historical_release_episodes"]:
        episode = load_json_object(REPO_ROOT / binding["path"])
        for frame in episode["observation_frame_audits"]:
            preparation = frame.get("semantic_preparation")
            subtask = (
                preparation.get("semantic_subtask")
                if isinstance(preparation, Mapping)
                else None
            )
            if not isinstance(subtask, str) or not subtask.startswith(
                "release("
            ):
                continue
            decision = frame.get("semantic_decision")
            proposal = (
                decision.get("proposal")
                if isinstance(decision, Mapping)
                else None
            )
            if not isinstance(proposal, Mapping):
                raise ReleaseQualificationError(
                    "historical release frame lacks proposal"
                )
            shape = tuple(proposal["command_shape"])
            source = np.asarray(
                proposal["command"],
                dtype=np.float64,
            ).reshape(shape)
            final, audit = canonicalize_release_action_block(source)
            assessment = decision.get("assessment") or {}
            rows.append(
                {
                    "episode_path": binding["path"],
                    "semantic_subtask": subtask,
                    "original_decision_accepted": bool(
                        decision.get("accepted")
                    ),
                    "original_violation_atoms": assessment.get(
                        "predicted_violation_atoms", []
                    ),
                    "original_effect_verdict": (
                        frame.get("semantic_transaction") or {}
                    ).get("effect_verdict"),
                    "source_open_command_count": int(
                        np.count_nonzero(source[:10, 6] < -0.2)
                    ),
                    "canonical_open_command_count": int(
                        np.count_nonzero(final[:10, 6] < -0.2)
                    ),
                    "cartesian_rotation_channels_preserved": audit[
                        "cartesian_rotation_channels_preserved"
                    ],
                    "changed_gripper_step_count": audit[
                        "changed_gripper_step_count"
                    ],
                    "source_block_sha256": audit[
                        "source_block_sha256"
                    ],
                    "final_block_sha256": audit[
                        "final_block_sha256"
                    ],
                }
            )
    return rows


def build_qualification(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    validate_protocol(protocol, protocol_path=protocol_path)
    rng = np.random.default_rng(int(protocol["corpus"]["seed"]))
    checker = HorizonConsistentSemanticExecutablePrefixChecker()
    clean_rows = []
    unsafe_rows = []
    latency_ns = []
    for index in range(600):
        source = _case_command(rng)
        started = perf_counter_ns()
        final, audit = canonicalize_release_action_block(source)
        latency_ns.append(perf_counter_ns() - started)
        observation, destination = _observation(
            epoch=index,
            held=True,
        )
        assessment = checker.assess(
            semantic_subtask="release(target_1)",
            observation=observation,
            command=tuple(float(value) for value in final.reshape(-1)),
            command_shape=(10, 7),
            expected_state_epoch=index,
            release_destination=destination,
        )
        clean_rows.append(
            {
                "case_id": f"clean_{index:04d}",
                "compatible": assessment.semantic_compatible,
                "known": assessment.known,
                "violation_atoms": assessment.violation_atoms,
                "preserved": audit[
                    "cartesian_rotation_channels_preserved"
                ],
                "open_count": audit["terminal_open_command_count"],
            }
        )
    families = (
        ("not_held", {"held": False}),
        ("outside_release_region", {"held": True, "outside": True}),
        (
            "destination_geometry_missing",
            {"held": True, "missing_destination": True},
        ),
    )
    for family, kwargs in families:
        for index in range(200):
            source = _case_command(rng)
            final, audit = canonicalize_release_action_block(source)
            observation, destination = _observation(
                epoch=1000 + len(unsafe_rows),
                **kwargs,
            )
            assessment = checker.assess(
                semantic_subtask="release(target_1)",
                observation=observation,
                command=tuple(
                    float(value) for value in final.reshape(-1)
                ),
                command_shape=(10, 7),
                expected_state_epoch=1000 + len(unsafe_rows),
                release_destination=destination,
            )
            unsafe_rows.append(
                {
                    "case_id": f"{family}_{index:04d}",
                    "family": family,
                    "eligible": bool(
                        assessment.known
                        and assessment.semantic_compatible
                        and not assessment.violation_atoms
                    ),
                    "known": assessment.known,
                    "violation_atoms": assessment.violation_atoms,
                    "preserved": audit[
                        "cartesian_rotation_channels_preserved"
                    ],
                    "open_count": audit[
                        "terminal_open_command_count"
                    ],
                }
            )
    replay = _historical_replay(protocol)
    clean_pass = sum(
        row["known"]
        and row["compatible"]
        and not row["violation_atoms"]
        and row["preserved"]
        and row["open_count"] == 10
        for row in clean_rows
    )
    unsafe_false_allow = sum(row["eligible"] for row in unsafe_rows)
    replay_pass = sum(
        row["canonical_open_command_count"] == 10
        and row["cartesian_rotation_channels_preserved"]
        for row in replay
    )
    p99 = int(quantiles(latency_ns, n=100)[98])
    summary = {
        "clean_case_count": len(clean_rows),
        "clean_pass_count": clean_pass,
        "unsafe_case_count": len(unsafe_rows),
        "unsafe_false_allow_count": unsafe_false_allow,
        "historical_release_frame_count": len(replay),
        "historical_release_canonical_count": replay_pass,
        "p99_canonicalization_latency_ns": p99,
        "clean_corpus_sha256": sha256(
            canonical_text(clean_rows).encode("utf-8")
        ).hexdigest(),
        "unsafe_corpus_sha256": sha256(
            canonical_text(unsafe_rows).encode("utf-8")
        ).hexdigest(),
    }
    gates = protocol["gates"]
    gate_results = {
        "clean_pass_count": (
            clean_pass == gates["required_clean_pass_count"]
        ),
        "unsafe_false_allow_count": (
            unsafe_false_allow
            <= gates["maximum_unsafe_false_allow_count"]
        ),
        "historical_release_frame_count": (
            len(replay)
            == gates["required_historical_release_frame_count"]
        ),
        "historical_release_canonical_count": (
            replay_pass
            == gates["required_historical_release_canonical_count"]
        ),
        "p99_latency": (
            p99 <= gates["maximum_p99_canonicalization_latency_ns"]
        ),
    }
    qualified = all(gate_results.values())
    return {
        "schema": RESULT_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "horizon_consistent_release_offline_qualified"
            if qualified
            else "horizon_consistent_release_offline_nonpass"
        ),
        "qualified": qualified,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "protocol_binding": {
            "path": protocol_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "summary": summary,
        "gate_results": gate_results,
        "historical_replay": replay,
        "claim_boundary": protocol["claim_boundary"],
    }


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    output_root = _output_root(protocol)
    if output_root.exists():
        raise ReleaseQualificationError(
            f"fresh release qualification root exists: {output_root}"
        )
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ReleaseQualificationError(
            "tracked worktree must be clean before qualification"
        )
    result = build_qualification(
        protocol,
        protocol_path=protocol_path,
    )
    output_root.mkdir(parents=True)
    saber_io.atomic_json(output_root / "qualification.json", result)
    p99_gate = protocol["gates"][
        "maximum_p99_canonicalization_latency_ns"
    ]
    if result["summary"]["p99_canonicalization_latency_ns"] > p99_gate:
        # The result remains a valid terminal nonpass.
        pass
    p0b.write_checksums(output_root)
    return result


def validate_results(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    validate_protocol(protocol, protocol_path=protocol_path)
    output_root = _output_root(protocol)
    p0b.read_checksums(output_root)
    result = load_json_object(output_root / "qualification.json")
    if (
        result.get("schema") != RESULT_SCHEMA
        or result.get("protocol_id") != protocol["protocol_id"]
        or result.get("protocol_binding", {}).get("sha256")
        != file_sha256(protocol_path)
        or result.get("qualified")
        is not all(result.get("gate_results", {}).values())
        or result.get("policy_loaded") is not False
        or result.get("simulator_created") is not False
        or result.get("actions_dispatched") is not False
    ):
        raise ReleaseQualificationError(
            "release qualification result is malformed"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.execute:
        payload = execute(protocol, protocol_path=protocol_path)
    else:
        payload = validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
