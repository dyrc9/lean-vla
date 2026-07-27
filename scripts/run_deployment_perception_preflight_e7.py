#!/usr/bin/env python3
"""Freeze and audit data readiness for deployment-perception qualification."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = Path(
    "/data0/ldx/datasets/modified_libero_rlds/"
    "libero_spatial_no_noops/1.0.0"
)
PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_deployment_perception_e7_protocol.json"
)
EVIDENCE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_deployment_perception_e7_preflight.json"
)
SOURCE_PATHS = (
    "scripts/run_deployment_perception_preflight_e7.py",
    "scripts/run_pi05_selector_qualification_e1.py",
    "src/proofalign/semantic_local_checker.py",
    "src/proofalign/semantic_effect_observer.py",
)
DATASET_METADATA_PATHS = (
    DATASET_ROOT / "features.json",
    DATASET_ROOT / "dataset_info.json",
    DATASET_ROOT
    / (
        "dataset_statistics_"
        "52c4489226d56b2b57ef8537aa0e29e58b74df154b0d09f535a6961a145ed292"
        ".json"
    ),
)
E1_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_pi05_selector_e1_protocol.json"
)
REQUIREMENTS = (
    {
        "id": "main_rgb",
        "description": "main RGB image",
        "any_of": ("steps.observation.image",),
    },
    {
        "id": "wrist_rgb",
        "description": "wrist RGB image",
        "any_of": ("steps.observation.wrist_image",),
    },
    {
        "id": "robot_state",
        "description": "EEF/gripper state",
        "any_of": ("steps.observation.state",),
    },
    {
        "id": "camera_intrinsics",
        "description": "per-camera intrinsic calibration",
        "any_of": (
            "steps.observation.camera_intrinsics",
            "episode_metadata.camera_intrinsics",
        ),
    },
    {
        "id": "camera_extrinsics",
        "description": "camera-to-robot/world extrinsic calibration",
        "any_of": (
            "steps.observation.camera_extrinsics",
            "episode_metadata.camera_extrinsics",
        ),
    },
    {
        "id": "target_identity_localization",
        "description": "target instance identity plus 2D/3D localization",
        "any_of": (
            "steps.observation.target_instance_mask",
            "steps.observation.target_pose",
            "steps.observation.object_poses",
        ),
    },
    {
        "id": "destination_geometry",
        "description": "destination instance/region geometry",
        "any_of": (
            "steps.observation.destination_instance_mask",
            "steps.observation.destination_pose",
            "steps.observation.region_geometry",
        ),
    },
    {
        "id": "visibility_occlusion",
        "description": "target/destination visibility and occlusion labels",
        "any_of": (
            "steps.observation.visibility",
            "steps.observation.occlusion",
        ),
    },
    {
        "id": "held_contact_state",
        "description": "held/grasp/contact supervision",
        "any_of": (
            "steps.observation.held_object",
            "steps.observation.contact_state",
            "steps.observation.grasp_state",
        ),
    },
    {
        "id": "trajectory_group_id",
        "description": "trajectory identity for leakage-safe grouping",
        "any_of": ("episode_metadata.file_path",),
    },
    {
        "id": "independent_qualification_split",
        "description": "frozen model/threshold-independent split",
        "any_of": (
            "dataset_split.validation",
            "dataset_split.test",
            "episode_metadata.qualification_split",
        ),
    },
)


class PerceptionPreflightError(RuntimeError):
    """Raised when the frozen E7 protocol or evidence is inconsistent."""


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def build_protocol() -> dict[str, Any]:
    return {
        "schema": (
            "proofalign.deployment-perception-preflight-e7.v1"
        ),
        "protocol_id": (
            "proofalign-deployment-perception-e7-20260725"
        ),
        "status": "frozen_data_adequacy_gate_before_model_selection",
        "created_at": "2026-07-25T00:00:00+08:00",
        "candidate_dataset": {
            "root": str(DATASET_ROOT),
            "metadata_sha256": {
                str(path): file_sha256(path)
                for path in DATASET_METADATA_PATHS
            },
            "e1_protocol_path": str(
                E1_PROTOCOL_PATH.relative_to(REPO_ROOT)
            ),
            "e1_protocol_sha256": file_sha256(E1_PROTOCOL_PATH),
        },
        "required_evidence": REQUIREMENTS,
        "qualification_design_if_data_gate_passes": {
            "minimum_tasks": 10,
            "minimum_trajectories_per_task": 20,
            "minimum_snapshots": 2000,
            "required_stage_groups": (
                "approach",
                "grasp",
                "transport",
                "pre_place",
                "release",
            ),
            "required_stress_groups": (
                "wrist_occluded",
                "base_occluded",
                "target_partially_visible",
                "destination_partially_visible",
                "novel_pose",
                "near_boundary",
            ),
            "split_unit": "trajectory_and_scene",
            "threshold_selection_split": "development_only",
            "qualification_split": "frozen_held_out",
            "forbidden_label_sources": (
                "reward",
                "success",
                "cost",
                "collision",
                "future_episode_outcome",
            ),
            "metrics": (
                "target_3d_error",
                "destination_3d_error",
                "held_state_accuracy",
                "visibility_calibration",
                "coverage",
                "ood_abstention",
                "worst_group",
                "latency",
            ),
        },
        "gates": {
            "all_required_evidence_present": True,
            "independent_qualification_split_present": True,
            "outcome_blind_labels": True,
        },
        "source_sha256": {
            relative: file_sha256(REPO_ROOT / relative)
            for relative in SOURCE_PATHS
        },
        "output": str(EVIDENCE_PATH.relative_to(REPO_ROOT)),
        "execution_authorization": {
            "training_authorized": False,
            "model_selection_authorized": False,
            "policy_load_authorized": False,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "outcome_read_authorized": False,
        },
        "claim_boundary": (
            "Dataset-schema adequacy only. This preflight neither trains "
            "nor qualifies a perception model and contains no policy, "
            "simulator, action, outcome, efficacy, deployment, or safety "
            "evidence."
        ),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if (
        protocol.get("schema")
        != "proofalign.deployment-perception-preflight-e7.v1"
    ):
        raise PerceptionPreflightError(
            "unsupported E7 protocol schema"
        )
    if protocol["status"] != (
        "frozen_data_adequacy_gate_before_model_selection"
    ):
        raise PerceptionPreflightError("E7 status changed")
    if protocol["output"] != str(
        EVIDENCE_PATH.relative_to(REPO_ROOT)
    ):
        raise PerceptionPreflightError("E7 output path changed")
    if canonical_text(
        protocol["required_evidence"]
    ) != canonical_text(REQUIREMENTS):
        raise PerceptionPreflightError(
            "E7 required evidence changed"
        )
    if any(protocol["execution_authorization"].values()):
        raise PerceptionPreflightError(
            "E7 protocol authorizes execution"
        )
    for relative, expected in protocol["source_sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise PerceptionPreflightError(
                f"E7 source binding is stale: {relative}"
            )
    candidate = protocol["candidate_dataset"]
    if candidate["e1_protocol_sha256"] != file_sha256(
        E1_PROTOCOL_PATH
    ):
        raise PerceptionPreflightError(
            "E7 E1 dataset protocol binding is stale"
        )
    for path_text, expected in candidate[
        "metadata_sha256"
    ].items():
        path = Path(path_text)
        if not path.is_file() or file_sha256(path) != expected:
            raise PerceptionPreflightError(
                f"E7 dataset metadata binding is stale: {path}"
            )


def _feature_paths() -> set[str]:
    features = json.loads(
        (DATASET_ROOT / "features.json").read_text(
            encoding="utf-8"
        )
    )
    root = features["featuresDict"]["features"]
    step = root["steps"]["sequence"]["feature"][
        "featuresDict"
    ]["features"]
    observation = step["observation"]["featuresDict"][
        "features"
    ]
    paths = {
        f"steps.{name}"
        for name in step
        if name != "observation"
    }
    paths.update(
        f"steps.observation.{name}" for name in observation
    )
    episode = root["episode_metadata"]["featuresDict"][
        "features"
    ]
    paths.update(
        f"episode_metadata.{name}" for name in episode
    )
    info = json.loads(
        (DATASET_ROOT / "dataset_info.json").read_text(
            encoding="utf-8"
        )
    )
    split_names = {
        str(split["name"])
        for split in info.get("splits", [])
        if isinstance(split, dict) and "name" in split
    }
    paths.update(f"dataset_split.{name}" for name in split_names)
    return paths


def build_evidence(protocol: dict[str, Any]) -> dict[str, Any]:
    validate_protocol(protocol)
    available = _feature_paths()
    rows = []
    for requirement in protocol["required_evidence"]:
        matches = sorted(
            set(requirement["any_of"]).intersection(available)
        )
        rows.append(
            {
                "id": requirement["id"],
                "description": requirement["description"],
                "required_any_of": requirement["any_of"],
                "matched_paths": matches,
                "present": bool(matches),
            }
        )
    missing = [row["id"] for row in rows if not row["present"]]
    all_present = not missing
    qualification_split = next(
        row
        for row in rows
        if row["id"] == "independent_qualification_split"
    )["present"]
    gate_results = {
        "all_required_evidence_present": all_present,
        "independent_qualification_split_present": (
            qualification_split
        ),
        "outcome_blind_labels": (
            protocol["qualification_design_if_data_gate_passes"][
                "forbidden_label_sources"
            ]
            == [
                "reward",
                "success",
                "cost",
                "collision",
                "future_episode_outcome",
            ]
        ),
    }
    ready = all(gate_results.values())
    return {
        "schema": (
            "proofalign.deployment-perception-preflight-result-e7.v1"
        ),
        "evidence_id": (
            "proofalign-deployment-perception-e7-preflight-20260725"
        ),
        "classification": (
            "deployment_perception_data_ready"
            if ready
            else "deployment_perception_data_inadequate"
        ),
        "training_performed": False,
        "model_selected": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "outcomes_read": False,
        "available_feature_paths": sorted(available),
        "requirement_rows": rows,
        "missing_requirement_ids": missing,
        "gate_results": gate_results,
        "qualification_ready": ready,
        "required_next_artifact": {
            "type": (
                "frozen_outcome_blind_perception_supervision_dataset"
            ),
            "must_add": missing,
            "must_preserve": (
                "trajectory-and-scene grouping",
                "development-only threshold selection",
                "held-out qualification split",
                "no reward/success/cost/collision label generation",
            ),
        },
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "claim_boundary": protocol["claim_boundary"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-protocol", action="store_true")
    mode.add_argument("--write-evidence", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write_protocol:
            if PROTOCOL_PATH.exists() and not args.replace_existing:
                raise PerceptionPreflightError(
                    f"refusing to replace frozen protocol: {PROTOCOL_PATH}"
                )
            PROTOCOL_PATH.parent.mkdir(parents=True, exist_ok=True)
            PROTOCOL_PATH.write_text(
                canonical_text(build_protocol()),
                encoding="utf-8",
            )
            print(PROTOCOL_PATH)
            return 0
        protocol = json.loads(
            PROTOCOL_PATH.read_text(encoding="utf-8")
        )
        expected = canonical_text(build_evidence(protocol))
        if args.check:
            if EVIDENCE_PATH.read_text(
                encoding="utf-8"
            ) != expected:
                raise PerceptionPreflightError(
                    "E7 preflight evidence is stale"
                )
            print(f"E7 preflight evidence is current: {EVIDENCE_PATH}")
            return 0
        if EVIDENCE_PATH.exists() and not args.replace_existing:
            raise PerceptionPreflightError(
                f"refusing to replace frozen evidence: {EVIDENCE_PATH}"
            )
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(expected, encoding="utf-8")
        result = json.loads(expected)
        print(
            json.dumps(
                {
                    "output": str(EVIDENCE_PATH),
                    "classification": result["classification"],
                    "missing_requirement_ids": result[
                        "missing_requirement_ids"
                    ],
                    "qualification_ready": result[
                        "qualification_ready"
                    ],
                },
                indent=2,
            )
        )
        return 0
    except (
        KeyError,
        OSError,
        PerceptionPreflightError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
