from __future__ import annotations

from proofalign.models import Action, ActionKind, Pose, WorldState


class DiscreteSimulator:
    """A tiny symbolic simulator for contract-level behavior."""

    def execute(self, state: WorldState, action: Action) -> WorldState:
        next_state = state.clone()
        next_state.last_action_success = True

        if action.params.get("collision"):
            next_state.collision = True
        if "human_hand_distance" in action.params:
            next_state.min_distance_to_human_hand = float(action.params["human_hand_distance"])
        if "obstacle_distance" in action.params:
            next_state.min_distance_to_obstacle = float(action.params["obstacle_distance"])

        if action.kind == ActionKind.PICK:
            self._pick(next_state, action)
        elif action.kind == ActionKind.PLACE:
            self._place(next_state, action)
        elif action.kind == ActionKind.MOVE_TO:
            self._move_to(next_state, action)
        elif action.kind == ActionKind.STOP:
            next_state.notes.append("safe stop requested")
        elif action.kind == ActionKind.REJECT:
            next_state.notes.append("instruction rejected")

        return next_state

    def _pick(self, state: WorldState, action: Action) -> None:
        obj = state.objects.get(action.object_id or "")
        if not obj or action.params.get("fail_grasp"):
            state.last_action_success = False
            return
        wrong_object = action.params.get("actual_object")
        if wrong_object and wrong_object in state.objects:
            obj = state.objects[wrong_object]
        obj.held_by = "gripper"
        state.gripper_holding = obj.object_id

    def _place(self, state: WorldState, action: Action) -> None:
        obj = state.objects.get(action.object_id or "")
        region = state.regions.get(action.region or "")
        if not obj or not region or action.params.get("fail_place"):
            state.last_action_success = False
            return
        obj.held_by = None
        state.gripper_holding = None
        if action.params.get("wrong_region") and action.params["wrong_region"] in state.regions:
            obj.pose = state.regions[action.params["wrong_region"]].center
        else:
            obj.pose = region.center

    def _move_to(self, state: WorldState, action: Action) -> None:
        pose = action.pose or Pose(0, 0, 0)
        state.robot_pose = pose
        if action.object_id and action.object_id in state.objects:
            state.objects[action.object_id].pose = pose
