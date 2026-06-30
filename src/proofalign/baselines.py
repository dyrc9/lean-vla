from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from proofalign.action_abstraction import actions_from_dicts
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent
from proofalign.models import Decision, ExecutionDecision, ExecutionStep, SafetySpec, WorldState
from proofalign.simulator import DiscreteSimulator


class BaselineMode(str, Enum):
    VLA_ONLY = "vla_only"
    COLLISION_ONLY = "collision_only"
    INTENT_ONLY = "intent_only"
    EFFECT_ONLY = "effect_only"
    DUAL = "dual"


@dataclass
class BaselineRunner:
    checker: DualAlignmentChecker
    simulator: DiscreteSimulator

    def run(
        self,
        mode: BaselineMode,
        instruction: str,
        initial_state: WorldState,
        spec: SafetySpec,
        candidate_action_dicts: list[dict],
    ) -> ExecutionDecision:
        if mode == BaselineMode.DUAL:
            from proofalign.executor import SafetyExecutor

            return SafetyExecutor(self.checker, self.simulator).run(instruction, initial_state, spec, candidate_action_dicts)

        intent = parse_intent(instruction)
        state = initial_state
        trace: list[ExecutionStep] = []

        for action in actions_from_dicts(candidate_action_dicts):
            before = state.clone()
            if mode == BaselineMode.INTENT_ONLY:
                intent_result = self.checker.check_intent_alignment(intent, before, action, spec)
                trace.append(ExecutionStep(action, intent_result, None, intent_result.suggested_decision, before))
                if not intent_result.passed:
                    return ExecutionDecision(intent_result.suggested_decision, state, trace, intent_result.explanation)
                state = self.simulator.execute(before, action)
                continue

            after = self.simulator.execute(before, action)

            if mode == BaselineMode.VLA_ONLY:
                state = after
                continue

            if mode == BaselineMode.COLLISION_ONLY:
                collision = spec.require_no_collision and after.collision
                clearance = after.min_distance_to_human_hand < spec.safety_margin or after.min_distance_to_obstacle < spec.safety_margin
                if collision or clearance:
                    decision = Decision.SAFE_STOP if collision else Decision.REPLAN
                    return ExecutionDecision(decision, after, trace, "collision/clearance baseline blocked transition")
                state = after
                continue

            if mode == BaselineMode.EFFECT_ONLY:
                effect_result = self.checker.check_effect_alignment(before, action, after, spec)
                trace.append(ExecutionStep(action, effect_result, effect_result, effect_result.suggested_decision, before, after))
                if not effect_result.passed:
                    return ExecutionDecision(effect_result.suggested_decision, after, trace, effect_result.explanation)
                state = after
                continue

        return ExecutionDecision(Decision.ALLOW, state, trace, f"{mode.value} completed candidate actions")
