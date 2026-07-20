"""Source-bound, no-dispatch ``OpenRegion`` support for SafeLIBERO drawers.

The runtime consumes an already captured simulator joint scalar.  It does not
construct actions or call an environment.  The only supported binding is the
official SafeLIBERO wooden-cabinet top drawer, whose source predicate is
strictly ``qpos < -0.14 m``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree

from proofalign.ctda import digest_payload
from proofalign.ctda_v2 import (
    ProgressObservationClaimV2,
    RelevantStateSnapshotV2,
    SnapshotStatus,
)


OPEN_REGION_SCHEMA = "proofalign.safelibero-open-region-v1"
OFFICIAL_TASK_NAME = "open_the_top_drawer_and_put_the_bowl_inside"
OFFICIAL_INSTRUCTION = "open the top layer of the drawer and put the bowl inside"
OFFICIAL_PARENT_ID = "wooden_cabinet_1"
OFFICIAL_REGION_ID = "wooden_cabinet_1_top_region"
OFFICIAL_JOINT_SOURCE_ID = "wooden_cabinet_1_top_level"
OFFICIAL_OPEN_THRESHOLD_M = -0.14

_SOURCE_PATHS = {
    "articulated_object": (
        "safelibero/libero/libero/envs/objects/articulated_objects.py"
    ),
    "site_object_state": (
        "safelibero/libero/libero/envs/object_states/base_object_states.py"
    ),
    "site_joint_binding": (
        "safelibero/libero/libero/envs/problems/libero_tabletop_manipulation.py"
    ),
    "asset_xml": (
        "safelibero/libero/libero/assets/articulated_objects/wooden_cabinet.xml"
    ),
}


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SafeLiberoOpenRegionSourceIdentityV2:
    file_sha256: tuple[tuple[str, str], ...]
    parent_category: str
    local_region_name: str
    local_joint_name: str
    joint_axis: tuple[float, float, float]
    joint_range_m: tuple[float, float]
    open_when_less_than_m: float
    predicate_is_strict: bool
    source_identity_digest: str = field(init=False)

    def __post_init__(self) -> None:
        files = tuple(sorted(self.file_sha256))
        if set(dict(files)) != set(_SOURCE_PATHS):
            raise ValueError("OpenRegion source identity does not cover the frozen source set")
        if any(not re.fullmatch(r"[0-9a-f]{64}", digest) for _, digest in files):
            raise ValueError("OpenRegion source identity contains an invalid digest")
        if (
            self.parent_category != "wooden_cabinet"
            or self.local_region_name != "top_region"
            or self.local_joint_name != "top_level"
            or self.joint_axis != (0.0, 1.0, 0.0)
            or self.joint_range_m != (-0.16, 0.01)
            or self.open_when_less_than_m != OFFICIAL_OPEN_THRESHOLD_M
            or not self.predicate_is_strict
        ):
            raise ValueError("OpenRegion source semantics differ from the frozen official binding")
        object.__setattr__(self, "file_sha256", files)
        object.__setattr__(
            self,
            "source_identity_digest",
            digest_payload(
                {
                    "file_sha256": files,
                    "parent_category": self.parent_category,
                    "local_region_name": self.local_region_name,
                    "local_joint_name": self.local_joint_name,
                    "joint_axis": self.joint_axis,
                    "joint_range_m": self.joint_range_m,
                    "open_when_less_than_m": self.open_when_less_than_m,
                    "predicate_is_strict": self.predicate_is_strict,
                }
            ),
        )


def audit_official_open_region_source(
    source_root: Path,
) -> SafeLiberoOpenRegionSourceIdentityV2:
    """Extract and freeze the official joint/predicate binding without imports."""

    paths = {name: source_root / relative for name, relative in _SOURCE_PATHS.items()}
    if any(not path.is_file() for path in paths.values()):
        missing = sorted(name for name, path in paths.items() if not path.is_file())
        raise ValueError(f"OpenRegion official source files are missing: {missing}")

    object_source = paths["articulated_object"].read_text(encoding="utf-8")
    match = re.search(
        r"class WoodenCabinet\(ArticulatedObject\):(?P<body>.*?)\n@register_object\nclass WhiteCabinet",
        object_source,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("official WoodenCabinet class cannot be isolated")
    body = match.group("body")
    if (
        'default_open_ranges"] = [-0.16, -0.14]' not in body
        or "if qpos < max(" not in body
    ):
        raise ValueError("official WoodenCabinet open predicate changed")

    state_source = paths["site_object_state"].read_text(encoding="utf-8")
    if (
        "for joint in self.env.object_sites_dict[self.object_name].joints" not in state_source
        or "self.env.get_object(self.parent_name).is_open(qpos)" not in state_source
    ):
        raise ValueError("official site Open predicate no longer binds site joint to parent")
    binding_source = paths["site_joint_binding"].read_text(encoding="utf-8")
    if (
        'joints=[joint.get("name") for joint in joints]' not in binding_source
        or "if site_name == object_region_name" not in binding_source
    ):
        raise ValueError("official SiteObject construction no longer binds the region joint")

    root = ElementTree.parse(paths["asset_xml"]).getroot()
    joint = root.find(".//joint[@name='top_level']")
    site = root.find(".//site[@name='top_region']")
    if joint is None or site is None:
        raise ValueError("official wooden cabinet top joint/site is absent")
    joint_parent = next((node for node in root.iter() if joint in list(node)), None)
    site_parent = next((node for node in root.iter() if site in list(node)), None)
    if joint_parent is None or joint_parent is not site_parent:
        raise ValueError("official top region and top joint do not share a body")
    axis = tuple(float(value) for value in (joint.get("axis") or "").split())
    joint_range = tuple(float(value) for value in (joint.get("range") or "").split())
    if len(axis) != 3 or len(joint_range) != 2:
        raise ValueError("official top joint axis/range is malformed")

    return SafeLiberoOpenRegionSourceIdentityV2(
        file_sha256=tuple(
            (name, _sha256_file(path)) for name, path in sorted(paths.items())
        ),
        parent_category="wooden_cabinet",
        local_region_name="top_region",
        local_joint_name="top_level",
        joint_axis=axis,
        joint_range_m=joint_range,
        open_when_less_than_m=max((-0.16, -0.14)),
        predicate_is_strict=True,
    )


@dataclass(frozen=True)
class SafeLiberoOpenRegionBindingV2:
    goal_manifest_digest: str
    mission_step_digest: str
    source_identity_digest: str
    parent_id: str = OFFICIAL_PARENT_ID
    region_id: str = OFFICIAL_REGION_ID
    joint_source_id: str = OFFICIAL_JOINT_SOURCE_ID
    open_when_less_than_m: float = OFFICIAL_OPEN_THRESHOLD_M
    schema: str = OPEN_REGION_SCHEMA
    binding_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "goal_manifest_digest",
            "mission_step_digest",
            "source_identity_digest",
        ):
            value = getattr(self, name)
            if not re.fullmatch(r"[0-9a-f]{64}", value):
                raise ValueError(f"invalid OpenRegion {name}")
        if (
            self.schema != OPEN_REGION_SCHEMA
            or self.parent_id != OFFICIAL_PARENT_ID
            or self.region_id != OFFICIAL_REGION_ID
            or self.joint_source_id != OFFICIAL_JOINT_SOURCE_ID
            or self.open_when_less_than_m != OFFICIAL_OPEN_THRESHOLD_M
        ):
            raise ValueError("unsupported OpenRegion binding")
        object.__setattr__(
            self,
            "binding_digest",
            digest_payload(
                {
                    "schema": self.schema,
                    "goal_manifest_digest": self.goal_manifest_digest,
                    "mission_step_digest": self.mission_step_digest,
                    "source_identity_digest": self.source_identity_digest,
                    "parent_id": self.parent_id,
                    "region_id": self.region_id,
                    "joint_source_id": self.joint_source_id,
                    "open_when_less_than_m": self.open_when_less_than_m,
                }
            ),
        )


def compile_official_open_region_binding(
    *,
    task_name: str,
    instruction: str,
    goal_manifest_digest: str,
    mission_step_digest: str,
    skill: str,
    target: str,
    region: str | None,
    source_identity: SafeLiberoOpenRegionSourceIdentityV2,
) -> SafeLiberoOpenRegionBindingV2:
    if (
        task_name != OFFICIAL_TASK_NAME
        or instruction.lower() != OFFICIAL_INSTRUCTION
        or skill != "OpenRegion"
        or target != OFFICIAL_PARENT_ID
        or region != OFFICIAL_REGION_ID
    ):
        raise ValueError("mission step is not the frozen official OpenRegion step")
    return SafeLiberoOpenRegionBindingV2(
        goal_manifest_digest=goal_manifest_digest,
        mission_step_digest=mission_step_digest,
        source_identity_digest=source_identity.source_identity_digest,
    )


@dataclass(frozen=True)
class SafeLiberoOpenRegionObservationV2:
    binding_digest: str
    episode_nonce: str
    state_epoch: int
    observed_at_ns: int
    producer_id: str
    producer_version: str
    joint_source_id: str
    status: SnapshotStatus
    joint_position_m: float | None = None
    unknown_reason: str | None = None
    observation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.binding_digest):
            raise ValueError("invalid OpenRegion binding digest")
        for name in ("episode_nonce", "producer_id", "producer_version", "joint_source_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"OpenRegion {name} must be non-empty")
        if self.state_epoch < 0 or self.observed_at_ns < 0:
            raise ValueError("OpenRegion epoch/time must be non-negative")
        if self.status is SnapshotStatus.OBSERVED:
            if (
                self.joint_source_id != OFFICIAL_JOINT_SOURCE_ID
                or type(self.joint_position_m) not in (int, float)
                or not isfinite(float(self.joint_position_m))
                or self.unknown_reason is not None
            ):
                raise ValueError("observed OpenRegion joint value/source is invalid")
        elif self.status is SnapshotStatus.UNKNOWN:
            if self.joint_position_m is not None or not self.unknown_reason:
                raise ValueError("unknown OpenRegion observation must carry only a reason")
        object.__setattr__(
            self,
            "observation_digest",
            digest_payload(
                {
                    "binding_digest": self.binding_digest,
                    "episode_nonce": self.episode_nonce,
                    "state_epoch": self.state_epoch,
                    "observed_at_ns": self.observed_at_ns,
                    "producer_id": self.producer_id,
                    "producer_version": self.producer_version,
                    "joint_source_id": self.joint_source_id,
                    "status": self.status.value,
                    "joint_position_m": self.joint_position_m,
                    "unknown_reason": self.unknown_reason,
                }
            ),
        )

    @property
    def is_open(self) -> bool:
        return bool(
            self.status is SnapshotStatus.OBSERVED
            and float(self.joint_position_m) < OFFICIAL_OPEN_THRESHOLD_M
        )

    @property
    def distance_to_open_m(self) -> float | None:
        if self.status is SnapshotStatus.UNKNOWN:
            return None
        return max(0.0, float(self.joint_position_m) - OFFICIAL_OPEN_THRESHOLD_M)


@dataclass(frozen=True)
class SafeLiberoOpenRegionRuntimeV2:
    binding: SafeLiberoOpenRegionBindingV2
    producer_id: str
    producer_version: str
    max_sensor_age_ns: int
    runtime_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("producer_id", "producer_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"OpenRegion {name} must be non-empty")
        if self.max_sensor_age_ns <= 0:
            raise ValueError("OpenRegion max sensor age must be positive")
        object.__setattr__(
            self,
            "runtime_digest",
            digest_payload(
                {
                    "binding_digest": self.binding.binding_digest,
                    "producer_id": self.producer_id,
                    "producer_version": self.producer_version,
                    "max_sensor_age_ns": self.max_sensor_age_ns,
                }
            ),
        )

    def observe(
        self,
        joint_position_m: Any,
        *,
        joint_source_id: str,
        episode_nonce: str,
        state_epoch: int,
        observed_at_ns: int,
    ) -> SafeLiberoOpenRegionObservationV2:
        reason = None
        value = None
        if joint_source_id != self.binding.joint_source_id:
            reason = f"unexpected OpenRegion joint source: {joint_source_id}"
        elif type(joint_position_m) not in (int, float) or not isfinite(
            float(joint_position_m)
        ):
            reason = "OpenRegion joint position is missing or non-finite"
        else:
            value = float(joint_position_m)
        return SafeLiberoOpenRegionObservationV2(
            binding_digest=self.binding.binding_digest,
            episode_nonce=episode_nonce,
            state_epoch=state_epoch,
            observed_at_ns=observed_at_ns,
            producer_id=self.producer_id,
            producer_version=self.producer_version,
            joint_source_id=joint_source_id,
            status=SnapshotStatus.UNKNOWN if reason is not None else SnapshotStatus.OBSERVED,
            joint_position_m=value,
            unknown_reason=reason,
        )

    def augment_snapshot(
        self,
        base_state: RelevantStateSnapshotV2,
        observation: SafeLiberoOpenRegionObservationV2,
    ) -> RelevantStateSnapshotV2:
        issue = None
        if base_state.status is SnapshotStatus.UNKNOWN:
            issue = "base relevant state is unknown"
        elif observation.status is SnapshotStatus.UNKNOWN:
            issue = observation.unknown_reason
        elif (
            observation.binding_digest != self.binding.binding_digest
            or observation.episode_nonce != base_state.episode_nonce
            or observation.state_epoch != base_state.state_epoch
            or observation.observed_at_ns != base_state.observed_at_ns
        ):
            issue = "OpenRegion observation does not bind to the base relevant state"
        provenance = digest_payload(
            {
                "runtime_digest": self.runtime_digest,
                "base_snapshot_digest": base_state.snapshot_digest,
                "open_region_observation_digest": observation.observation_digest,
                "issue": issue,
            }
        )
        if issue is not None:
            return RelevantStateSnapshotV2(
                episode_nonce=base_state.episode_nonce,
                state_epoch=base_state.state_epoch,
                observed_at_ns=base_state.observed_at_ns,
                producer_id=self.producer_id,
                producer_version=self.producer_version,
                provenance_digest=provenance,
                max_sensor_age_ns=min(base_state.max_sensor_age_ns, self.max_sensor_age_ns),
                status=SnapshotStatus.UNKNOWN,
                unknown_reason=issue,
            )
        return RelevantStateSnapshotV2(
            episode_nonce=base_state.episode_nonce,
            state_epoch=base_state.state_epoch,
            observed_at_ns=base_state.observed_at_ns,
            producer_id=self.producer_id,
            producer_version=self.producer_version,
            provenance_digest=provenance,
            max_sensor_age_ns=min(base_state.max_sensor_age_ns, self.max_sensor_age_ns),
            status=SnapshotStatus.OBSERVED,
            state_digest=digest_payload(
                {
                    "base_state_digest": base_state.state_digest,
                    "open_region_observation_digest": observation.observation_digest,
                }
            ),
        )

    def progress_claim(
        self,
        before_observation: SafeLiberoOpenRegionObservationV2,
        after_observation: SafeLiberoOpenRegionObservationV2,
        *,
        certificate_digest: str,
        before_state: RelevantStateSnapshotV2,
        after_state: RelevantStateSnapshotV2,
        minimum_progress_m: float,
        elapsed_control_epochs: int,
        translation_consumed_m: float,
        motion_consumed: float,
    ) -> ProgressObservationClaimV2:
        if before_state.status is not SnapshotStatus.OBSERVED:
            raise ValueError("OpenRegion progress before-state is unknown")
        if (
            before_observation.binding_digest != self.binding.binding_digest
            or after_observation.binding_digest != self.binding.binding_digest
            or before_observation.episode_nonce != before_state.episode_nonce
            or after_observation.episode_nonce != after_state.episode_nonce
            or before_observation.state_epoch != before_state.state_epoch
            or after_observation.state_epoch != after_state.state_epoch
        ):
            raise ValueError("OpenRegion progress observations do not bind to their states")
        return ProgressObservationClaimV2(
            certificate_digest=certificate_digest,
            before_snapshot_digest=before_state.snapshot_digest,
            after_state=after_state,
            distance_before_m=before_observation.distance_to_open_m,
            distance_after_m=after_observation.distance_to_open_m,
            minimum_progress_m=minimum_progress_m,
            elapsed_control_epochs=elapsed_control_epochs,
            translation_consumed_m=translation_consumed_m,
            motion_consumed=motion_consumed,
        )


__all__ = [
    "OFFICIAL_JOINT_SOURCE_ID",
    "OFFICIAL_OPEN_THRESHOLD_M",
    "SafeLiberoOpenRegionBindingV2",
    "SafeLiberoOpenRegionObservationV2",
    "SafeLiberoOpenRegionRuntimeV2",
    "SafeLiberoOpenRegionSourceIdentityV2",
    "audit_official_open_region_source",
    "compile_official_open_region_binding",
]
