from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import dist
from typing import Any


class ActionKind(str, Enum):
    PICK = "Pick"
    PLACE = "Place"
    MOVE_TO = "MoveTo"
    AVOID = "Avoid"
    STOP = "Stop"
    REJECT = "Reject"


class Decision(str, Enum):
    ALLOW = "allow"
    REJECT = "reject"
    REPLAN = "replan"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Pose":
        data = data or {}
        return cls(float(data.get("x", 0.0)), float(data.get("y", 0.0)), float(data.get("z", 0.0)))

    def distance_to(self, other: "Pose") -> float:
        return dist((self.x, self.y, self.z), (other.x, other.y, other.z))

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class ObjectPart:
    name: str
    safe_to_grasp: bool = True
    dangerous: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "ObjectPart":
        if isinstance(data, str):
            return cls(name=data)
        return cls(
            name=str(data["name"]),
            safe_to_grasp=bool(data.get("safe_to_grasp", True)),
            dangerous=bool(data.get("dangerous", False)),
        )


@dataclass
class Object:
    object_id: str
    kind: str
    pose: Pose = field(default_factory=lambda: Pose(0, 0, 0))
    parts: dict[str, ObjectPart] = field(default_factory=dict)
    held_by: str | None = None
    handheld_by_human: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Object":
        parts = {p["name"] if isinstance(p, dict) else str(p): ObjectPart.from_dict(p) for p in data.get("parts", [])}
        return cls(
            object_id=str(data["id"]),
            kind=str(data.get("kind", data["id"])),
            pose=Pose.from_dict(data.get("pose")),
            parts=parts,
            held_by=data.get("held_by"),
            handheld_by_human=bool(data.get("handheld_by_human", False)),
        )

    def part(self, name: str | None) -> ObjectPart | None:
        if name is None:
            return None
        return self.parts.get(name)


@dataclass
class Region:
    region_id: str
    center: Pose
    radius: float = 0.2

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Region":
        return cls(str(data["id"]), Pose.from_dict(data.get("center")), float(data.get("radius", 0.2)))

    def contains(self, pose: Pose) -> bool:
        return self.center.distance_to(pose) <= self.radius


@dataclass(frozen=True)
class Relation:
    subject: str
    relation: str
    target: str


@dataclass
class WorldState:
    objects: dict[str, Object] = field(default_factory=dict)
    regions: dict[str, Region] = field(default_factory=dict)
    gripper_holding: str | None = None
    robot_pose: Pose = field(default_factory=lambda: Pose(0, 0, 0))
    min_distance_to_human_hand: float = 999.0
    min_distance_to_obstacle: float = 999.0
    collision: bool = False
    last_action_success: bool = True
    relations: list[Relation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldState":
        return cls(
            objects={obj["id"]: Object.from_dict(obj) for obj in data.get("objects", [])},
            regions={region["id"]: Region.from_dict(region) for region in data.get("regions", [])},
            gripper_holding=data.get("gripper_holding"),
            robot_pose=Pose.from_dict(data.get("robot_pose")),
            min_distance_to_human_hand=float(data.get("min_distance_to_human_hand", 999.0)),
            min_distance_to_obstacle=float(data.get("min_distance_to_obstacle", 999.0)),
            collision=bool(data.get("collision", False)),
            last_action_success=bool(data.get("last_action_success", True)),
            relations=[Relation(**r) for r in data.get("relations", [])],
            notes=list(data.get("notes", [])),
        )

    def clone(self) -> "WorldState":
        return WorldState.from_dict(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "objects": [
                {
                    "id": obj.object_id,
                    "kind": obj.kind,
                    "pose": obj.pose.to_dict(),
                    "parts": [
                        {
                            "name": part.name,
                            "safe_to_grasp": part.safe_to_grasp,
                            "dangerous": part.dangerous,
                        }
                        for part in obj.parts.values()
                    ],
                    "held_by": obj.held_by,
                    "handheld_by_human": obj.handheld_by_human,
                }
                for obj in self.objects.values()
            ],
            "regions": [
                {"id": region.region_id, "center": region.center.to_dict(), "radius": region.radius}
                for region in self.regions.values()
            ],
            "gripper_holding": self.gripper_holding,
            "robot_pose": self.robot_pose.to_dict(),
            "min_distance_to_human_hand": self.min_distance_to_human_hand,
            "min_distance_to_obstacle": self.min_distance_to_obstacle,
            "collision": self.collision,
            "last_action_success": self.last_action_success,
            "relations": [r.__dict__ for r in self.relations],
            "notes": list(self.notes),
        }


@dataclass
class TaskIntent:
    raw_instruction: str
    verb: str
    target_object: str | None = None
    target_part: str | None = None
    target_region: str | None = None
    avoid_objects: list[str] = field(default_factory=list)
    prohibited_objects: list[str] = field(default_factory=list)
    prohibited_parts: list[str] = field(default_factory=list)
    reject_required: bool = False
    unsafe_reason: str | None = None


@dataclass
class SafetySpec:
    safety_margin: float = 0.2
    protected_objects: list[str] = field(default_factory=list)
    forbidden_objects: list[str] = field(default_factory=list)
    forbidden_parts: list[str] = field(default_factory=list)
    require_no_collision: bool = True
    require_progress_to_region: bool = False
    reject_dangerous: bool = True
    require_certificates: bool = False
    certificate_min_confidence: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SafetySpec":
        data = data or {}
        return cls(
            safety_margin=float(data.get("safety_margin", 0.2)),
            protected_objects=list(data.get("protected_objects", [])),
            forbidden_objects=list(data.get("forbidden_objects", [])),
            forbidden_parts=list(data.get("forbidden_parts", [])),
            require_no_collision=bool(data.get("require_no_collision", True)),
            require_progress_to_region=bool(data.get("require_progress_to_region", False)),
            reject_dangerous=bool(data.get("reject_dangerous", True)),
            require_certificates=bool(data.get("require_certificates", False)),
            certificate_min_confidence=float(data.get("certificate_min_confidence", 0.5)),
        )


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    object_id: str | None = None
    part: str | None = None
    region: str | None = None
    pose: Pose | None = None
    avoid_object: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionContract:
    action: Action
    promise: str
    expected_holding: str | None = None
    expected_region: str | None = None
    min_human_hand_distance: float | None = None
    min_obstacle_distance: float | None = None
    no_collision: bool = True


@dataclass
class CheckResult:
    passed: bool
    layer: str
    violations: list[str] = field(default_factory=list)
    explanation: str = ""
    suggested_decision: Decision = Decision.ALLOW
    lean_mode: str = "mock"
    violation_reports: list[Any] = field(default_factory=list)


@dataclass
class ExecutionStep:
    action: Action
    intent_result: CheckResult
    effect_result: CheckResult | None
    decision: Decision
    before: WorldState
    after: WorldState | None = None
    pre_certificates: list[Any] = field(default_factory=list)
    post_certificates: list[Any] = field(default_factory=list)
    raw_action: Any | None = None
    proofalign_action: dict[str, Any] | None = None
    env_info: dict[str, Any] = field(default_factory=dict)
    reward: float | None = None
    done: bool | None = None
    runtime_seconds: dict[str, float] = field(default_factory=dict)


@dataclass
class ExecutionDecision:
    decision: Decision
    final_state: WorldState
    trace: list[ExecutionStep]
    explanation: str
