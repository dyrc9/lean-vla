from __future__ import annotations

import re

from proofalign.certificates import CertificateBundle, CertificateKind, certificates_from_action_params
from proofalign.lean_bridge import LeanBridge
from proofalign.models import (
    Action,
    ActionKind,
    CheckResult,
    Decision,
    SafetySpec,
    TaskIntent,
    WorldState,
)
from proofalign.violations import ViolationReport, ViolationType


class DualAlignmentChecker:
    """Runtime checker for symbolic dual alignment contracts."""

    def __init__(self, lean_bridge: LeanBridge | None = None) -> None:
        self.lean = lean_bridge or LeanBridge()

    def check_intent_alignment(
        self,
        intent: TaskIntent,
        state: WorldState,
        action: Action,
        spec: SafetySpec,
        pre_certificates: CertificateBundle | None = None,
        step: int | None = None,
    ) -> CheckResult:
        violations: list[str] = []
        reports: list[ViolationReport] = []
        certs = pre_certificates or certificates_from_action_params(action.params, "intent")

        if intent.reject_required:
            if action.kind != ActionKind.REJECT:
                self._add_violation(
                    violations,
                    reports,
                    ViolationType.INTENT_MISMATCH,
                    "intent",
                    intent.unsafe_reason or "task intent requires rejection",
                    Decision.REJECT,
                )
            return self._result("intent", violations, "reject unsafe or unsupported instruction", Decision.REJECT, reports)

        if action.kind in {ActionKind.STOP, ActionKind.REJECT}:
            return self._result("intent", [], "explicit stop/reject action is always intent-compatible", Decision.ALLOW, reports)

        if _matches_any(action.object_id, spec.forbidden_objects):
            self._add_violation(
                violations,
                reports,
                ViolationType.FORBIDDEN_OBJECT,
                "intent",
                f"action touches forbidden object {action.object_id}",
                Decision.REJECT,
                [action.object_id or ""],
            )
        if action.part in spec.forbidden_parts:
            self._add_violation(
                violations,
                reports,
                ViolationType.UNSAFE_AFFORDANCE,
                "intent",
                f"action touches forbidden part {action.part}",
                Decision.REJECT,
                [action.object_id or ""],
            )

        if _matches_any(action.object_id, intent.avoid_objects) or _matches_any(action.avoid_object, intent.avoid_objects):
            self._add_violation(
                violations,
                reports,
                ViolationType.INTENT_MISMATCH,
                "intent",
                f"action conflicts with avoid target {action.object_id or action.avoid_object}",
                Decision.REJECT,
                [action.object_id or action.avoid_object or ""],
            )

        obj = state.objects.get(action.object_id or "")
        part = obj.part(action.part) if obj else None
        if spec.reject_dangerous and part and (part.dangerous or not part.safe_to_grasp):
            self._add_violation(
                violations,
                reports,
                ViolationType.UNSAFE_AFFORDANCE,
                "intent",
                f"part {action.part} of {action.object_id} is not a safe grasp/contact part",
                Decision.REJECT,
                [action.object_id or ""],
            )
        if obj and obj.handheld_by_human:
            self._add_violation(
                violations,
                reports,
                ViolationType.PRECONDITION,
                "intent",
                f"object {obj.object_id} is currently hand-held by a human",
                Decision.REJECT,
                [obj.object_id],
            )

        self._check_pre_certificates(certs, action, spec, step, violations, reports)

        if intent.verb == "pick":
            if action.kind not in {ActionKind.PICK, ActionKind.MOVE_TO}:
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"pick intent cannot be refined by {action.kind.value}", Decision.REJECT)
            if not _same_symbol(action.object_id, intent.target_object):
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"expected object {intent.target_object}, got {action.object_id}", Decision.REJECT, [action.object_id or ""])
            if action.kind == ActionKind.PICK and intent.target_part and action.part != intent.target_part:
                self._add_violation(violations, reports, ViolationType.UNSAFE_AFFORDANCE, "intent", f"expected part {intent.target_part}, got {action.part}", Decision.REJECT, [action.object_id or ""])
        elif intent.verb == "place":
            if action.kind not in {ActionKind.PLACE, ActionKind.PICK, ActionKind.MOVE_TO}:
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"place intent cannot be refined by {action.kind.value}", Decision.REJECT)
            if not _same_symbol(action.object_id, intent.target_object):
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"expected object {intent.target_object}, got {action.object_id}", Decision.REJECT, [action.object_id or ""])
            if action.kind == ActionKind.PLACE and action.region != intent.target_region:
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"expected region {intent.target_region}, got {action.region}", Decision.REJECT, [action.object_id or ""])
        elif intent.verb == "move":
            if action.kind not in {ActionKind.MOVE_TO, ActionKind.PLACE}:
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"move intent cannot be refined by {action.kind.value}", Decision.REJECT)
            if not _same_symbol(action.object_id, intent.target_object):
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"expected object {intent.target_object}, got {action.object_id}", Decision.REJECT, [action.object_id or ""])
            if action.region and action.region != intent.target_region:
                self._add_violation(violations, reports, ViolationType.INTENT_MISMATCH, "intent", f"expected target {intent.target_region}, got {action.region}", Decision.REJECT, [action.object_id or ""])
        else:
            self._add_violation(violations, reports, ViolationType.UNKNOWN_INTENT, "intent", "unknown intent cannot be aligned", Decision.REJECT)

        return self._result("intent", violations, "action is a legal symbolic refinement", Decision.REJECT, reports)

    def check_effect_alignment(
        self,
        before: WorldState,
        action: Action,
        after: WorldState,
        spec: SafetySpec,
        post_certificates: CertificateBundle | None = None,
        step: int | None = None,
    ) -> CheckResult:
        violations: list[str] = []
        reports: list[ViolationReport] = []
        certs = post_certificates or certificates_from_action_params(action.params, "effect")

        if spec.require_no_collision and after.collision:
            self._add_violation(violations, reports, ViolationType.COLLISION, "effect", "collision was observed during execution", Decision.SAFE_STOP)
        if after.min_distance_to_human_hand < spec.safety_margin:
            self._add_violation(
                violations,
                reports,
                ViolationType.CLEARANCE,
                "effect",
                f"human hand distance {after.min_distance_to_human_hand:.3f} below margin {spec.safety_margin:.3f}",
                Decision.REPLAN,
            )
        if after.min_distance_to_obstacle < spec.safety_margin:
            self._add_violation(
                violations,
                reports,
                ViolationType.CLEARANCE,
                "effect",
                f"obstacle distance {after.min_distance_to_obstacle:.3f} below margin {spec.safety_margin:.3f}",
                Decision.REPLAN,
            )

        if action.kind == ActionKind.PICK and action.object_id:
            obj = after.objects.get(action.object_id)
            if not after.last_action_success or after.gripper_holding != action.object_id or not obj or obj.held_by != "gripper":
                self._add_violation(violations, reports, ViolationType.POSTCONDITION, "effect", f"pick postcondition failed: {action.object_id} is not held by gripper", Decision.REPLAN, [action.object_id])

        if action.kind == ActionKind.PLACE and action.object_id and action.region:
            obj = after.objects.get(action.object_id)
            region = after.regions.get(action.region)
            if not after.last_action_success or after.gripper_holding is not None:
                self._add_violation(violations, reports, ViolationType.POSTCONDITION, "effect", "place postcondition failed: gripper did not release object", Decision.REPLAN, [action.object_id])
            if not obj or not region or not region.contains(obj.pose):
                self._add_violation(violations, reports, ViolationType.POSTCONDITION, "effect", f"place postcondition failed: {action.object_id} is not in {action.region}", Decision.REPLAN, [action.object_id])

        if action.kind == ActionKind.MOVE_TO and action.region and spec.require_progress_to_region:
            obj_id = action.object_id
            region = after.regions.get(action.region)
            if obj_id and region and obj_id in before.objects and obj_id in after.objects:
                before_dist = before.objects[obj_id].pose.distance_to(region.center)
                after_dist = after.objects[obj_id].pose.distance_to(region.center)
                if after_dist >= before_dist:
                    self._add_violation(violations, reports, ViolationType.POSTCONDITION, "effect", f"move postcondition failed: {obj_id} did not progress toward {action.region}", Decision.REPLAN, [obj_id])

        self._check_post_certificates(certs, action, spec, step, violations, reports)

        decision = Decision.SAFE_STOP if any("collision" in v for v in violations) else Decision.REPLAN
        return self._result("effect", violations, "observed effect matches symbolic action contract", decision, reports)

    def check_dual_alignment(
        self,
        intent: TaskIntent,
        before: WorldState,
        action: Action,
        after: WorldState,
        spec: SafetySpec,
    ) -> CheckResult:
        intent_result = self.check_intent_alignment(intent, before, action, spec)
        if not intent_result.passed:
            return CheckResult(
                passed=False,
                layer="dual",
                violations=intent_result.violations,
                explanation="Intent-action alignment failed before execution.",
                suggested_decision=intent_result.suggested_decision,
                lean_mode=intent_result.lean_mode,
                violation_reports=intent_result.violation_reports,
            )
        effect_result = self.check_effect_alignment(before, action, after, spec)
        if not effect_result.passed:
            return CheckResult(
                passed=False,
                layer="dual",
                violations=effect_result.violations,
                explanation="Action-effect alignment failed after execution.",
                suggested_decision=effect_result.suggested_decision,
                lean_mode=effect_result.lean_mode,
                violation_reports=effect_result.violation_reports,
            )
        return CheckResult(True, "dual", [], "Both alignment layers passed.", Decision.ALLOW, effect_result.lean_mode)

    def _result(
        self,
        layer: str,
        violations: list[str],
        ok: str,
        failure_decision: Decision,
        reports: list[ViolationReport] | None = None,
    ) -> CheckResult:
        lean_project = self.lean.check_project()
        passed = not violations and lean_project.passed
        if violations:
            explanation = "; ".join(violations)
        elif not lean_project.passed:
            explanation = "Lean project check failed; refusing to trust symbolic contract."
        else:
            explanation = ok
        return CheckResult(
            passed=passed,
            layer=layer,
            violations=violations if violations else ([] if lean_project.passed else [lean_project.stderr.strip()]),
            explanation=explanation,
            suggested_decision=Decision.ALLOW if passed else failure_decision,
            lean_mode=lean_project.mode,
            violation_reports=reports or [],
        )

    def _check_pre_certificates(
        self,
        certs: CertificateBundle,
        action: Action,
        spec: SafetySpec,
        step: int | None,
        violations: list[str],
        reports: list[ViolationReport],
    ) -> None:
        required: list[CertificateKind] = []
        if action.object_id:
            required.append(CertificateKind.OBJECT_IDENTITY)
        if action.kind == ActionKind.PICK and action.part:
            required.append(CertificateKind.AFFORDANCE)
        if action.kind in {ActionKind.PLACE, ActionKind.MOVE_TO}:
            required.extend([CertificateKind.COLLISION_FREE, CertificateKind.HUMAN_CLEARANCE])
        for kind in required:
            errors = certs.errors_for(
                kind,
                spec.certificate_min_confidence,
                subject=action.object_id if kind in {CertificateKind.OBJECT_IDENTITY, CertificateKind.AFFORDANCE} else None,
                now_step=step,
                missing_is_error=spec.require_certificates,
            )
            for error in errors:
                self._add_violation(violations, reports, ViolationType.CERTIFICATE, "intent", error, Decision.REJECT)

    def _check_post_certificates(
        self,
        certs: CertificateBundle,
        action: Action,
        spec: SafetySpec,
        step: int | None,
        violations: list[str],
        reports: list[ViolationReport],
    ) -> None:
        required = [CertificateKind.STATE_TRANSITION]
        if action.kind in {ActionKind.PLACE, ActionKind.MOVE_TO, ActionKind.PICK}:
            required.append(CertificateKind.FRAME_CONDITION)
        for kind in required:
            errors = certs.errors_for(
                kind,
                spec.certificate_min_confidence,
                subject=action.object_id if action.object_id else None,
                now_step=step,
                missing_is_error=spec.require_certificates,
            )
            for error in errors:
                self._add_violation(violations, reports, ViolationType.CERTIFICATE, "effect", error, Decision.REPLAN)

    def _add_violation(
        self,
        violations: list[str],
        reports: list[ViolationReport],
        violation_type: ViolationType,
        layer: str,
        message: str,
        decision: Decision,
        object_refs: list[str] | None = None,
    ) -> None:
        clean_refs = [ref for ref in object_refs or [] if ref]
        violations.append(message)
        reports.append(
            ViolationReport(
                violation_type=violation_type,
                layer=layer,
                message=message,
                object_refs=clean_refs,
                recoverability=decision,
            )
        )


def _matches_any(value: str | None, candidates: list[str]) -> bool:
    return any(_same_symbol(value, candidate) for candidate in candidates)


def _same_symbol(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    return _symbol_key(left) == _symbol_key(right)


def _symbol_key(value: str) -> str:
    key = re.sub(r"__?\d+", "", value.lower())
    key = key.replace("_", "")
    return re.sub(r"[^a-z0-9]", "", key)
