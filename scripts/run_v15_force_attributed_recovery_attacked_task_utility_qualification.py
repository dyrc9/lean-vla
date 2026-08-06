#!/usr/bin/env python3
"""Run paired attacked task-utility qualification for v15.3 recovery."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import json
from pathlib import Path
import re
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
from proofalign.digests import digest_text  # noqa: E402
from scripts import run_contact_phase_pick_up_clean_pilot as generic  # noqa: E402
from scripts import (  # noqa: E402
    run_joint_limit_containment_v11_attacked_scale45 as transplant,
)
from scripts import run_physical_sufficiency_attacked_pilot as attack_base  # noqa: E402
from scripts import run_predictive_virtual_brake_v13_clean as runtime_base  # noqa: E402
from scripts import run_saber_threat_validation_r5 as checksums  # noqa: E402
from scripts import (  # noqa: E402
    run_v15_force_attributed_recovery_task_utility_qualification as clean,
)
from scripts import saber_io  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-attacked-task-utility-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-attacked-task-utility-qualification-evidence.v1"
)
BASE_EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-attacked-task-utility-base-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_3_force_attributed_recovery_attacked_"
    "task_utility_qualification"
)
STAGE = (
    "predictive_virtual_brake_v15_3_force_attributed_recovery_"
    "attacked_task_utility_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_attacked_task_utility_qualification_protocol.json"
)
ATTACKED_EVIDENCE_NAME = "attacked_qualification_evidence.json"
_BASE_QUALIFICATION_ENRICH = clean._qualification_enrich
_TIME_PATTERN = re.compile(
    r"Time\s*=\s*([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)"
)


class V15AttackedTaskUtilityError(RuntimeError):
    """Raised when paired v15.3 attacked evidence differs."""


class _WarningAudit:
    """Capture checksum-bound MuJoCo warnings by episode and sim time."""

    def __init__(self) -> None:
        self.episode_id: str | None = None
        self.counts: Counter[str] = Counter()
        self.by_episode: dict[str, Counter[str]] = {}
        self.samples: dict[str, str] = {}

    def __call__(self, message: str) -> None:
        text = str(message)
        if "Too many contacts" in text:
            match = _TIME_PATTERN.search(text)
            time_value = float(match.group(1)) if match else None
            category = (
                "contact_capacity_time_zero"
                if time_value == 0.0
                else "contact_capacity_nonzero_or_unknown_time"
            )
        else:
            category = "other_mujoco_warning"
        self.counts[category] += 1
        episode = self.episode_id or "outside_episode"
        self.by_episode.setdefault(episode, Counter())[category] += 1
        self.samples.setdefault(category, text[:500])

    def report(self) -> dict[str, Any]:
        return {
            "total_warning_count": sum(self.counts.values()),
            "counts": dict(sorted(self.counts.items())),
            "by_episode": {
                episode: dict(sorted(values.items()))
                for episode, values in sorted(self.by_episode.items())
            },
            "sample_messages": dict(sorted(self.samples.items())),
            "contact_capacity_warning_count": (
                self.counts["contact_capacity_time_zero"]
                + self.counts[
                    "contact_capacity_nonzero_or_unknown_time"
                ]
            ),
            "contact_capacity_time_zero_count": self.counts[
                "contact_capacity_time_zero"
            ],
            "contact_capacity_nonzero_or_unknown_time_count": self.counts[
                "contact_capacity_nonzero_or_unknown_time"
            ],
            "time_zero_is_diagnostic_not_active_gate": True,
        }


def _git_ancestor(commit: str) -> bool:
    return (
        subprocess.run(
            ("git", "merge-base", "--is-ancestor", commit, "HEAD"),
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
        ).returncode
        == 0
    )


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("stage") != STAGE
    ):
        raise V15AttackedTaskUtilityError(
            "unsupported or unauthorized v15.3 attacked protocol"
        )
    if protocol_path.resolve() != DEFAULT_PROTOCOL.resolve():
        raise V15AttackedTaskUtilityError(
            "non-default v15.3 attacked protocol refused"
        )
    if protocol.get("execution_authorization") != {
        "attacked_exploratory_pilot": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_rollout": False,
        "confirmatory_claim": False,
    }:
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked authorization differs"
        )
    schedule = protocol.get("schedule")
    expected_count = int(protocol["gates"]["expected_episode_count"])
    if (
        not isinstance(schedule, list)
        or len(schedule) != expected_count
        or protocol.get("schedule_sha256")
        != attack_base.schedule_sha256(schedule)
    ):
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked schedule differs"
        )
    specs = attack_base.build_specs(protocol)
    pair_count = int(protocol["design"]["pair_count"])
    if Counter(spec.arm for spec in specs) != {
        arm: pair_count for arm in ARM_ORDER
    }:
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked arm balance differs"
        )
    clean_path = REPO_ROOT / str(
        protocol["paired_clean_binding"]["protocol_path"]
    )
    source_path = REPO_ROOT / str(protocol["attack_source"]["path"])
    if (
        not source_path.is_file()
        or file_sha256(source_path)
        != protocol["attack_source"]["sha256"]
    ):
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked record-source binding differs"
        )
    expected_records = transplant.derive_attack_transplants(
        load_json_object(clean_path),
        load_json_object(source_path),
    )
    if protocol.get("attack_records") != expected_records:
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked prompt transplants differ"
        )
    index = attack_base.attack_record_index(protocol)
    if any(
        (spec.unit.suite, spec.unit.task_id, spec.unit.init_state_id)
        not in index
        for spec in specs
    ):
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked episode lacks an exact attack record"
        )
    source = protocol.get("source")
    if (
        not isinstance(source, Mapping)
        or not _git_ancestor(str(source["repository_commit"]))
    ):
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked source commit is unavailable"
        )
    for relative, expected_sha in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected_sha:
            raise V15AttackedTaskUtilityError(
                f"v15.3 attacked source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15AttackedTaskUtilityError(
                f"v15.3 attacked binding differs: {path}"
            )
        if "classification" in binding:
            payload = load_json_object(path)
            if payload.get("classification") != binding["classification"]:
                raise V15AttackedTaskUtilityError(
                    f"v15.3 attacked classification differs: {path}"
                )


def _attacked_base_enrich(
    protocol: Mapping[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    enriched = _BASE_QUALIFICATION_ENRICH(protocol, evidence)
    return {
        **enriched,
        "schema": BASE_EVIDENCE_SCHEMA,
        "condition": "instruction_attacked",
        "held_out_attack_outcomes": True,
        "clean_task_outcomes_observed_before_protocol_freeze": True,
        "attacked_task_outcomes_observed_before_protocol_freeze": False,
        "method_claim": (
            "paired pre-specified instruction-attack task utility for the "
            "stress-qualified v15.3 simulator recovery"
        ),
    }


@contextmanager
def _patched_attacked(
    protocol: Mapping[str, Any],
    warnings: _WarningAudit | None = None,
) -> Iterator[None]:
    online = clean.online
    originals = (
        clean.PROTOCOL_SCHEMA,
        clean.EVIDENCE_SCHEMA,
        clean.AUTHORIZED_STATUS,
        clean.DEFAULT_PROTOCOL,
        clean._qualification_enrich,
        generic.validate_protocol,
        generic.build_specs,
        online.run_episode,
    )
    records = attack_base.attack_record_index(protocol)

    def validate_normalized(
        normalized: Mapping[str, Any],
        *,
        protocol_path: Path,
    ) -> None:
        restored = dict(normalized)
        restored["status"] = AUTHORIZED_STATUS
        validate_protocol(restored, protocol_path=protocol_path)

    def run_attacked_episode(**kwargs: Any) -> dict[str, Any]:
        forwarded = dict(kwargs)
        forwarded["attack_records"] = records
        if warnings is not None:
            warnings.episode_id = Path(
                str(forwarded["output_dir"])
            ).name
        try:
            return originals[-1](**forwarded)
        finally:
            if warnings is not None:
                warnings.episode_id = None

    clean.PROTOCOL_SCHEMA = PROTOCOL_SCHEMA
    clean.EVIDENCE_SCHEMA = BASE_EVIDENCE_SCHEMA
    clean.AUTHORIZED_STATUS = AUTHORIZED_STATUS
    clean.DEFAULT_PROTOCOL = DEFAULT_PROTOCOL
    clean._qualification_enrich = _attacked_base_enrich
    generic.validate_protocol = validate_normalized
    generic.build_specs = attack_base.build_specs
    online.run_episode = run_attacked_episode
    try:
        yield
    finally:
        (
            clean.PROTOCOL_SCHEMA,
            clean.EVIDENCE_SCHEMA,
            clean.AUTHORIZED_STATUS,
            clean.DEFAULT_PROTOCOL,
            clean._qualification_enrich,
            generic.validate_protocol,
            generic.build_specs,
            online.run_episode,
        ) = originals


def _episode_map(
    evidence: Mapping[str, Any],
) -> dict[tuple[str, str], tuple[Mapping[str, Any], Mapping[str, Any]]]:
    by_id = {
        str(row["episode_id"]): row for row in evidence["per_episode"]
    }
    result = {}
    for artifact in evidence["episodes"]:
        row = by_id[str(artifact["episode_id"])]
        result[(str(row["base_pair_id"]), str(row["arm"]))] = (
            row,
            load_json_object(REPO_ROOT / str(artifact["path"])),
        )
    return result


def _attack_metrics(
    protocol: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bool], dict[str, Any]]:
    records = attack_base.attack_record_index(protocol)
    attacked = _episode_map(evidence)
    clean_evidence = load_json_object(
        REPO_ROOT
        / str(protocol["paired_clean_binding"]["evidence_path"])
    )
    clean_map = _episode_map(clean_evidence)
    metadata_mismatches = 0
    prompt_mismatches = 0
    comparison_count = 0
    changed_first_blocks = 0
    first_by_pair: dict[str, dict[str, str]] = {}
    paired_rows = []

    for spec in attack_base.build_specs(protocol):
        key = (spec.unit.base_pair_id, spec.arm)
        row, episode = attacked[key]
        clean_row, clean_episode = clean_map[key]
        record = records[
            (spec.unit.suite, spec.unit.task_id, spec.unit.init_state_id)
        ]
        metadata = episode["metadata"]
        expected_metadata = {
            "original_instruction": spec.unit.trusted_instruction,
            "perturbed_instruction": record["perturbed_instruction"],
            "attack_objective": "constraint_violation",
            "attack_record_digest": attack_record_digest(record),
            "observation_attack_type": "none",
            "execution_attack_family": "none",
        }
        metadata_mismatches += sum(
            metadata.get(name) != expected
            for name, expected in expected_metadata.items()
        )
        frames = episode["observation_frame_audits"]
        expected_prompt = digest_text(str(record["perturbed_instruction"]))
        prompt_mismatches += sum(
            frame.get("exact_policy_prompt_digest") != expected_prompt
            for frame in frames
        )
        attacked_first = str(frames[0]["policy_action_chunk_sha256"])
        clean_first = str(
            clean_episode["observation_frame_audits"][0][
                "policy_action_chunk_sha256"
            ]
        )
        first_by_pair.setdefault(spec.unit.base_pair_id, {})[
            spec.arm
        ] = attacked_first
        comparison_count += 1
        changed_first_blocks += int(attacked_first != clean_first)
        if (
            row["suite"] != clean_row["suite"]
            or row["base_pair_id"] != clean_row["base_pair_id"]
        ):
            raise V15AttackedTaskUtilityError(
                "paired clean/attacked workload differs"
            )
        paired_rows.append(
            {
                "base_pair_id": spec.unit.base_pair_id,
                "arm": spec.arm,
                "clean_task_success": bool(clean_row["task_success"]),
                "attacked_task_success": bool(row["task_success"]),
                "clean_unsafe": bool(
                    clean_row["unsafe_cost_or_collision"]
                ),
                "attacked_unsafe": bool(
                    row["unsafe_cost_or_collision"]
                ),
                "first_action_block_changed": (
                    attacked_first != clean_first
                ),
            }
        )
    paired_first = sum(
        len(values) == len(ARM_ORDER) and len(set(values.values())) == 1
        for values in first_by_pair.values()
    )
    config = protocol["attacked_data_gates"]
    metrics = {
        "attack_record_count": len(records),
        "attack_metadata_mismatch_count": metadata_mismatches,
        "attacked_prompt_digest_mismatch_count": prompt_mismatches,
        "paired_clean_episode_comparison_count": comparison_count,
        "attack_changed_first_action_block_count": changed_first_blocks,
        "attacked_paired_first_action_block_match_count": paired_first,
    }
    gates = {
        "attack_record_count": (
            len(records) == config["expected_attack_record_count"]
        ),
        "attack_metadata_matches": metadata_mismatches == 0,
        "attacked_prompt_digest_matches": prompt_mismatches == 0,
        "paired_clean_episode_comparisons": (
            comparison_count
            == config["expected_paired_clean_episode_comparison_count"]
        ),
        "attack_changes_first_action_blocks": (
            changed_first_blocks
            >= config["minimum_changed_first_action_block_count"]
        ),
        "attacked_first_action_blocks_match_within_workload": (
            paired_first
            == config[
                "expected_attacked_paired_first_action_block_match_count"
            ]
        ),
    }
    paired = {
        "rows": paired_rows,
        "clean_reference_by_arm": clean_evidence["by_arm"],
        "attacked_reference_by_arm": evidence["by_arm"],
        "same_pairs_init_states_environment_and_policy_seeds": True,
        "all_clean_pairs_retained_without_outcome_filtering": True,
    }
    return metrics, gates, paired


def _build_attacked_evidence(
    protocol: Mapping[str, Any],
    base: Mapping[str, Any],
    warning_report: Mapping[str, Any],
) -> dict[str, Any]:
    metrics, attack_gates, paired = _attack_metrics(protocol, base)
    warning_config = protocol["warning_gates"]
    warning_gates = {
        "active_contact_capacity_warning_free": (
            int(
                warning_report[
                    "contact_capacity_nonzero_or_unknown_time_count"
                ]
            )
            <= warning_config[
                "maximum_nonzero_or_unknown_time_contact_capacity_warning_count"
            ]
        ),
    }
    combined = {
        **base["gate_results"],
        **{f"attacked_{name}": value for name, value in attack_gates.items()},
        **warning_gates,
    }
    passed = bool(combined and all(combined.values()))
    return {
        **base,
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if passed
            else protocol["nonpass_classification"]
        ),
        "qualification_pass": passed,
        "attacked_task_utility_qualification_claim_authorized": passed,
        "confirmatory_claim_authorized": False,
        "arbitrary_attack_claim_authorized": False,
        "gate_results": combined,
        "aggregate": {**base["aggregate"], **metrics},
        "paired_clean_attacked_analysis": paired,
        "mujoco_warning_audit": dict(warning_report),
        "time_zero_contact_capacity_warnings_are_diagnostic": True,
        "method_claim": (
            "paired simulator evidence under the frozen SABER task-prompt "
            "constraint-violation attack for v15.3 recovery"
        ),
        "claim_boundary": protocol["claim_boundary"],
    }


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    with _patched_attacked(protocol):
        report = clean.preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=policy_gpu,
            egl_gpu=egl_gpu,
        )
    return {
        **report,
        "schema": (
            "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
            "recovery-attacked-task-utility-qualification-preflight.v1"
        ),
        "condition": "instruction_attacked",
        "paired_clean_task_outcomes_observed": True,
        "attacked_task_outcomes_observed_before_freeze": False,
        "all_clean_pairs_retained": True,
        "checksum_bound_mujoco_warning_audit": True,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    if (
        Path(sys.executable).resolve()
        != runtime_base.REQUIRED_INTERPRETER.resolve()
    ):
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked rollout requires external/openpi/.venv/bin/python"
        )
    try:
        import mujoco
    except ImportError as exc:
        raise V15AttackedTaskUtilityError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    warnings = _WarningAudit()
    previous = mujoco.get_mju_user_warning()
    mujoco.set_mju_user_warning(warnings)
    try:
        with _patched_attacked(protocol, warnings):
            base = clean.execute(
                protocol,
                protocol_path=protocol_path,
                policy_gpu=policy_gpu,
                egl_gpu=egl_gpu,
            )
    finally:
        mujoco.set_mju_user_warning(previous)
    enriched = _build_attacked_evidence(protocol, base, warnings.report())
    output_root = REPO_ROOT / str(protocol["fresh_output_root"])
    saber_io.atomic_json(output_root / ATTACKED_EVIDENCE_NAME, enriched)
    manifest_path = output_root / "run_manifest.json"
    manifest = load_json_object(manifest_path)
    manifest.update(
        {
            "attacked_qualification_classification": enriched[
                "classification"
            ],
            "attacked_qualification_evidence": ATTACKED_EVIDENCE_NAME,
            "mujoco_warning_audit_checksum_bound": True,
        }
    )
    saber_io.atomic_json(manifest_path, manifest)
    checksums.write_checksums(output_root)
    return enriched


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    validate_protocol(protocol, protocol_path=protocol_path)
    with _patched_attacked(protocol):
        base = clean.validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    output_root = REPO_ROOT / str(protocol["fresh_output_root"])
    retained = load_json_object(output_root / ATTACKED_EVIDENCE_NAME)
    rebuilt = _build_attacked_evidence(
        protocol,
        base,
        retained["mujoco_warning_audit"],
    )
    if json.loads(canonical_text(rebuilt)) != retained:
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked evidence differs from recomputation"
        )
    manifest = load_json_object(output_root / "run_manifest.json")
    if (
        manifest.get("status") != "complete"
        or manifest.get("attacked_qualification_classification")
        != retained["classification"]
        or manifest.get("attacked_qualification_evidence")
        != ATTACKED_EVIDENCE_NAME
    ):
        raise V15AttackedTaskUtilityError(
            "v15.3 attacked manifest differs"
        )
    return retained


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
            parser.error("--execute requires --policy-gpu and --egl-gpu")
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
