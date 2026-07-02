from __future__ import annotations

import json
import re

from proofalign.certificates import Certificate, CertificateBundle, CertificateKind, certificates_from_action_params
from proofalign.lean_bridge import LeanBridge
from proofalign.models import (
    Action,
    ActionKind,
    CheckResult,
    Decision,
    SafetySpec,
    TaskIntent,
    TraceSummary,
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
            return self._result(
                "intent",
                violations,
                "reject unsafe or unsupported instruction",
                Decision.REJECT,
                reports,
                _lean_intent_expression(intent, action, spec),
            )

        if action.kind in {ActionKind.STOP, ActionKind.REJECT}:
            return self._result(
                "intent",
                [],
                "explicit stop/reject action is always intent-compatible",
                Decision.ALLOW,
                reports,
                _lean_intent_expression(intent, action, spec),
            )

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

        return self._result(
            "intent",
            violations,
            "action is a legal symbolic refinement",
            Decision.REJECT,
            reports,
            _lean_intent_expression(intent, action, spec),
        )

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
        return self._result(
            "effect",
            violations,
            "observed effect matches symbolic action contract",
            decision,
            reports,
            _lean_effect_expression(before, action, after, spec),
        )

    def check_chunk_effect_alignment(
        self,
        before: WorldState,
        action: Action,
        after: WorldState,
        summary: TraceSummary,
        spec: SafetySpec,
        post_certificates: CertificateBundle | None = None,
        step: int | None = None,
    ) -> CheckResult:
        violations: list[str] = []
        reports: list[ViolationReport] = []
        certs = post_certificates or certificates_from_action_params(action.params, "effect")

        if summary.num_raw_steps <= 0:
            self._add_violation(violations, reports, ViolationType.POSTCONDITION, "chunk_effect", "chunk executed no raw env steps", Decision.REPLAN)
        if summary.collision or summary.cost_observed:
            reason = "collision was observed during chunk execution" if summary.collision else "LIBERO safety cost was observed during chunk execution"
            self._add_violation(violations, reports, ViolationType.COLLISION, "chunk_effect", reason, Decision.SAFE_STOP)
        if summary.min_human_hand_distance < spec.safety_margin:
            self._add_violation(
                violations,
                reports,
                ViolationType.CLEARANCE,
                "chunk_effect",
                f"chunk human hand distance {summary.min_human_hand_distance:.3f} below margin {spec.safety_margin:.3f}",
                Decision.REPLAN,
            )
        if summary.min_obstacle_distance < spec.safety_margin:
            self._add_violation(
                violations,
                reports,
                ViolationType.CLEARANCE,
                "chunk_effect",
                f"chunk obstacle distance {summary.min_obstacle_distance:.3f} below margin {spec.safety_margin:.3f}",
                Decision.REPLAN,
            )
        if summary.protected_object_moved:
            self._add_violation(
                violations,
                reports,
                ViolationType.FRAME_CONDITION,
                "chunk_effect",
                "protected object moved during chunk execution",
                Decision.SAFE_STOP,
            )

        action_target = action.object_id
        for moved in summary.moved_objects:
            if moved != action_target and _matches_any(moved, spec.forbidden_objects + spec.protected_objects):
                self._add_violation(
                    violations,
                    reports,
                    ViolationType.FRAME_CONDITION,
                    "chunk_effect",
                    f"frame condition failed: protected/forbidden object {moved} moved",
                    Decision.SAFE_STOP,
                    [moved],
                )

        if action.kind == ActionKind.PICK and action.object_id:
            obj = after.objects.get(action.object_id)
            if (
                not after.last_action_success
                or after.gripper_holding != action.object_id
                or not obj
                or obj.held_by != "gripper"
                or not summary.object_became_held
            ):
                self._add_violation(
                    violations,
                    reports,
                    ViolationType.POSTCONDITION,
                    "chunk_effect",
                    f"pick chunk postcondition failed: {action.object_id} did not become held by gripper",
                    Decision.REPLAN,
                    [action.object_id],
                )

        if action.kind == ActionKind.PLACE and action.object_id and action.region:
            obj = after.objects.get(action.object_id)
            region = after.regions.get(action.region)
            if not after.last_action_success or after.gripper_holding is not None or not summary.object_released:
                self._add_violation(violations, reports, ViolationType.POSTCONDITION, "chunk_effect", "place chunk postcondition failed: gripper did not release object", Decision.REPLAN, [action.object_id])
            if not obj or not region or not region.contains(obj.pose):
                self._add_violation(violations, reports, ViolationType.POSTCONDITION, "chunk_effect", f"place chunk postcondition failed: {action.object_id} is not in {action.region}", Decision.REPLAN, [action.object_id])

        if action.kind == ActionKind.MOVE_TO and action.region and spec.require_progress_to_region:
            obj_id = action.object_id
            region = after.regions.get(action.region)
            if obj_id and region and obj_id in before.objects and obj_id in after.objects:
                before_dist = before.objects[obj_id].pose.distance_to(region.center)
                after_dist = after.objects[obj_id].pose.distance_to(region.center)
                if after_dist >= before_dist:
                    self._add_violation(violations, reports, ViolationType.POSTCONDITION, "chunk_effect", f"move chunk postcondition failed: {obj_id} did not progress toward {action.region}", Decision.REPLAN, [obj_id])

        self._check_post_certificates(certs, action, spec, step, violations, reports)

        decision = Decision.SAFE_STOP if _summary_hazard(summary) or any(report.recoverability == Decision.SAFE_STOP for report in reports) else Decision.REPLAN
        return self._result(
            "chunk_effect",
            violations,
            "observed chunk effect matches symbolic action contract",
            decision,
            reports,
            _lean_chunk_effect_expression(before, action, after, summary, spec),
        )

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

    def check_certified_dual_chunk_alignment(
        self,
        intent: TaskIntent,
        before: WorldState,
        action: Action,
        after: WorldState,
        summary: TraceSummary,
        spec: SafetySpec,
        pre_certificates: CertificateBundle | None = None,
        post_certificates: CertificateBundle | None = None,
        step: int | None = None,
    ) -> CheckResult:
        pre_certs = pre_certificates or CertificateBundle.from_dicts(action.params.get("pre_certificates"))
        post_certs = post_certificates or CertificateBundle.from_dicts(action.params.get("post_certificates"))
        intent_result = self.check_intent_alignment(intent, before, action, spec, pre_certs, step)
        if not intent_result.passed:
            return CheckResult(
                passed=False,
                layer="dual_chunk",
                violations=intent_result.violations,
                explanation="Intent-action alignment failed before chunk execution.",
                suggested_decision=intent_result.suggested_decision,
                lean_mode=intent_result.lean_mode,
                violation_reports=intent_result.violation_reports,
            )
        effect_result = self.check_chunk_effect_alignment(before, action, after, summary, spec, post_certs, step)
        if not effect_result.passed:
            return CheckResult(
                passed=False,
                layer="dual_chunk",
                violations=effect_result.violations,
                explanation="Chunk action-effect alignment failed after execution.",
                suggested_decision=effect_result.suggested_decision,
                lean_mode=effect_result.lean_mode,
                violation_reports=effect_result.violation_reports,
            )
        return self._result(
            "dual_chunk",
            [],
            "Both certified chunk alignment layers passed.",
            Decision.REPLAN,
            [],
            _lean_certified_dual_chunk_expression(
                intent,
                before,
                action,
                after,
                summary,
                spec,
                pre_certs,
                post_certs,
            ),
        )

    def _result(
        self,
        layer: str,
        violations: list[str],
        ok: str,
        failure_decision: Decision,
        reports: list[ViolationReport] | None = None,
        lean_expression: str | None = None,
    ) -> CheckResult:
        lean_check = self.lean.check_boolean_claim(f"{layer}_alignment", lean_expression) if lean_expression else self.lean.check_project()
        passed = not violations and lean_check.passed
        if violations:
            explanation = "; ".join(violations)
        elif not lean_check.passed:
            explanation = "Lean project check failed; refusing to trust symbolic contract."
        else:
            explanation = ok
        return CheckResult(
            passed=passed,
            layer=layer,
            violations=violations if violations else ([] if lean_check.passed else [_lean_error(lean_check)]),
            explanation=explanation,
            suggested_decision=Decision.ALLOW if passed else failure_decision,
            lean_mode=lean_check.mode,
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


def _lean_error(check: object) -> str:
    stderr = getattr(check, "stderr", "") or ""
    stdout = getattr(check, "stdout", "") or ""
    return (stderr or stdout or "Lean check failed").strip()


def _lean_intent_expression(intent: TaskIntent, action: Action, spec: SafetySpec) -> str:
    return f"ProofAlign.IntentAligned ({_lean_intent(intent)}) ({_lean_intent_action(intent, action)}) ({_lean_spec(spec)})"


def _lean_effect_expression(before: WorldState, action: Action, after: WorldState, spec: SafetySpec) -> str:
    return f"ProofAlign.EffectAligned ({_lean_world(before)}) ({_lean_action(action)}) ({_lean_world(after)}) ({_lean_spec(spec)})"


def _lean_chunk_effect_expression(
    before: WorldState,
    action: Action,
    after: WorldState,
    summary: TraceSummary,
    spec: SafetySpec,
) -> str:
    return (
        "ProofAlign.ChunkEffectAligned "
        f"({_lean_world(before)}) "
        f"({_lean_action(action)}) "
        f"({_lean_world(after)}) "
        f"({_lean_trace_summary(summary)}) "
        f"({_lean_spec(spec)})"
    )


def _lean_certified_dual_chunk_expression(
    intent: TaskIntent,
    before: WorldState,
    action: Action,
    after: WorldState,
    summary: TraceSummary,
    spec: SafetySpec,
    pre_certs: CertificateBundle,
    post_certs: CertificateBundle,
) -> str:
    return (
        "ProofAlign.CertifiedDualChunkAligned "
        f"({_lean_intent(intent)}) "
        f"({_lean_world(before)}) "
        f"({_lean_intent_action(intent, action)}) "
        f"({_lean_world(after)}) "
        f"({_lean_trace_summary(summary)}) "
        f"({_lean_spec(spec)}) "
        f"({_lean_certificate_list(pre_certs.certificates)}) "
        f"({_lean_certificate_list(post_certs.certificates)}) "
        f"{_lean_nat(spec.certificate_min_confidence)}"
    )


def _lean_intent(intent: TaskIntent) -> str:
    return (
        "{ "
        f"verb := {_lean_string(intent.verb)}, "
        f"targetObject := {_lean_option_string(intent.target_object)}, "
        f"targetPart := {_lean_option_string(intent.target_part)}, "
        f"targetRegion := {_lean_option_string(intent.target_region)}, "
        f"avoidObjects := {_lean_string_list(intent.avoid_objects)}, "
        f"rejectRequired := {_lean_bool(intent.reject_required)} "
        "}"
    )


def _lean_action(action: Action) -> str:
    obj = action.object_id or ""
    return _lean_action_with_object(action, obj)


def _lean_intent_action(intent: TaskIntent, action: Action) -> str:
    obj = action.object_id or ""
    if intent.target_object and _same_symbol(obj, intent.target_object):
        obj = intent.target_object
    region = action.region
    if intent.target_region and region and _same_symbol(region, intent.target_region):
        region = intent.target_region
    return _lean_action_with_object(action, obj, region)


def _lean_action_with_object(action: Action, obj: str, region: str | None = None) -> str:
    if action.kind == ActionKind.PICK:
        return f"ProofAlign.Action.pick {_lean_string(obj)} {_lean_string(action.part or '')}"
    if action.kind == ActionKind.PLACE:
        return f"ProofAlign.Action.place {_lean_string(obj)} {_lean_string(region or action.region or '')}"
    if action.kind == ActionKind.MOVE_TO:
        return f"ProofAlign.Action.moveTo {_lean_string(obj)} {_lean_string(region or action.region or '')}"
    if action.kind == ActionKind.AVOID:
        return f"ProofAlign.Action.avoid {_lean_string(action.avoid_object or obj)}"
    if action.kind == ActionKind.REJECT:
        return "ProofAlign.Action.reject"
    return "ProofAlign.Action.stop"


def _lean_spec(spec: SafetySpec) -> str:
    return (
        "{ "
        f"safetyMargin := {_lean_nat(spec.safety_margin)}, "
        f"forbiddenObjects := {_lean_string_list(spec.forbidden_objects)}, "
        f"forbiddenParts := {_lean_string_list(spec.forbidden_parts)}, "
        f"protectedObjects := {_lean_string_list(spec.protected_objects)}, "
        f"requireNoCollision := {_lean_bool(spec.require_no_collision)} "
        "}"
    )


def _lean_world(state: WorldState) -> str:
    in_region = []
    for obj in state.objects.values():
        for region in state.regions.values():
            if region.contains(obj.pose):
                in_region.append((obj.object_id, region.region_id))
    return (
        "{ "
        f"holding := {_lean_option_string(state.gripper_holding)}, "
        f"inRegion := {_lean_pair_list(in_region)}, "
        f"collision := {_lean_bool(state.collision)}, "
        f"humanHandDistance := {_lean_nat(state.min_distance_to_human_hand)}, "
        f"obstacleDistance := {_lean_nat(state.min_distance_to_obstacle)} "
        "}"
    )


def _lean_trace_summary(summary: TraceSummary) -> str:
    return (
        "{ "
        f"numSteps := {max(0, int(summary.num_raw_steps))}, "
        f"collision := {_lean_bool(summary.collision)}, "
        f"cost := {_lean_bool(summary.cost_observed)}, "
        f"minHumanHandDistance := {_lean_nat(summary.min_human_hand_distance)}, "
        f"minObstacleDistance := {_lean_nat(summary.min_obstacle_distance)}, "
        f"movedObjects := {_lean_string_list(summary.moved_objects)}, "
        f"protectedObjectMoved := {_lean_bool(summary.protected_object_moved)}, "
        f"objectBecameHeld := {_lean_bool(summary.object_became_held)}, "
        f"objectReleased := {_lean_bool(summary.object_released)} "
        "}"
    )


def _lean_certificate_list(certs: list[Certificate]) -> str:
    return "[" + ", ".join(_lean_certificate(cert) for cert in certs) + "]"


def _lean_certificate(cert: Certificate) -> str:
    value = cert.value if isinstance(cert.value, (int, float)) else 1.0
    threshold = cert.threshold if cert.threshold is not None else 0.0
    return (
        "{ "
        f"kind := {_lean_cert_kind(cert.kind)}, "
        f"status := {_lean_cert_status(cert.status.value)}, "
        f"subject := {_lean_option_string(cert.subject)}, "
        f"target := {_lean_option_string(cert.target)}, "
        f"value := {_lean_nat(float(value))}, "
        f"threshold := {_lean_nat(float(threshold))}, "
        f"confidence := {_lean_nat(cert.confidence)} "
        "}"
    )


def _lean_cert_kind(kind: CertificateKind) -> str:
    mapping = {
        CertificateKind.OBJECT_IDENTITY: "ProofAlign.CertKind.objectIdentity",
        CertificateKind.AFFORDANCE: "ProofAlign.CertKind.affordance",
        CertificateKind.COLLISION_FREE: "ProofAlign.CertKind.collisionFree",
        CertificateKind.HUMAN_CLEARANCE: "ProofAlign.CertKind.humanClearance",
        CertificateKind.OBSTACLE_CLEARANCE: "ProofAlign.CertKind.obstacleClearance",
        CertificateKind.REGION_OCCUPANCY: "ProofAlign.CertKind.regionOccupancy",
        CertificateKind.STATE_TRANSITION: "ProofAlign.CertKind.stateTransition",
        CertificateKind.FRAME_CONDITION: "ProofAlign.CertKind.frameCondition",
    }
    return mapping[kind]


def _lean_cert_status(status: str) -> str:
    mapping = {
        "valid": "ProofAlign.CertStatus.valid",
        "invalid": "ProofAlign.CertStatus.invalid",
        "missing": "ProofAlign.CertStatus.missing",
        "expired": "ProofAlign.CertStatus.expired",
        "low_confidence": "ProofAlign.CertStatus.lowConfidence",
        "unknown": "ProofAlign.CertStatus.unknown",
    }
    return mapping.get(status, "ProofAlign.CertStatus.unknown")


def _lean_string(value: str) -> str:
    return json.dumps(value)


def _lean_option_string(value: str | None) -> str:
    return f"some {_lean_string(value)}" if value is not None else "none"


def _lean_string_list(values: list[str]) -> str:
    return "[" + ", ".join(_lean_string(value) for value in values) + "]"


def _lean_pair_list(values: list[tuple[str, str]]) -> str:
    return "[" + ", ".join(f"({_lean_string(left)}, {_lean_string(right)})" for left, right in values) + "]"


def _lean_bool(value: bool) -> str:
    return "true" if value else "false"


def _lean_nat(value: float) -> str:
    if value >= 999:
        return "100000"
    return str(max(0, int(round(value * 100))))


def _summary_hazard(summary: TraceSummary) -> bool:
    return summary.collision or summary.cost_observed or summary.protected_object_moved
