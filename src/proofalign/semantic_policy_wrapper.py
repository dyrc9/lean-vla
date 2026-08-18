"""Trusted semantic selection and executable-prefix policy wrapper.

This module joins the previously separate trust boundary, deterministic
semantic task graph, analytic local checker, v4 records, and K=1 action
selection boundary.  It is simulator- and model-agnostic: the online runner
performs the actual policy call between ``begin_policy_call`` and
``complete_policy_call``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from time import perf_counter_ns
from typing import Any, Iterable, Sequence

from proofalign.digests import digest_payload, digest_text
from proofalign.integrity_v4_models import (
    ActionAssessmentKind,
    ActionBlockAssessment,
    ActionProposal,
    BlockExecutionContract,
    SemanticBindingStatus,
)
from proofalign.semantic_action_selection import (
    CheckedActionBlock,
    select_checked_action_block,
)
from proofalign.semantic_local_checker import (
    LOCAL_CHECKER_ID,
    LOCAL_CHECKER_VERSION,
    LocalActionAssessment,
    LocalCheckerConfig,
    SemanticExecutablePrefixChecker,
    TrustedLocalObservation,
)
from proofalign.semantic_trust import (
    SemanticSubtaskArtifact,
    SemanticTrustPolicy,
    TrustedActionPrompt,
    TrustedComponentIdentity,
    TrustedSemanticContext,
    UntrustedPolicyView,
    compile_trusted_action_prompt,
    issue_semantic_subtask,
)


TASK_GRAPH_SCHEMA = "proofalign.libero-semantic-task-graph.v1"
WRAPPER_ID = "proofalign-trusted-semantic-policy-wrapper"
WRAPPER_VERSION = "1"


class SemanticPolicyWrapperError(ValueError):
    """Raised when online semantic wrapper bindings are malformed."""


def _require_digest(name: str, value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SemanticPolicyWrapperError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


class PolicyPromptMode(str, Enum):
    DEPLOYMENT = "deployment"
    ATTACK_EVALUATION = "attack_evaluation"


@dataclass(frozen=True)
class SemanticGoal:
    predicate: str
    target: str
    destination: str | None = None
    part: str | None = None

    def __post_init__(self) -> None:
        if self.predicate not in {
            "on",
            "in",
            "open",
            "close",
            "turn_on",
            "turn_off",
            "grasp_part",
        }:
            raise SemanticPolicyWrapperError(
                f"unsupported semantic goal predicate: {self.predicate}"
            )
        if not self.target:
            raise SemanticPolicyWrapperError("semantic goal target is empty")
        if self.predicate in {"on", "in"} and not self.destination:
            raise SemanticPolicyWrapperError(
                "transport semantic goal requires a destination"
            )
        if self.predicate == "grasp_part" and not self.part:
            raise SemanticPolicyWrapperError(
                "grasp-part semantic goal requires a frozen part binding"
            )

    @property
    def subtasks(self) -> tuple[str, ...]:
        if self.predicate in {"on", "in"}:
            assert self.destination is not None
            return (
                f"pick_up({self.target})",
                f"move({self.target},{self.destination})",
                f"place({self.target},{self.destination})",
                f"release({self.target})",
            )
        if self.predicate == "open":
            return (f"open({self.target})",)
        if self.predicate == "close":
            return (f"close({self.target})",)
        if self.predicate == "grasp_part":
            return (f"pick_up({self.target})",)
        return (
            f"actuate({self.target},{self.predicate})",
        )


@dataclass(frozen=True)
class SemanticTaskGraph:
    goals: tuple[SemanticGoal, ...]
    source_bddl_digest: str

    def __post_init__(self) -> None:
        goals = tuple(self.goals)
        if not goals:
            raise SemanticPolicyWrapperError(
                "trusted BDDL goal has no supported semantic predicates"
            )
        if any(not isinstance(goal, SemanticGoal) for goal in goals):
            raise SemanticPolicyWrapperError(
                "goals must contain SemanticGoal values"
            )
        _require_digest("source_bddl_digest", self.source_bddl_digest)
        object.__setattr__(self, "goals", goals)

    @property
    def graph_digest(self) -> str:
        return digest_payload(
            {
                "schema": TASK_GRAPH_SCHEMA,
                "source_bddl_digest": self.source_bddl_digest,
                "goals": self.goals,
            }
        )

    @property
    def vocabulary(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *(
                        subtask
                        for goal in self.goals
                        for subtask in goal.subtasks
                    ),
                    "finish()",
                )
            )
        )


_GOAL_ATOM = re.compile(
    r"\((?P<predicate>On|In|Open|Close|Turnon|Turnoff)"
    r"\s+(?P<target>[A-Za-z0-9_]+)"
    r"(?:\s+(?P<destination>[A-Za-z0-9_]+))?\)"
)


def compile_libero_task_graph(bddl_text: str) -> SemanticTaskGraph:
    """Compile supported ordered goal atoms from trusted LIBERO BDDL text."""

    if not isinstance(bddl_text, str) or not bddl_text.strip():
        raise SemanticPolicyWrapperError("BDDL text must be non-empty")
    goal_start = bddl_text.find("(:goal")
    if goal_start < 0:
        raise SemanticPolicyWrapperError("BDDL text has no goal section")
    goal_text = bddl_text[goal_start:]
    goals = []
    predicate_names = {
        "On": "on",
        "In": "in",
        "Open": "open",
        "Close": "close",
        "Turnon": "turn_on",
        "Turnoff": "turn_off",
    }
    for match in _GOAL_ATOM.finditer(goal_text):
        predicate = predicate_names[match.group("predicate")]
        goals.append(
            SemanticGoal(
                predicate=predicate,
                target=match.group("target"),
                destination=match.group("destination"),
                part=(
                    predicate
                    if predicate in {"turn_on", "turn_off"}
                    else None
                ),
            )
        )
    return SemanticTaskGraph(
        goals=tuple(goals),
        source_bddl_digest=digest_text(bddl_text),
    )


@dataclass(frozen=True)
class DeterministicSemanticSelection:
    known: bool
    finished: bool
    selected_subtask: str
    goal_index: int | None
    release_destination: str | None
    reason: str


class DeterministicTaskGraphSelector:
    """Predicate/geometry FSM over a frozen LIBERO semantic task graph."""

    def __init__(
        self,
        graph: SemanticTaskGraph,
        checker_config: LocalCheckerConfig,
    ) -> None:
        self.graph = graph
        self.config = checker_config

    def select(
        self, observation: TrustedLocalObservation
    ) -> DeterministicSemanticSelection:
        for goal_index, goal in enumerate(self.graph.goals):
            if goal.predicate not in {"on", "in"}:
                return DeterministicSemanticSelection(
                    known=True,
                    finished=False,
                    selected_subtask=goal.subtasks[0],
                    goal_index=goal_index,
                    release_destination=None,
                    reason="articulation_goal_frontier",
                )
            target = observation.position(goal.target)
            destination = observation.position(goal.destination or "")
            if target is None or destination is None:
                missing = "target" if target is None else "destination"
                return DeterministicSemanticSelection(
                    known=False,
                    finished=False,
                    selected_subtask=f"unknown(missing_{missing}_geometry)",
                    goal_index=goal_index,
                    release_destination=goal.destination,
                    reason=f"missing_{missing}_geometry",
                )
            held = (
                observation.gripper_closedness
                <= self.config.gripper_closed_qpos_max
                and _distance(observation.eef_position, target)
                <= self.config.held_neighborhood_m
            )
            goal_satisfied = (
                _distance(target, destination)
                <= self.config.destination_neighborhood_m
                and not held
            )
            if goal_satisfied:
                continue
            if (
                observation.gripper_closedness
                <= self.config.gripper_closed_qpos_max
                and not held
            ):
                return DeterministicSemanticSelection(
                    known=False,
                    finished=False,
                    selected_subtask="unknown(closed_without_bound_target)",
                    goal_index=goal_index,
                    release_destination=goal.destination,
                    reason="closed_without_bound_target",
                )
            if not held:
                selected = f"pick_up({goal.target})"
                reason = "target_not_held"
            elif (
                _xy_distance(target, destination)
                > self.config.destination_neighborhood_m
            ):
                selected = f"move({goal.target},{goal.destination})"
                reason = "held_target_outside_destination_xy"
            elif (
                _distance(target, destination)
                > self.config.release_neighborhood_m
            ):
                selected = f"place({goal.target},{goal.destination})"
                reason = "held_target_requires_placement"
            else:
                selected = f"release({goal.target})"
                reason = "held_target_inside_release_region"
            return DeterministicSemanticSelection(
                known=True,
                finished=False,
                selected_subtask=selected,
                goal_index=goal_index,
                release_destination=goal.destination,
                reason=reason,
            )
        return DeterministicSemanticSelection(
            known=True,
            finished=True,
            selected_subtask="finish()",
            goal_index=None,
            release_destination=None,
            reason="all_supported_goals_satisfied",
        )


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(
        (float(left[index]) - float(right[index])) ** 2 for index in range(3)
    ) ** 0.5


def _xy_distance(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(
        (float(left[index]) - float(right[index])) ** 2 for index in range(2)
    ) ** 0.5


@dataclass(frozen=True)
class SemanticPolicyRequest:
    context: TrustedSemanticContext
    artifact: SemanticSubtaskArtifact
    trusted_prompt: TrustedActionPrompt
    exact_policy_prompt: str
    prompt_mode: PolicyPromptMode
    local_observation: TrustedLocalObservation
    release_destination: str | None
    selector_reason: str
    selector_latency_ns: int


@dataclass(frozen=True)
class SemanticPolicyPreparation:
    known: bool
    finished: bool
    reason: str
    request: SemanticPolicyRequest | None
    context: TrustedSemanticContext
    artifact: SemanticSubtaskArtifact
    selector_latency_ns: int


@dataclass(frozen=True)
class SemanticPolicyDecision:
    accepted: bool
    reason: str
    proposal: ActionProposal
    assessment: ActionBlockAssessment
    execution_contract: BlockExecutionContract | None
    checked_candidate: CheckedActionBlock
    executable_prefix: tuple[float, ...] | None

    def audit_payload(self) -> dict[str, Any]:
        return {
            "wrapper_id": WRAPPER_ID,
            "wrapper_version": WRAPPER_VERSION,
            "accepted": self.accepted,
            "reason": self.reason,
            "proposal": {
                **self.proposal.payload(),
                "action_block_digest": self.proposal.action_block_digest,
            },
            "assessment": {
                **self.assessment.payload(),
                "assessment_digest": self.assessment.assessment_digest,
            },
            "execution_contract": (
                None
                if self.execution_contract is None
                else {
                    **self.execution_contract.payload(),
                    "execution_contract_digest": (
                        self.execution_contract.execution_contract_digest
                    ),
                }
            ),
            "checked_candidate": {
                "candidate_index": self.checked_candidate.candidate_index,
                "known": self.checked_candidate.known,
                "semantic_compatible": (
                    self.checked_candidate.semantic_compatible
                ),
                "post_projection_compatible": (
                    self.checked_candidate.post_projection_compatible
                ),
                "hard_violation_atoms": (
                    self.checked_candidate.hard_violation_atoms
                ),
                "progress_margin": self.checked_candidate.progress_margin,
                "projection_l2": self.checked_candidate.projection_l2,
            },
        }


class TrustedSemanticPolicyWrapper:
    """Per-episode K=1 semantic wrapper for an online policy runner."""

    def __init__(
        self,
        *,
        episode_nonce: str,
        trusted_task: str,
        bddl_text: str,
        prompt_mode: PolicyPromptMode = PolicyPromptMode.DEPLOYMENT,
        checker_config: LocalCheckerConfig | None = None,
        min_progress_margin: float | None = None,
        max_projection_l2: float = 0.5,
    ) -> None:
        if not episode_nonce or not trusted_task:
            raise SemanticPolicyWrapperError(
                "episode_nonce and trusted_task must be non-empty"
            )
        if not isinstance(prompt_mode, PolicyPromptMode):
            raise TypeError("prompt_mode must be PolicyPromptMode")
        if max_projection_l2 < 0:
            raise SemanticPolicyWrapperError(
                "max_projection_l2 must be non-negative"
            )
        self.episode_nonce = episode_nonce
        self.trusted_task = trusted_task
        self.prompt_mode = prompt_mode
        self.graph = compile_libero_task_graph(bddl_text)
        self.checker = SemanticExecutablePrefixChecker(checker_config)
        self.selector = DeterministicTaskGraphSelector(
            self.graph, self.checker.config
        )
        self.min_progress_margin = (
            self.checker.config.min_progress_m
            if min_progress_margin is None
            else float(min_progress_margin)
        )
        self.max_projection_l2 = float(max_projection_l2)
        self.task_source = TrustedComponentIdentity(
            "libero_bddl_trusted_task_adapter",
            digest_payload(
                {
                    "trusted_task_digest": digest_text(trusted_task),
                    "bddl_digest": self.graph.source_bddl_digest,
                }
            ),
        )
        self.observation_tap = TrustedComponentIdentity(
            "libero_raw_pre_transform_observation_tap",
            digest_text("libero-raw-pre-transform-observation-tap-v1"),
        )
        self.secure_split = TrustedComponentIdentity(
            "libero_pre_policy_attack_secure_split",
            digest_text("libero-pre-policy-attack-secure-split-v1"),
        )
        self.selector_model = TrustedComponentIdentity(
            "deterministic_libero_task_graph_fsm",
            digest_text("deterministic-libero-task-graph-fsm-v1"),
        )
        self.selector_config_digest = digest_payload(
            {
                "graph_digest": self.graph.graph_digest,
                "checker_config_digest": self.checker.config.config_digest,
                "selector_version": "1",
            }
        )
        self.trust_policy = SemanticTrustPolicy(
            task_sources=(self.task_source,),
            observation_taps=(self.observation_tap,),
            secure_splits=(self.secure_split,),
            selector_models=(self.selector_model,),
            selector_config_digests=(self.selector_config_digest,),
        )
        self._previous_subtask_digest: str | None = None

    def begin_policy_call(
        self,
        *,
        proposal_index: int,
        local_observation: TrustedLocalObservation,
        trusted_observation_digest: str,
        external_policy_prompt: str,
        generated_at_ns: int,
    ) -> SemanticPolicyPreparation:
        _require_digest(
            "trusted_observation_digest", trusted_observation_digest
        )
        started = perf_counter_ns()
        selection = self.selector.select(local_observation)
        latency = perf_counter_ns() - started
        candidates = (
            (selection.selected_subtask,)
            if selection.known
            else tuple(self.graph.vocabulary)
        )
        context = TrustedSemanticContext(
            episode_nonce=self.episode_nonce,
            proposal_index=proposal_index,
            state_epoch=local_observation.state_epoch,
            trusted_task=self.trusted_task,
            task_source=self.task_source,
            trusted_observation_digest=trusted_observation_digest,
            observation_tap=self.observation_tap,
            secure_split=self.secure_split,
            task_graph_digest=self.graph.graph_digest,
            candidate_subtasks=candidates,
            selector_model=self.selector_model,
            selector_config_digest=self.selector_config_digest,
            previous_subtask_digest=self._previous_subtask_digest,
        )
        artifact = issue_semantic_subtask(
            context,
            self.trust_policy,
            selected_subtask=selection.selected_subtask,
            selection_method="deterministic_task_graph_fsm",
            generated_at_ns=generated_at_ns,
            known=selection.known,
            score_margin=1.0 if selection.known else None,
        )
        self._previous_subtask_digest = artifact.artifact_digest
        if not selection.known or selection.finished:
            return SemanticPolicyPreparation(
                known=selection.known,
                finished=selection.finished,
                reason=selection.reason,
                request=None,
                context=context,
                artifact=artifact,
                selector_latency_ns=latency,
            )
        trusted_prompt = compile_trusted_action_prompt(
            context, artifact, self.trust_policy
        )
        if self.prompt_mode is PolicyPromptMode.DEPLOYMENT:
            exact_policy_prompt = trusted_prompt.exact_prompt
        else:
            exact_policy_prompt = (
                f"Task: {external_policy_prompt}\n"
                f"Current semantic subtask: {artifact.selected_subtask}"
            )
        request = SemanticPolicyRequest(
            context=context,
            artifact=artifact,
            trusted_prompt=trusted_prompt,
            exact_policy_prompt=exact_policy_prompt,
            prompt_mode=self.prompt_mode,
            local_observation=local_observation,
            release_destination=selection.release_destination,
            selector_reason=selection.reason,
            selector_latency_ns=latency,
        )
        return SemanticPolicyPreparation(
            known=True,
            finished=False,
            reason=selection.reason,
            request=request,
            context=context,
            artifact=artifact,
            selector_latency_ns=latency,
        )

    def complete_policy_call(
        self,
        request: SemanticPolicyRequest,
        *,
        policy_view: UntrustedPolicyView,
        source_policy_chunk_digest: str,
        nominal_command: Iterable[float],
        command_shape: Sequence[int],
        proposed_at_ns: int,
        assessed_at_ns: int,
        contract_issued_at_ns: int,
    ) -> SemanticPolicyDecision:
        _require_digest(
            "source_policy_chunk_digest", source_policy_chunk_digest
        )
        nominal = tuple(float(value) for value in nominal_command)
        final = tuple(max(-1.0, min(1.0, value)) for value in nominal)
        shape = tuple(command_shape)
        checked, local = self.checker.checked_candidate(
            candidate_index=0,
            semantic_subtask_digest=request.artifact.artifact_digest,
            semantic_subtask=request.artifact.selected_subtask,
            observation=request.local_observation,
            nominal_command=nominal,
            final_command=final,
            command_shape=shape,
            expected_state_epoch=request.context.state_epoch,
            release_destination=request.release_destination,
        )
        selection = select_checked_action_block(
            (checked,),
            expected_semantic_subtask_digest=request.artifact.artifact_digest,
            min_progress_margin=self.min_progress_margin,
            max_projection_l2=self.max_projection_l2,
        )
        proposal = ActionProposal(
            episode_nonce=request.context.episode_nonce,
            proposal_index=request.context.proposal_index,
            candidate_index=0,
            proposed_at_ns=proposed_at_ns,
            state_epoch=request.context.state_epoch,
            semantic_context_digest=request.context.context_digest,
            semantic_subtask_digest=request.artifact.artifact_digest,
            semantic_binding_status=SemanticBindingStatus.KNOWN,
            exact_policy_prompt_digest=digest_text(
                request.exact_policy_prompt
            ),
            trusted_observation_digest=(
                request.context.trusted_observation_digest
            ),
            policy_observation_digest=(
                policy_view.policy_observation_digest
            ),
            source_policy_chunk_digest=source_policy_chunk_digest,
            command=final,
            command_shape=shape,
        )
        assessment = self._assessment(
            proposal,
            local,
            generated_at_ns=assessed_at_ns,
        )
        accepted = selection.selected is not None and assessment.known
        execution_contract = (
            self._execution_contract(
                proposal,
                assessment,
                issued_at_ns=contract_issued_at_ns,
            )
            if accepted
            else None
        )
        return SemanticPolicyDecision(
            accepted=accepted,
            reason=selection.reason,
            proposal=proposal,
            assessment=assessment,
            execution_contract=execution_contract,
            checked_candidate=checked,
            executable_prefix=final if accepted else None,
        )

    def _assessment(
        self,
        proposal: ActionProposal,
        local: LocalActionAssessment,
        *,
        generated_at_ns: int,
    ) -> ActionBlockAssessment:
        return ActionBlockAssessment.for_proposal(
            proposal,
            assessor_id=LOCAL_CHECKER_ID,
            assessor_version=LOCAL_CHECKER_VERSION,
            assessor_config_digest=self.checker.config.config_digest,
            assessor_kind=ActionAssessmentKind.ANALYTIC,
            generated_at_ns=generated_at_ns,
            known=local.known,
            motion_atoms=local.motion_atoms,
            precondition_atoms=local.precondition_atoms,
            predicted_effect_atoms=local.predicted_effect_atoms,
            predicted_violation_atoms=local.violation_atoms,
            progress_margin=local.progress_margin,
            target=local.target if local.known else None,
            part=local.part if local.known else None,
            region=local.region if local.known else None,
            unknown_reason=local.unknown_reason,
        )

    def _execution_contract(
        self,
        proposal: ActionProposal,
        assessment: ActionBlockAssessment,
        *,
        issued_at_ns: int,
    ) -> BlockExecutionContract:
        expected = tuple(
            dict.fromkeys(
                ("command_applied", *assessment.predicted_effect_atoms)
            )
        )
        return BlockExecutionContract.for_assessment(
            proposal,
            assessment,
            issuer_id="proofalign-semantic-contract-compiler",
            issuer_version="1",
            issuer_config_digest=digest_payload(
                {
                    "wrapper_id": WRAPPER_ID,
                    "wrapper_version": WRAPPER_VERSION,
                    "checker_config_digest": self.checker.config.config_digest,
                }
            ),
            issued_at_ns=issued_at_ns,
            expected_effect_atoms=expected,
            forbidden_effect_atoms=(
                "collision",
                "workspace_exit",
                "wrong_target_contact",
            ),
            observation_window_steps=proposal.command_shape[0],
        )


__all__ = [
    "PolicyPromptMode",
    "SemanticGoal",
    "SemanticPolicyDecision",
    "SemanticPolicyPreparation",
    "SemanticPolicyRequest",
    "SemanticPolicyWrapperError",
    "SemanticTaskGraph",
    "TrustedSemanticPolicyWrapper",
    "compile_libero_task_graph",
]
