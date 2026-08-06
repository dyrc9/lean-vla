#!/usr/bin/env python3
"""Run or validate the v11 attacked study paired to clean scale45."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.attack_records import (  # noqa: E402
    attack_record_digest,
)
from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ARM_ORDER,
    canonical_text,
)
from scripts import run_joint_limit_containment_v11_clean_pilot as clean  # noqa: E402
from scripts import run_l2_joint_limit_containment_v11 as online  # noqa: E402
from scripts import run_physical_sufficiency_attacked_pilot as inherited  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.joint-limit-containment-v11-attacked-scale45-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.joint-limit-containment-v11-attacked-scale45-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v11_joint_limit_containment_attacked_scale45"
)
STAGE = "joint_limit_containment_v11_attacked_scale45"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_attacked_"
    "scale45_protocol.json"
)


class JointLimitContainmentAttackedScale45Error(RuntimeError):
    """Raised when the paired attacked scale45 study leaves scope."""


def derive_attack_transplants(
    clean_protocol: Mapping[str, Any],
    source_bundle: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Transplant one frozen task-only prompt to every held-out init."""

    source_records = source_bundle.get("records")
    if not isinstance(source_records, list):
        raise JointLimitContainmentAttackedScale45Error(
            "M2 attack-record bundle has no records"
        )
    by_task: dict[tuple[str, int], Mapping[str, Any]] = {}
    for source in source_records:
        if not isinstance(source, Mapping):
            raise JointLimitContainmentAttackedScale45Error(
                "M2 attack record is not an object"
            )
        key = (str(source["suite"]), int(source["task_id"]))
        if key in by_task:
            raise JointLimitContainmentAttackedScale45Error(
                f"M2 attack task is duplicated: {key}"
            )
        by_task[key] = source

    transplants = []
    for workload in clean_protocol["workloads"]:
        key = (str(workload["suite"]), int(workload["task_id"]))
        source = by_task.get(key)
        if source is None:
            raise JointLimitContainmentAttackedScale45Error(
                f"M2 attack task is absent: {key}"
            )
        trusted = str(workload["trusted_instruction"])
        if source.get("original_instruction") != trusted:
            raise JointLimitContainmentAttackedScale45Error(
                f"M2 trusted prompt differs: {key}"
            )
        perturbed = source.get("perturbed_instruction")
        if not isinstance(perturbed, str) or not perturbed:
            raise JointLimitContainmentAttackedScale45Error(
                f"M2 perturbed prompt is absent: {key}"
            )
        source_record = dict(source)
        target_init = int(workload["init_state_id"])
        transplants.append(
            {
                "schema_version": (
                    "proofalign.saber-task-prompt-transplant.v1"
                ),
                "suite": key[0],
                "task_id": key[1],
                "init_state_id": target_init,
                "original_instruction": trusted,
                "perturbed_instruction": perturbed,
                "objective": source.get("objective"),
                "tools_used": list(source.get("tools_used") or ()),
                "source": source.get("source"),
                "edit_distance_chars": source.get(
                    "edit_distance_chars"
                ),
                "source_record": {
                    "schema_version": source.get("schema_version"),
                    "init_state_id": int(source["init_state_id"]),
                    "record_sha256": attack_record_digest(
                        source_record
                    ),
                    "generation": source.get("generation"),
                },
                "transplant": {
                    "scope": "task_text_only",
                    "prompt_text_changed": False,
                    "original_instruction_exact_match": True,
                    "source_init_state_id": int(
                        source["init_state_id"]
                    ),
                    "target_init_state_id": target_init,
                    "target_base_pair_id": str(
                        workload["base_pair_id"]
                    ),
                },
            }
        )
    if len(transplants) != len(clean_protocol["workloads"]):
        raise JointLimitContainmentAttackedScale45Error(
            "attack transplant population differs from clean workload"
        )
    return transplants


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    """Validate scale45 without the predecessor's fresh15 constants."""

    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("stage") != STAGE
    ):
        raise JointLimitContainmentAttackedScale45Error(
            "unsupported or unauthorized attacked scale45 protocol"
        )
    if protocol_path.resolve() != DEFAULT_PROTOCOL.resolve():
        raise JointLimitContainmentAttackedScale45Error(
            "non-default attacked scale45 protocol refused"
        )
    if protocol.get("execution_authorization") != {
        "attacked_exploratory_pilot": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_rollout": False,
        "confirmatory_claim": False,
    }:
        raise JointLimitContainmentAttackedScale45Error(
            "attacked scale45 authorization differs"
        )
    schedule = protocol.get("schedule")
    expected_count = int(
        protocol["gates"]["expected_episode_count"]
    )
    if (
        not isinstance(schedule, list)
        or len(schedule) != expected_count
        or protocol.get("schedule_sha256")
        != inherited.schedule_sha256(schedule)
    ):
        raise JointLimitContainmentAttackedScale45Error(
            "attacked scale45 schedule differs"
        )
    specs = inherited.build_specs(protocol)
    pair_count = int(protocol["design"]["pair_count"])
    if Counter(spec.arm for spec in specs) != {
        arm: pair_count for arm in ARM_ORDER
    }:
        raise JointLimitContainmentAttackedScale45Error(
            "attacked scale45 arm balance differs"
        )
    clean_path = REPO_ROOT / str(
        protocol["paired_clean_binding"]["protocol_path"]
    )
    clean_protocol = load_json_object(clean_path)
    source_path = REPO_ROOT / str(
        protocol["attack_source"]["path"]
    )
    if (
        not source_path.is_file()
        or file_sha256(source_path)
        != protocol["attack_source"]["sha256"]
    ):
        raise JointLimitContainmentAttackedScale45Error(
            "M2 attack-record source binding differs"
        )
    expected = derive_attack_transplants(
        clean_protocol,
        load_json_object(source_path),
    )
    if protocol.get("attack_records") != expected:
        raise JointLimitContainmentAttackedScale45Error(
            "task-prompt transplants differ from frozen M2 records"
        )
    index = inherited.attack_record_index(protocol)
    if any(
        (
            spec.unit.suite,
            spec.unit.task_id,
            spec.unit.init_state_id,
        )
        not in index
        for spec in specs
    ):
        raise JointLimitContainmentAttackedScale45Error(
            "an attacked episode lacks an exact attack record"
        )
    source = protocol.get("source")
    if not isinstance(source, Mapping):
        raise JointLimitContainmentAttackedScale45Error(
            "attacked scale45 source binding is absent"
        )
    if subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            str(source["repository_commit"]),
            "HEAD",
        ),
        cwd=REPO_ROOT,
        check=False,
    ).returncode != 0:
        raise JointLimitContainmentAttackedScale45Error(
            "attacked scale45 source is not an ancestor"
        )
    for relative, expected_sha in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if (
            not path.is_file()
            or file_sha256(path) != expected_sha
        ):
            raise JointLimitContainmentAttackedScale45Error(
                f"attacked scale45 source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise JointLimitContainmentAttackedScale45Error(
                f"attacked scale45 binding differs: {path}"
            )
        if "classification" in binding:
            payload = load_json_object(path)
            if payload.get("classification") != binding[
                "classification"
            ]:
                raise JointLimitContainmentAttackedScale45Error(
                    f"attacked scale45 classification differs: {path}"
                )


@contextmanager
def _patched_inherited() -> Iterator[None]:
    base = inherited.base
    originals = (
        inherited.PROTOCOL_SCHEMA,
        inherited.EVIDENCE_SCHEMA,
        inherited.AUTHORIZED_STATUS,
        inherited.STAGE,
        inherited.DEFAULT_PROTOCOL,
        inherited.online,
        inherited.validate_protocol,
        inherited.derive_attack_transplants,
        base.PROTOCOL_SCHEMA,
        base.EVIDENCE_SCHEMA,
        base.EXPECTED_RUNNER,
        base.AUTHORIZED_STATUS,
        base.DEFAULT_PROTOCOL,
        base.online,
        base._v10_metrics,
    )
    inherited.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    inherited.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    inherited.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    inherited.STAGE = STAGE
    inherited.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    inherited.online = online
    inherited.validate_protocol = validate_protocol
    inherited.derive_attack_transplants = derive_attack_transplants
    base.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    base.EVIDENCE_SCHEMA = EVIDENCE_SCHEMA
    base.EXPECTED_RUNNER = online.RUNNER_VARIANT
    base.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    base.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    base.online = online
    base._v10_metrics = clean._v11_metrics
    try:
        yield
    finally:
        (
            inherited.PROTOCOL_SCHEMA,
            inherited.EVIDENCE_SCHEMA,
            inherited.AUTHORIZED_STATUS,
            inherited.STAGE,
            inherited.DEFAULT_PROTOCOL,
            inherited.online,
            inherited.validate_protocol,
            inherited.derive_attack_transplants,
            base.PROTOCOL_SCHEMA,
            base.EVIDENCE_SCHEMA,
            base.EXPECTED_RUNNER,
            base.AUTHORIZED_STATUS,
            base.DEFAULT_PROTOCOL,
            base.online,
            base._v10_metrics,
        ) = originals


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    with _patched_inherited():
        return inherited.validate_results(
            protocol,
            protocol_path=protocol_path,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--policy-gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    elif args.execute:
        if args.policy_gpu is None or args.egl_gpu is None:
            parser.error(
                "--execute requires --policy-gpu and --egl-gpu"
            )
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    else:
        payload = validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
