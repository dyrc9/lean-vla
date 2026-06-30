from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from proofalign.models import Decision


class ViolationType(str, Enum):
    INTENT_MISMATCH = "intent_mismatch"
    FORBIDDEN_OBJECT = "forbidden_object"
    UNSAFE_AFFORDANCE = "unsafe_affordance"
    PRECONDITION = "precondition"
    POSTCONDITION = "postcondition"
    COLLISION = "collision"
    CLEARANCE = "clearance"
    FRAME_CONDITION = "frame_condition"
    CERTIFICATE = "certificate"
    UNKNOWN_INTENT = "unknown_intent"


@dataclass(frozen=True)
class ViolationReport:
    violation_type: ViolationType
    layer: str
    message: str
    object_refs: list[str] = field(default_factory=list)
    certificate_refs: list[str] = field(default_factory=list)
    recoverability: Decision = Decision.REPLAN
    repair_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "violation_type": self.violation_type.value,
            "layer": self.layer,
            "message": self.message,
            "object_refs": self.object_refs,
            "certificate_refs": self.certificate_refs,
            "recoverability": self.recoverability.value,
            "repair_hint": self.repair_hint,
            "metadata": self.metadata,
        }
