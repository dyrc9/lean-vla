"""Task-bound compiler for the frozen LIBERO-Safety affordance grasp slice.

The generic legacy instruction parser is intentionally not used here.  A manifest
binds one suite/task id and one BDDL digest to the exact benchmark goal predicate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from proofalign.ctda import (
    AuthorityEnvelope,
    MissionSpec,
    PhaseObligation,
    TaskTransition,
    TimeBase,
    canonical_json,
    digest_payload,
    digest_text,
)
from proofalign.models import GripperContactPartQuery, WorldState


MANIFEST_REGISTRY_SCHEMA = "proofalign.libero.task-manifests.v1"
MANIFEST_SCHEMA = "proofalign.libero.task-manifest.v1"
CONTACT_PART_PREDICATE = "CheckGripperContactPart"
CONTACT_PART_BINDING = "bddl_safe_geom_set"


class LiberoTaskManifestError(ValueError):
    """Raised when a task manifest is absent, malformed, or not source-bound."""


@dataclass(frozen=True)
class LiberoTaskManifest:
    suite: str
    task_id: int
    task_name: str
    bddl_file: str
    bddl_sha256: str
    instruction: str
    goal_predicate: str
    target_object: str
    geom_ids: tuple[str, ...]
    grasp_binding: str = CONTACT_PART_BINDING
    schema: str = MANIFEST_SCHEMA
    manifest_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "suite",
            "task_name",
            "bddl_file",
            "bddl_sha256",
            "instruction",
            "goal_predicate",
            "target_object",
            "grasp_binding",
        ):
            value = str(getattr(self, name)).strip()
            if not value:
                raise LiberoTaskManifestError(f"manifest field {name} must be non-empty")
            object.__setattr__(self, name, value)
        if self.schema != MANIFEST_SCHEMA:
            raise LiberoTaskManifestError(f"unsupported task manifest schema: {self.schema}")
        if type(self.task_id) is not int or self.task_id < 0:
            raise LiberoTaskManifestError("manifest task_id must be a non-negative integer")
        if not re.fullmatch(r"[0-9a-f]{64}", self.bddl_sha256):
            raise LiberoTaskManifestError("manifest BDDL digest must be lowercase SHA-256")
        if self.goal_predicate != CONTACT_PART_PREDICATE:
            raise LiberoTaskManifestError(
                f"unsupported manifest goal predicate: {self.goal_predicate}"
            )
        query = GripperContactPartQuery(self.target_object, self.geom_ids)
        object.__setattr__(self, "geom_ids", query.geom_ids)
        object.__setattr__(self, "manifest_digest", digest_payload(self.unsigned_payload()))

    @property
    def contact_query(self) -> GripperContactPartQuery:
        return GripperContactPartQuery(self.target_object, self.geom_ids)

    @property
    def goal_atom(self) -> str:
        return self.contact_query.atom

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "suite": self.suite,
            "task_id": self.task_id,
            "task_name": self.task_name,
            "bddl_file": self.bddl_file,
            "bddl_sha256": self.bddl_sha256,
            "instruction": self.instruction,
            "goal_predicate": self.goal_predicate,
            "target_object": self.target_object,
            "geom_ids": self.geom_ids,
            "grasp_binding": self.grasp_binding,
        }


def load_libero_task_manifest(
    registry_path: Path,
    *,
    suite: str,
    task_id: int,
    bddl_path: Path,
) -> LiberoTaskManifest:
    """Load and verify one manifest against the selected benchmark BDDL bytes."""

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiberoTaskManifestError(f"cannot read task manifest registry: {exc}") from exc
    if not isinstance(registry, dict) or registry.get("schema") != MANIFEST_REGISTRY_SCHEMA:
        raise LiberoTaskManifestError("unsupported LIBERO task manifest registry schema")
    entries = registry.get("manifests")
    if not isinstance(entries, list):
        raise LiberoTaskManifestError("task manifest registry has no manifests list")
    matches = [
        item
        for item in entries
        if isinstance(item, dict)
        and item.get("suite") == suite
        and item.get("task_id") == task_id
    ]
    if len(matches) != 1:
        raise LiberoTaskManifestError(
            f"expected one task manifest for {suite}/{task_id}, found {len(matches)}"
        )
    try:
        bddl_bytes = bddl_path.read_bytes()
    except OSError as exc:
        raise LiberoTaskManifestError(f"cannot read selected BDDL: {exc}") from exc
    digest = sha256(bddl_bytes).hexdigest()
    text = bddl_bytes.decode("utf-8")
    instruction, target, geom_ids = parse_contact_part_bddl_goal(text)
    item = dict(matches[0])
    item.setdefault("schema", MANIFEST_SCHEMA)
    item["instruction"] = instruction
    manifest = LiberoTaskManifest(**item)
    if manifest.bddl_sha256 != digest:
        raise LiberoTaskManifestError(
            f"BDDL digest mismatch for {suite}/{task_id}: {digest} != {manifest.bddl_sha256}"
        )
    if manifest.target_object != target or manifest.geom_ids != geom_ids:
        raise LiberoTaskManifestError(
            f"manifest goal differs from selected BDDL for {suite}/{task_id}"
        )
    return manifest


def parse_contact_part_bddl_goal(text: str) -> tuple[str, str, tuple[str, ...]]:
    """Parse only an exact single-atom ``CheckGripperContactPart`` goal."""

    instruction_match = re.search(r"\(:language\s+([^)]+)\)", text, re.IGNORECASE)
    if instruction_match is None:
        raise LiberoTaskManifestError("BDDL has no language field")
    instruction = " ".join(instruction_match.group(1).split())
    goal_match = re.search(
        r"\(:goal\s*\(\s*And\s*"
        r"\(\s*Checkgrippercontactpart\s+([A-Za-z0-9_]+)\s+"
        r"\(([^()]*)\)\s*\)\s*\)\s*\)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if goal_match is None:
        raise LiberoTaskManifestError(
            "BDDL goal is not one exact CheckGripperContactPart conjunction"
        )
    if len(re.findall(r"\(:goal\b", text, re.IGNORECASE)) != 1:
        raise LiberoTaskManifestError("BDDL must contain exactly one goal section")
    target = goal_match.group(1)
    tokens = tuple(re.findall(r"\d+", goal_match.group(2)))
    query = GripperContactPartQuery(target, tokens)
    return instruction, query.object_id, query.geom_ids


def compile_libero_task_manifest(
    manifest: LiberoTaskManifest,
    state: WorldState,
    safety_spec: Any,
    authority: AuthorityEnvelope,
    time_base: TimeBase,
    *,
    spec_id: str,
    episode_nonce: str,
) -> MissionSpec:
    """Compile a source-bound contact-part manifest into a typed CTDA mission."""

    if manifest.target_object not in state.objects:
        raise LiberoTaskManifestError("manifest target is absent from the observed registry")
    matching_observations = [
        item
        for item in state.gripper_contact_parts
        if item.atom == manifest.goal_atom
    ]
    if len(matching_observations) != 1:
        raise LiberoTaskManifestError(
            "exact contact-part observation is unavailable or duplicated"
        )
    initial_phase = "contact" if matching_observations[0].satisfied else "approach"
    forbidden_objects = tuple(
        sorted(str(item) for item in getattr(safety_spec, "forbidden_objects", ()))
    )
    forbidden_parts = tuple(
        sorted(str(item) for item in getattr(safety_spec, "forbidden_parts", ()))
    )
    must_preserve = {
        str(item) for item in getattr(safety_spec, "protected_objects", ())
    }
    must_preserve.discard(manifest.target_object)
    hard_invariants = _hard_invariants(safety_spec, must_preserve)
    required_evidence = (
        ("legacy_certificate",)
        if getattr(safety_spec, "require_certificates", False)
        else ()
    )
    transition = TaskTransition("approach", "Pick", "contact")
    obligation = PhaseObligation(
        obligation_id=f"libero-manifest:{manifest.manifest_digest}:contact-part",
        source_phase=transition.source_phase,
        skill=transition.skill,
        destination_phase=transition.destination_phase,
        guarantees=(manifest.goal_atom,),
        target=manifest.target_object,
        part=manifest.grasp_binding,
        completes_goal=True,
    )
    unsigned_authority = replace(
        authority,
        attestation_digest="unsigned",
        authenticated=False,
        attestation=None,
    )
    goal = canonical_json(
        {
            "manifest_digest": manifest.manifest_digest,
            "bddl_sha256": manifest.bddl_sha256,
            "predicate": manifest.goal_predicate,
            "target_object": manifest.target_object,
            "geom_ids": manifest.geom_ids,
        }
    )
    return MissionSpec(
        spec_id=spec_id,
        authority=unsigned_authority,
        instruction_digest=digest_text(manifest.instruction),
        goal=goal,
        phases=("approach", "contact"),
        transitions=(transition,),
        initial_phase=initial_phase,
        time_base=time_base,
        episode_nonce=episode_nonce,
        hard_invariants=hard_invariants,
        object_ids=tuple(sorted(str(item) for item in state.objects)),
        region_ids=tuple(sorted(str(item) for item in state.regions)),
        safe_parts=((manifest.target_object, manifest.grasp_binding),),
        forbidden_objects=forbidden_objects,
        forbidden_parts=forbidden_parts,
        default_must_preserve=tuple(sorted(must_preserve)),
        required_evidence=required_evidence,
        goal_atoms=(manifest.goal_atom,),
        goal_phases=("contact",),
        phase_obligations=(obligation,),
    )


def _hard_invariants(safety_spec: Any, must_preserve: set[str]) -> tuple[str, ...]:
    result: list[str] = []
    if getattr(safety_spec, "require_no_collision", True):
        result.append("no_collision")
    margin = getattr(safety_spec, "safety_margin", None)
    keys = {_symbol_key(item) for item in must_preserve}
    if margin is not None and any("humanhand" in item for item in keys):
        result.append(f"human_clearance>={margin}")
    if margin is not None and any("obstacle" in item for item in keys):
        result.append(f"obstacle_clearance>={margin}")
    return tuple(result)


def _symbol_key(value: Any) -> str:
    text = re.sub(r"__?\d+$", "", str(value).lower())
    return re.sub(r"[^a-z0-9]", "", text)


def manifest_registry_digest(path: Path) -> str:
    """Return the byte-level SHA-256 used by the E0 protocol pin."""

    return sha256(path.read_bytes()).hexdigest()


__all__ = [
    "CONTACT_PART_BINDING",
    "CONTACT_PART_PREDICATE",
    "LiberoTaskManifest",
    "LiberoTaskManifestError",
    "compile_libero_task_manifest",
    "load_libero_task_manifest",
    "manifest_registry_digest",
    "parse_contact_part_bddl_goal",
]
