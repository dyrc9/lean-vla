from __future__ import annotations

import argparse
import json
from pathlib import Path

from proofalign.action_abstraction import actions_from_dicts
from proofalign.certificates import CertificateBundle
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent
from proofalign.models import Action, ActionKind, Decision, ExecutionDecision, ExecutionStep, SafetySpec, WorldState
from proofalign.results import format_execution
from proofalign.simulator import DiscreteSimulator


class SafetyExecutor:
    def __init__(self, checker: DualAlignmentChecker | None = None, simulator: DiscreteSimulator | None = None) -> None:
        self.checker = checker or DualAlignmentChecker()
        self.simulator = simulator or DiscreteSimulator()

    def run(self, instruction: str, initial_state: WorldState, spec: SafetySpec, candidate_action_dicts: list[dict]) -> ExecutionDecision:
        intent = parse_intent(instruction)
        state = initial_state
        trace: list[ExecutionStep] = []

        if intent.reject_required:
            reject_action = Action(ActionKind.REJECT)
            result = self.checker.check_intent_alignment(intent, state, reject_action, spec)
            trace.append(ExecutionStep(reject_action, result, None, Decision.REJECT, state.clone()))
            return ExecutionDecision(Decision.REJECT, state, trace, result.explanation)

        for action in actions_from_dicts(candidate_action_dicts):
            before = state.clone()
            pre_certs = CertificateBundle.from_dicts(action.params.get("pre_certificates"))
            intent_result = self.checker.check_intent_alignment(intent, before, action, spec, pre_certs, len(trace))
            if not intent_result.passed:
                trace.append(
                    ExecutionStep(
                        action,
                        intent_result,
                        None,
                        intent_result.suggested_decision,
                        before,
                        pre_certificates=pre_certs.to_dicts(),
                    )
                )
                return ExecutionDecision(intent_result.suggested_decision, state, trace, intent_result.explanation)

            after = self.simulator.execute(before, action)
            post_certs = CertificateBundle.from_dicts(action.params.get("post_certificates"))
            effect_result = self.checker.check_effect_alignment(before, action, after, spec, post_certs, len(trace))
            decision = effect_result.suggested_decision
            trace.append(
                ExecutionStep(
                    action,
                    intent_result,
                    effect_result,
                    decision,
                    before,
                    after,
                    pre_certificates=pre_certs.to_dicts(),
                    post_certificates=post_certs.to_dicts(),
                )
            )
            if not effect_result.passed:
                return ExecutionDecision(decision, after, trace, effect_result.explanation)
            state = after

        return ExecutionDecision(Decision.ALLOW, state, trace, "all candidate actions passed both alignment layers")


def load_example(path: Path) -> tuple[str, WorldState, SafetySpec, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return (
        data["instruction"],
        WorldState.from_dict(data["initial_state"]),
        SafetySpec.from_dict(data.get("safety_spec")),
        data["candidate_actions"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ProofAlign safety wrapper demo.")
    parser.add_argument(
        "example",
        nargs="?",
        default="examples/tasks/aag_safe_grasp.json",
        help="Path to an example JSON task.",
    )
    args = parser.parse_args()
    instruction, state, spec, actions = load_example(Path(args.example))
    decision = SafetyExecutor().run(instruction, state, spec, actions)
    print(format_execution(decision))


if __name__ == "__main__":
    main()
