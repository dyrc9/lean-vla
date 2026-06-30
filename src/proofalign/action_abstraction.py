from __future__ import annotations

from typing import Any

from proofalign.models import Action, ActionKind, Pose


def action_from_dict(data: dict[str, Any]) -> Action:
    """Convert a simulated VLA action dictionary into a symbolic action."""

    kind_raw = str(data.get("type", data.get("kind", ""))).lower()
    if kind_raw in {"pick", "grasp"}:
        return Action(ActionKind.PICK, object_id=data.get("object"), part=data.get("part"), params=dict(data))
    if kind_raw in {"place", "put"}:
        return Action(ActionKind.PLACE, object_id=data.get("object"), region=data.get("region"), params=dict(data))
    if kind_raw in {"move", "moveto", "move_to"}:
        pose = Pose.from_dict(data.get("pose"))
        return Action(ActionKind.MOVE_TO, object_id=data.get("object"), pose=pose, region=data.get("region"), params=dict(data))
    if kind_raw == "avoid":
        return Action(ActionKind.AVOID, avoid_object=data.get("object"), params=dict(data))
    if kind_raw == "stop":
        return Action(ActionKind.STOP, params=dict(data))
    if kind_raw == "reject":
        return Action(ActionKind.REJECT, params=dict(data))
    raise ValueError(f"Unsupported VLA action type: {kind_raw!r}")


def actions_from_dicts(items: list[dict[str, Any]]) -> list[Action]:
    return [action_from_dict(item) for item in items]
