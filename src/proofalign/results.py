from __future__ import annotations

from proofalign.models import CheckResult, ExecutionDecision


def format_check_result(result: CheckResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    return f"[{status}] {result.layer}: {result.explanation} ({result.suggested_decision.value}, {result.lean_mode})"


def format_execution(decision: ExecutionDecision) -> str:
    lines = [f"decision={decision.decision.value}", decision.explanation]
    for idx, step in enumerate(decision.trace, start=1):
        lines.append(f"{idx}. {step.action.kind.value}: {step.decision.value}")
        lines.append(f"   intent: {format_check_result(step.intent_result)}")
        if step.effect_result:
            lines.append(f"   effect: {format_check_result(step.effect_result)}")
    return "\n".join(lines)
