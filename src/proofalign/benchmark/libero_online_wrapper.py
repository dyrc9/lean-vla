from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
import re
from time import monotonic_ns, perf_counter
from typing import Any, Iterable, Protocol

from proofalign.action_abstraction import action_from_dict
from proofalign.benchmark.libero_safety_adapter import _parts_for_kind
from proofalign.certificates import CertificateBundle
from proofalign.checker import DualAlignmentChecker
from proofalign.ctda import (
    MonitorCheckResult,
    MonitorVerdict,
    StaticCheckResult,
    StaticVerdict,
    digest_payload,
)
from proofalign.ctda_runtime import CTDARuntimeSession, PreparedPrefix
from proofalign.intent_parser import parse_intent
from proofalign.models import (
    Action,
    CheckResult,
    Decision,
    ExecutionDecision,
    ExecutionStep,
    GripperContactPartObservation,
    GripperContactPartQuery,
    Object,
    Pose,
    Region,
    SafetySpec,
    TaskIntent,
    TraceSummary,
    WorldState,
)
from proofalign.violations import ViolationType


class LiberoOnlineIntegrationError(RuntimeError):
    """Raised when a real LIBERO/VLA value cannot be safely abstracted."""


_CTDA_UNKNOWN_OBSERVATION_PREFIX = "ctda_unknown_observation:"


class LiberoActionAbstractor(Protocol):
    def abstract(
        self,
        raw_action: Any,
        *,
        instruction: str,
        observation: Any,
        state: WorldState,
        spec: SafetySpec,
        history: list[ExecutionStep],
    ) -> Action:
        """Convert a VLA action chunk into a ProofAlign symbolic action."""


class VLAActionProvider(Protocol):
    def __call__(self, instruction: str, observation: Any, history: list[ExecutionStep]) -> Any:
        """Return one raw action chunk for the current observation."""


@dataclass
class LiberoStepResult:
    observation: Any
    reward: float
    done: bool
    info: dict[str, Any]
    decision: Decision
    step: ExecutionStep


@dataclass
class DefaultLiberoActionAbstractor:
    """Default explicit adapter for already-symbolic VLA action metadata.

    Continuous actions are intentionally not guessed. A real VLA integration
    should pass either a ProofAlign-shaped action dictionary or provide a
    domain-specific abstractor that maps low-level chunks to symbolic contracts.
    """

    symbolic_key: str = "proofalign_action"

    def abstract(
        self,
        raw_action: Any,
        *,
        instruction: str,
        observation: Any,
        state: WorldState,
        spec: SafetySpec,
        history: list[ExecutionStep],
    ) -> Action:
        del instruction, observation, state, spec, history
        if isinstance(raw_action, dict):
            if self.symbolic_key in raw_action:
                return action_from_dict(dict(raw_action[self.symbolic_key]))
            if "candidate_actions" in raw_action:
                actions = raw_action["candidate_actions"]
                if not actions:
                    raise LiberoOnlineIntegrationError("candidate_actions is empty")
                return action_from_dict(dict(actions[0]))
            if "type" in raw_action or "kind" in raw_action:
                return action_from_dict(dict(raw_action))
        raise LiberoOnlineIntegrationError(
            "Raw VLA action is continuous or unrecognized; provide a LiberoActionAbstractor "
            "that emits Pick/Place/MoveTo/Stop/Reject contracts."
        )


@dataclass
class LiberoStateObserver:
    """Extract ProofAlign symbolic state from a LIBERO-Safety robosuite env."""

    default_safety_distance: float = 999.0
    region_radius: float = 0.08
    contact_part_queries: tuple[GripperContactPartQuery, ...] = ()

    def __post_init__(self) -> None:
        self.contact_part_queries = tuple(
            GripperContactPartQuery(item.object_id, item.geom_ids)
            for item in self.contact_part_queries
        )

    def observe(self, env: Any, observation: Any | None = None, info: dict[str, Any] | None = None) -> WorldState:
        info = info or {}
        raw_env = unwrap_libero_env(env)
        sim = getattr(raw_env, "sim", getattr(env, "sim", None))
        objects = self._objects(raw_env, sim)
        regions = self._regions(raw_env, sim)
        gripper_holding = next((obj.object_id for obj in objects.values() if obj.held_by == "gripper"), None)
        robot_pose = self._robot_pose(raw_env, sim, observation)
        human_distance, human_observed = self._distance(
            info, raw_env, "human_hand", robot_pose, objects
        )
        obstacle_distance, obstacle_observed = self._distance(
            info, raw_env, "obstacle", robot_pose, objects
        )
        collision, collision_observed = self._collision(info, raw_env)
        cost_observed = self._cost_observed(info, raw_env)
        contact_parts, missing_contact_parts = self._contact_part_observations(raw_env, sim)
        notes = ["state observed from LIBERO-Safety robosuite/MuJoCo backend"]
        for name, observed in (
            ("min_distance_to_human_hand", human_observed),
            ("min_distance_to_obstacle", obstacle_observed),
            ("collision", collision_observed),
            ("cost", cost_observed),
        ):
            if not observed:
                notes.append(f"{_CTDA_UNKNOWN_OBSERVATION_PREFIX}{name}")
        notes.extend(
            f"{_CTDA_UNKNOWN_OBSERVATION_PREFIX}{query.atom}"
            for query in missing_contact_parts
        )
        return WorldState(
            objects=objects,
            regions=regions,
            gripper_holding=gripper_holding,
            robot_pose=robot_pose,
            # Keep the legacy numeric defaults for non-CTDA callers. CTDA checks
            # the provenance notes above and fails closed instead of treating a
            # default value as an observation.
            min_distance_to_human_hand=human_distance,
            min_distance_to_obstacle=obstacle_distance,
            collision=collision,
            last_action_success=bool(info.get("last_action_success", True)),
            gripper_contact_parts=contact_parts,
            notes=notes,
        )

    def _objects(self, raw_env: Any, sim: Any) -> dict[str, Object]:
        source: dict[str, Any] = {}
        source.update(getattr(raw_env, "objects_dict", {}) or {})
        source.update(getattr(raw_env, "fixtures_dict", {}) or {})
        if not source:
            for name in getattr(raw_env, "obj_of_interest", []) or []:
                source[str(name)] = None

        objects: dict[str, Object] = {}
        for name, model in source.items():
            object_id = str(name)
            kind = str(
                getattr(model, "category_name", None)
                or getattr(model, "name", None)
                or object_id
            )
            held_by = "gripper" if self._is_gripper_holding(raw_env, object_id, model) else None
            objects[object_id] = Object(
                object_id=object_id,
                kind=kind,
                pose=self._object_pose(raw_env, sim, object_id, model),
                parts={part["name"]: _part_from_dict(part) for part in _parts_for_kind(kind)},
                held_by=held_by,
                handheld_by_human=_looks_like_human_hand(object_id, kind),
            )
        return objects

    def _regions(self, raw_env: Any, sim: Any) -> dict[str, Region]:
        regions: dict[str, Region] = {}
        sites = getattr(raw_env, "object_sites_dict", {}) or {}
        for name, site in sites.items():
            pose = self._site_pose(sim, name, site)
            regions[str(name)] = Region(str(name), pose, self.region_radius)
        return regions

    def _object_pose(self, raw_env: Any, sim: Any, object_id: str, model: Any) -> Pose:
        body_id = (getattr(raw_env, "obj_body_id", {}) or {}).get(object_id)
        if body_id is None and model is not None:
            root_body = getattr(model, "root_body", None)
            body_name2id = getattr(getattr(sim, "model", None), "body_name2id", None)
            if root_body is not None and callable(body_name2id):
                try:
                    body_id = body_name2id(root_body)
                except Exception:
                    body_id = None
        if body_id is not None:
            body_xpos = getattr(getattr(sim, "data", None), "body_xpos", None)
            try:
                return _pose_from_xyz(body_xpos[body_id])
            except Exception:
                pass
        return Pose(0.0, 0.0, 0.0)

    def _site_pose(self, sim: Any, name: str, site: Any) -> Pose:
        site_id = getattr(site, "site_id", None)
        if site_id is None:
            site_name2id = getattr(getattr(sim, "model", None), "site_name2id", None)
            if callable(site_name2id):
                for candidate in (name, getattr(site, "name", None)):
                    if candidate is None:
                        continue
                    try:
                        site_id = site_name2id(candidate)
                        break
                    except Exception:
                        continue
        if site_id is not None:
            site_xpos = getattr(getattr(sim, "data", None), "site_xpos", None)
            try:
                return _pose_from_xyz(site_xpos[site_id])
            except Exception:
                pass
        return Pose(0.0, 0.0, 0.0)

    def _robot_pose(self, raw_env: Any, sim: Any, observation: Any | None) -> Pose:
        if isinstance(observation, dict) and "robot0_eef_pos" in observation:
            return _pose_from_xyz(observation["robot0_eef_pos"])
        robots = getattr(raw_env, "robots", None) or []
        if robots:
            eef_site_id = getattr(robots[0], "eef_site_id", None)
            if eef_site_id is not None:
                site_xpos = getattr(getattr(sim, "data", None), "site_xpos", None)
                try:
                    return _pose_from_xyz(site_xpos[eef_site_id])
                except Exception:
                    pass
        return Pose(0.0, 0.0, 0.0)

    def _is_gripper_holding(self, raw_env: Any, object_id: str, model: Any) -> bool:
        if getattr(raw_env, "held_object", None) == object_id:
            return True
        check = getattr(raw_env, "check_gripper_contact", None)
        if not callable(check):
            return False
        for candidate in (model, getattr(model, "contact_geoms", None), object_id):
            if candidate is None:
                continue
            try:
                if bool(check(candidate)):
                    return True
            except Exception:
                continue
        return False

    def _contact_part_observations(
        self,
        raw_env: Any,
        sim: Any,
    ) -> tuple[list[GripperContactPartObservation], list[GripperContactPartQuery]]:
        """Independently mirror LIBERO's two-finger contact-part predicate.

        This reads MuJoCo contacts and the benchmark-owned object/gripper geom
        registries.  It does not call ``check_success`` or the predicate helper.
        """

        if not self.contact_part_queries:
            return [], []
        source: dict[str, Any] = {}
        source.update(getattr(raw_env, "objects_dict", {}) or {})
        source.update(getattr(raw_env, "fixtures_dict", {}) or {})
        model = getattr(sim, "model", None)
        data = getattr(sim, "data", None)
        geom_id2name = getattr(model, "geom_id2name", None)
        robots = getattr(raw_env, "robots", None) or []
        try:
            important_geoms = robots[0].gripper._important_geoms
            left_geoms = _flatten_geom_names(important_geoms["left_fingerpad"])
            right_geoms = _flatten_geom_names(important_geoms["right_fingerpad"])
            contacts = tuple(data.contact[index] for index in range(int(data.ncon)))
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return [], list(self.contact_part_queries)
        if not callable(geom_id2name) or not left_geoms or not right_geoms:
            return [], list(self.contact_part_queries)

        observations: list[GripperContactPartObservation] = []
        missing: list[GripperContactPartQuery] = []
        for query in self.contact_part_queries:
            object_model = source.get(query.object_id)
            contact_geoms = getattr(object_model, "contact_geoms", None)
            if not isinstance(contact_geoms, (list, tuple)):
                missing.append(query)
                continue
            selected_geoms = {
                str(name)
                for name in contact_geoms
                if isinstance(name, str)
                and _trailing_geom_id(name) in set(query.geom_ids)
            }
            if not selected_geoms:
                missing.append(query)
                continue
            left_matches: set[str] = set()
            right_matches: set[str] = set()
            try:
                for contact in contacts:
                    first = _libero_contact_name(geom_id2name(contact.geom1))
                    second = _libero_contact_name(geom_id2name(contact.geom2))
                    left_matches.update(
                        _contacted_object_geoms(first, second, left_geoms, selected_geoms)
                    )
                    right_matches.update(
                        _contacted_object_geoms(first, second, right_geoms, selected_geoms)
                    )
            except (AttributeError, IndexError, TypeError, ValueError):
                missing.append(query)
                continue
            observations.append(
                GripperContactPartObservation(
                    object_id=query.object_id,
                    geom_ids=query.geom_ids,
                    left_contact=bool(left_matches),
                    right_contact=bool(right_matches),
                    left_object_geoms=tuple(left_matches),
                    right_object_geoms=tuple(right_matches),
                )
            )
        return observations, missing

    def _distance(
        self,
        info: dict[str, Any],
        raw_env: Any,
        target: str,
        robot_pose: Pose,
        objects: dict[str, Object],
    ) -> tuple[float, bool]:
        keys = (
            f"min_distance_to_{target}",
            f"{target}_distance",
            f"min_{target}_distance",
        )
        for key in keys:
            if key in info:
                try:
                    value = float(info[key])
                except (TypeError, ValueError):
                    continue
                if isfinite(value):
                    return value, True
        for key in keys:
            if not hasattr(raw_env, key):
                continue
            try:
                value = float(getattr(raw_env, key))
            except (TypeError, ValueError):
                continue
            if isfinite(value):
                return value, True
        candidates = [
            obj.pose.distance_to(robot_pose)
            for obj in objects.values()
            if target in obj.object_id.lower() or target in obj.kind.lower()
        ]
        return (min(candidates), True) if candidates else (self.default_safety_distance, False)

    def _collision(self, info: dict[str, Any], raw_env: Any) -> tuple[bool, bool]:
        if "collision" in info:
            return bool(info["collision"]), True
        cost = info.get("cost")
        if isinstance(cost, dict):
            return any(bool(value) for value in cost.values()), True
        if cost is not None:
            return bool(cost), True
        if hasattr(raw_env, "collision"):
            return bool(getattr(raw_env, "collision")), True
        raw_cost = getattr(raw_env, "cost", None)
        if isinstance(raw_cost, dict):
            return any(bool(value) for value in raw_cost.values()), True
        if raw_cost is not None:
            return bool(raw_cost), True
        constraint_cost = self._constraint_cost(raw_env)
        if constraint_cost is not None:
            return any(bool(value) for value in constraint_cost.values()), True
        return False, False

    def _cost_observed(self, info: dict[str, Any], raw_env: Any) -> bool:
        if "cost" in info and info["cost"] is not None:
            return True
        if hasattr(raw_env, "cost") and getattr(raw_env, "cost") is not None:
            return True
        return self._constraint_cost(raw_env) is not None

    def _constraint_cost(self, raw_env: Any) -> dict[str, Any] | None:
        checker = getattr(raw_env, "_check_constraint", None)
        if not callable(checker):
            return None
        try:
            value = checker(False)
        except Exception:
            return None
        return dict(value) if isinstance(value, dict) else None


@dataclass
class ProofAlignLiberoWrapper:
    """Online ProofAlign gate around a LIBERO-Safety env."""

    env: Any
    instruction: str
    spec: SafetySpec
    checker: DualAlignmentChecker = field(default_factory=DualAlignmentChecker)
    state_observer: LiberoStateObserver = field(default_factory=LiberoStateObserver)
    action_abstractor: LiberoActionAbstractor = field(default_factory=DefaultLiberoActionAbstractor)
    max_chunk_steps: int = 8
    object_move_epsilon: float = 0.01
    progress_epsilon: float = 1e-4
    no_progress_patience: int = 3
    gripper_close_threshold: float = 0.2
    gripper_open_threshold: float = -0.2
    stop_on_replan: bool = True
    ctda_session: CTDARuntimeSession | None = None

    def __post_init__(self) -> None:
        self.intent: TaskIntent = parse_intent(self.instruction)
        self.current_observation: Any | None = None
        self.current_state: WorldState | None = None
        self.trace: list[ExecutionStep] = []

    def reset(self, *args: Any, **kwargs: Any) -> Any:
        observation = self.env.reset(*args, **kwargs)
        self.current_observation = observation
        self.current_state = self.state_observer.observe(self.env, observation)
        self.trace = []
        if self.ctda_session is not None:
            self.ctda_session.reset()
        return observation

    def step(self, raw_action: Any) -> LiberoStepResult:
        if self.ctda_session is not None:
            return self.step_chunk(raw_action, max_chunk_steps=1)
        total_start = perf_counter()
        policy_call_id, proposed_action_chunk, policy_metadata = _policy_action_audit(
            raw_action, default_call_id=f"policy:{len(self.trace):06d}"
        )
        if self.current_state is None:
            self.current_state = self.state_observer.observe(self.env, self.current_observation)
        before = self.current_state.clone()
        abstract_start = perf_counter()
        symbolic_action = self.action_abstractor.abstract(
            raw_action,
            instruction=self.instruction,
            observation=self.current_observation,
            state=before,
            spec=self.spec,
            history=self.trace,
        )
        abstract_time = perf_counter() - abstract_start
        pre_certs = CertificateBundle.from_dicts(symbolic_action.params.get("pre_certificates"))
        intent_start = perf_counter()
        intent_result = self.checker.check_intent_alignment(
            self.intent,
            before,
            symbolic_action,
            self.spec,
            pre_certs,
            len(self.trace),
        )
        intent_time = perf_counter() - intent_start
        if not intent_result.passed:
            step = ExecutionStep(
                symbolic_action,
                intent_result,
                None,
                intent_result.suggested_decision,
                before,
                pre_certificates=pre_certs.to_dicts(),
                raw_action=env_action_from_raw(raw_action),
                proofalign_action=action_to_dict(symbolic_action),
                env_info={},
                reward=0.0,
                done=True,
                runtime_seconds={
                    "action_abstractor": abstract_time,
                    "intent_check": intent_time,
                    "effect_check": 0.0,
                    "env_step": 0.0,
                    "wrapper_step_wall": perf_counter() - total_start,
                },
                policy_call_id=policy_call_id,
                policy_metadata=policy_metadata,
                proposed_action_chunk=proposed_action_chunk,
                discarded_action_chunk_tail=proposed_action_chunk,
            )
            self.trace.append(step)
            return LiberoStepResult(
                self.current_observation,
                0.0,
                True,
                self._info(intent_result.suggested_decision, intent_result),
                intent_result.suggested_decision,
                step,
            )

        env_action = env_action_from_raw(raw_action)
        env_start = perf_counter()
        observation, reward, done, info = normalize_env_step(self.env.step(env_action))
        env_time = perf_counter() - env_start
        self.current_observation = observation
        info = dict(info)
        after = self.state_observer.observe(self.env, observation, info)
        post_certs = CertificateBundle.from_dicts(symbolic_action.params.get("post_certificates"))
        effect_start = perf_counter()
        effect_result = self.checker.check_effect_alignment(
            before,
            symbolic_action,
            after,
            self.spec,
            post_certs,
            len(self.trace),
        )
        effect_time = perf_counter() - effect_start
        decision = effect_result.suggested_decision
        done = bool(done or decision in {Decision.REJECT, Decision.SAFE_STOP})
        info.update(self._info(decision, effect_result))
        step = ExecutionStep(
            symbolic_action,
            intent_result,
            effect_result,
            decision,
            before,
            after,
            pre_certificates=pre_certs.to_dicts(),
            post_certificates=post_certs.to_dicts(),
            raw_action=env_action,
            proofalign_action=action_to_dict(symbolic_action),
            env_info=dict(info),
            reward=float(reward),
            done=done,
            runtime_seconds={
                "action_abstractor": abstract_time,
                "intent_check": intent_time,
                "effect_check": effect_time,
                "env_step": env_time,
                "wrapper_step_wall": perf_counter() - total_start,
            },
            policy_call_id=policy_call_id,
            policy_metadata=policy_metadata,
            proposed_action_chunk=proposed_action_chunk,
            executed_policy_actions=[_frozen_action_copy(env_action)],
            discarded_action_chunk_tail=proposed_action_chunk[1:],
        )
        self.trace.append(step)
        self.current_observation = observation
        self.current_state = after
        return LiberoStepResult(observation, float(reward), done, info, decision, step)

    def step_chunk(
        self,
        raw_action: Any,
        *,
        max_chunk_steps: int | None = None,
        chunk_id: str | None = None,
    ) -> LiberoStepResult:
        total_start = perf_counter()
        requested_max_steps = max_chunk_steps or self.max_chunk_steps
        policy_call_id, proposed_action_chunk, policy_metadata = _policy_action_audit(
            raw_action, default_call_id=f"policy:{len(self.trace):06d}"
        )
        # Until incremental observation/authorization is available, one CTDA
        # authorization covers exactly one raw command. This prevents a failed
        # first observation from being followed by more commands in the chunk.
        max_steps = 1 if self.ctda_session is not None else requested_max_steps
        if self.current_state is None:
            self.current_state = self.state_observer.observe(self.env, self.current_observation)
        before = self.current_state.clone()

        abstract_start = perf_counter()
        if self.ctda_session is not None:
            # Paper CTDA never lets policy symbolic metadata select the contract.
            # This action is a compatibility/logging view of the frozen mission.
            symbolic_action = _ctda_mission_action(self.ctda_session)
        else:
            symbolic_action = self.action_abstractor.abstract(
                raw_action,
                instruction=self.instruction,
                observation=self.current_observation,
                state=before,
                spec=self.spec,
                history=self.trace,
            )
        abstract_time = perf_counter() - abstract_start

        env_actions = raw_actions_from_raw(raw_action, max_steps)
        pre_certs = CertificateBundle.from_dicts(symbolic_action.params.get("pre_certificates"))
        intent_start = perf_counter()
        if self.ctda_session is not None:
            intent_result = CheckResult(
                passed=True,
                layer="ctda_mission_root",
                explanation=(
                    "legacy policy-facing intent and proofalign_action are diagnostic only; "
                    "authorization is rooted in the frozen mission"
                ),
                lean_mode="ctda-python-reference",
            )
        else:
            intent_result = self.checker.check_intent_alignment(
                self.intent,
                before,
                symbolic_action,
                self.spec,
                pre_certs,
                len(self.trace),
            )
        intent_time = perf_counter() - intent_start
        if not intent_result.passed:
            step = ExecutionStep(
                symbolic_action,
                intent_result,
                None,
                intent_result.suggested_decision,
                before,
                pre_certificates=pre_certs.to_dicts(),
                raw_action=env_actions,
                proofalign_action=action_to_dict(symbolic_action),
                env_info={},
                reward=0.0,
                done=True,
                runtime_seconds={
                    "action_abstractor": abstract_time,
                    "intent_check": intent_time,
                    "effect_check": 0.0,
                    "env_step": 0.0,
                    "wrapper_step_wall": perf_counter() - total_start,
                },
                chunk_id=chunk_id or f"chunk_{len(self.trace)}",
                contract=action_to_dict(symbolic_action),
                raw_actions=[],
                policy_call_id=policy_call_id,
                policy_metadata=policy_metadata,
                proposed_action_chunk=proposed_action_chunk,
                discarded_action_chunk_tail=proposed_action_chunk,
                trace_summary=TraceSummary(num_raw_steps=0, boundary_reason="intent_reject"),
            )
            self.trace.append(step)
            return LiberoStepResult(
                self.current_observation,
                0.0,
                True,
                self._info(intent_result.suggested_decision, intent_result),
                intent_result.suggested_decision,
                step,
            )

        ctda_prepared: PreparedPrefix | None = None
        ctda_pre_time = 0.0
        ctda_dispatch_ns: int | None = None
        if self.ctda_session is not None:
            ctda_start = perf_counter()
            observation_issues = _ctda_observation_issues(before, self.spec)
            if observation_issues:
                static_result = StaticCheckResult.unknown(*observation_issues)
                prepared = None
            else:
                ctda_before = _ctda_state_for_spec(before, self.spec)
                prepared_result = self.ctda_session.prepare_prefix(
                    symbolic_action,
                    ctda_before,
                    tuple(env_actions[:1]),
                    self.spec,
                    now_ns=monotonic_ns(),
                )
                static_result = prepared_result.check
                prepared = prepared_result.prepared
            if prepared is not None and static_result.proven:
                ctda_dispatch_ns = monotonic_ns()
                static_result = _ctda_dispatch_check(prepared, ctda_dispatch_ns)
            ctda_pre_time = perf_counter() - ctda_start
            ctda_precheck = _ctda_static_check(
                static_result,
                self.ctda_session.evaluator_mode,
            )
            if prepared is None or not ctda_precheck.passed:
                ctda_metadata = _ctda_metadata(
                    self.ctda_session,
                    static_verdict=static_result.verdict.value,
                    witness_ref=static_result.witness_ref,
                    issues=static_result.issues,
                    dispatch_ns=ctda_dispatch_ns,
                )
                step = ExecutionStep(
                    symbolic_action,
                    intent_result,
                    ctda_precheck,
                    ctda_precheck.suggested_decision,
                    before,
                    pre_certificates=pre_certs.to_dicts(),
                    raw_action=env_actions,
                    proofalign_action=action_to_dict(symbolic_action),
                    env_info={},
                    reward=0.0,
                    done=True,
                    runtime_seconds={
                        "action_abstractor": abstract_time,
                        "intent_check": intent_time,
                        "ctda_prefix_pre": ctda_pre_time,
                        "ctda_monitor": 0.0,
                        "effect_check": 0.0,
                        "env_step": 0.0,
                        "wrapper_step_wall": perf_counter() - total_start,
                    },
                    chunk_id=chunk_id or f"chunk_{len(self.trace)}",
                    contract=action_to_dict(symbolic_action),
                    raw_actions=[],
                    policy_call_id=policy_call_id,
                    policy_metadata=policy_metadata,
                    proposed_action_chunk=proposed_action_chunk,
                    discarded_action_chunk_tail=proposed_action_chunk,
                    trace_summary=TraceSummary(num_raw_steps=0, boundary_reason="ctda_precheck"),
                    ctda=ctda_metadata,
                )
                self.trace.append(step)
                info = self._info(ctda_precheck.suggested_decision, ctda_precheck)
                info["proofalign_ctda"] = ctda_metadata
                return LiberoStepResult(
                    self.current_observation,
                    0.0,
                    True,
                    info,
                    ctda_precheck.suggested_decision,
                    step,
                )
            ctda_prepared = prepared

        summary = TraceSummary(
            min_human_hand_distance=before.min_distance_to_human_hand,
            min_obstacle_distance=before.min_distance_to_obstacle,
        )
        reward_total = 0.0
        done = False
        info: dict[str, Any] = {}
        observation = self.current_observation
        after = before
        env_time = 0.0
        executed_actions: list[Any] = []
        ctda_states_after: list[WorldState] = []
        previous = before
        no_progress_count = 0
        last_progress_distance = self._progress_distance(symbolic_action, before)

        dispatch_actions = (
            tuple(_frozen_action_copy(action) for action in ctda_prepared.authorized_actions)
            if ctda_prepared is not None
            else tuple(env_actions[:max_steps])
        )
        for index, env_action in enumerate(dispatch_actions):
            env_start = perf_counter()
            observation, reward, done_step, step_info = normalize_env_step(self.env.step(env_action))
            env_time += perf_counter() - env_start
            executed_actions.append(env_action)
            reward_total += float(reward)
            info = dict(step_info)
            after = self.state_observer.observe(self.env, observation, info)
            ctda_states_after.append(_ctda_state_for_spec(after, self.spec))
            self._update_trace_summary(summary, before, previous, after, info, symbolic_action)
            summary.num_raw_steps = index + 1
            done = bool(done or done_step)

            distance = self._progress_distance(symbolic_action, after)
            if distance is not None and last_progress_distance is not None:
                if distance >= last_progress_distance - self.progress_epsilon:
                    no_progress_count += 1
                else:
                    no_progress_count = 0
                last_progress_distance = distance

            boundary = self._chunk_boundary_reason(
                before,
                previous,
                after,
                symbolic_action,
                info,
                env_action,
                done,
                no_progress_count,
            )
            if boundary:
                summary.boundary_reason = boundary
                break
            previous = after
        else:
            summary.boundary_reason = "max_chunk_steps"

        # Capture the policy portion before a possible supervisor fallback is
        # appended to executed_actions.  The complete proposal remains audit
        # metadata and never changes the dispatch path.
        executed_policy_actions = [
            _frozen_action_copy(action) for action in executed_actions
        ]

        self.current_observation = observation
        post_certs = CertificateBundle.from_dicts(symbolic_action.params.get("post_certificates"))
        ctda_effect_result: CheckResult | None = None
        ctda_metadata: dict[str, Any] = {}
        ctda_monitor_time = 0.0
        ctda_monitor_verdict: MonitorVerdict | None = None
        ctda_observe_ns: int | None = None
        ctda_violation_at_ns: int | None = None
        if self.ctda_session is not None and ctda_prepared is not None:
            ctda_start = perf_counter()
            ctda_observe_ns = monotonic_ns()
            observation_issues = tuple(
                issue
                for state in ctda_states_after
                for issue in _ctda_observation_issues(state, self.spec)
            )
            if observation_issues:
                ctda_monitor_verdict = MonitorVerdict.UNKNOWN
                ctda_effect_result = CheckResult(
                    passed=False,
                    layer="ctda_monitor",
                    violations=list(dict.fromkeys(observation_issues)),
                    explanation="; ".join(dict.fromkeys(observation_issues)),
                    suggested_decision=Decision.REPLAN,
                    lean_mode="ctda-python-reference",
                )
                ctda_violation_at_ns = monotonic_ns()
                ctda_metadata = _ctda_metadata(
                    self.ctda_session,
                    static_verdict=StaticVerdict.PROVEN.value,
                    monitor_verdict=MonitorVerdict.UNKNOWN.value,
                    issues=tuple(ctda_effect_result.violations),
                    candidate_digest=ctda_prepared.candidate.candidate_digest,
                    contract_id=ctda_prepared.candidate.proposal.contract_id,
                    dispatch_ns=ctda_dispatch_ns,
                    observe_ns=ctda_observe_ns,
                    bounded_stutter=ctda_prepared.bounded_stutter,
                    bounded_stutter_count_before=(
                        ctda_prepared.bounded_stutter_count_before
                    ),
                    bounded_stutter_count_after=(
                        self.ctda_session.bounded_stutter_count
                    ),
                    bounded_stutter_translation_before_m=(
                        ctda_prepared.bounded_stutter_translation_before_m
                    ),
                    bounded_stutter_translation_after_m=(
                        ctda_prepared.bounded_stutter_translation_after_m
                    ),
                    bounded_stutter_motion_before=(
                        ctda_prepared.bounded_stutter_motion_before
                    ),
                    bounded_stutter_motion_after=(
                        ctda_prepared.bounded_stutter_motion_after
                    ),
                )
            else:
                try:
                    monitored, record = self.ctda_session.observe_prefix(
                        ctda_prepared,
                        tuple(ctda_states_after),
                        tuple(executed_actions),
                        self.spec,
                        dispatch_ns=ctda_dispatch_ns,
                        observation_times_ns=(ctda_observe_ns,),
                        now_ns=ctda_observe_ns,
                    )
                    ctda_monitor_verdict = monitored.verdict
                    ctda_effect_result = _ctda_monitor_check(
                        monitored,
                        self.ctda_session.evaluator_mode,
                    )
                    if not ctda_effect_result.passed:
                        ctda_violation_at_ns = monotonic_ns()
                    ctda_metadata = _ctda_metadata(
                        self.ctda_session,
                        static_verdict=StaticVerdict.PROVEN.value,
                        monitor_verdict=monitored.verdict.value,
                        witness_ref=monitored.witness_ref,
                        issues=monitored.issues,
                        record_digest=record.record_digest,
                        candidate_digest=record.candidate.candidate_digest,
                        contract_id=record.candidate.proposal.contract_id,
                        plant_trace_digest=record.plant_trace.plant_trace_digest,
                        event_trace_digest=record.event_trace.symbolic_event_trace_digest,
                        record_payload=asdict(record),
                        dispatch_ns=ctda_dispatch_ns,
                        observe_ns=ctda_observe_ns,
                        bounded_stutter=ctda_prepared.bounded_stutter,
                        bounded_stutter_count_before=(
                            ctda_prepared.bounded_stutter_count_before
                        ),
                        bounded_stutter_count_after=(
                            self.ctda_session.bounded_stutter_count
                        ),
                        bounded_stutter_translation_before_m=(
                            ctda_prepared.bounded_stutter_translation_before_m
                        ),
                        bounded_stutter_translation_after_m=(
                            ctda_prepared.bounded_stutter_translation_after_m
                        ),
                        bounded_stutter_motion_before=(
                            ctda_prepared.bounded_stutter_motion_before
                        ),
                        bounded_stutter_motion_after=(
                            ctda_prepared.bounded_stutter_motion_after
                        ),
                    )
                except Exception as exc:
                    ctda_violation_at_ns = monotonic_ns()
                    ctda_effect_result = CheckResult(
                        passed=False,
                        layer="ctda_monitor",
                        violations=[f"CTDA runtime evidence construction failed: {exc}"],
                        explanation=f"CTDA runtime evidence construction failed: {exc}",
                        suggested_decision=Decision.SAFE_STOP,
                        lean_mode="ctda-python-reference",
                    )
                    ctda_metadata = _ctda_metadata(
                        self.ctda_session,
                        static_verdict=StaticVerdict.PROVEN.value,
                        monitor_verdict=MonitorVerdict.INCONSISTENT.value,
                        issues=tuple(ctda_effect_result.violations),
                        candidate_digest=ctda_prepared.candidate.candidate_digest,
                        contract_id=ctda_prepared.candidate.proposal.contract_id,
                        dispatch_ns=ctda_dispatch_ns,
                        observe_ns=ctda_observe_ns,
                        bounded_stutter=ctda_prepared.bounded_stutter,
                        bounded_stutter_count_before=(
                            ctda_prepared.bounded_stutter_count_before
                        ),
                        bounded_stutter_count_after=(
                            self.ctda_session.bounded_stutter_count
                        ),
                        bounded_stutter_translation_before_m=(
                            ctda_prepared.bounded_stutter_translation_before_m
                        ),
                        bounded_stutter_translation_after_m=(
                            ctda_prepared.bounded_stutter_translation_after_m
                        ),
                        bounded_stutter_motion_before=(
                            ctda_prepared.bounded_stutter_motion_before
                        ),
                        bounded_stutter_motion_after=(
                            ctda_prepared.bounded_stutter_motion_after
                        ),
                    )
            if ctda_effect_result is not None and not ctda_effect_result.passed:
                try:
                    fallback_state_before = after
                    (
                        fallback_observation,
                        fallback_reward,
                        fallback_done,
                        fallback_info,
                        fallback_state,
                        fallback_receipt,
                        fallback_trace,
                        fallback_env_time,
                    ) = self._execute_ctda_fallback(
                        trigger=ctda_effect_result.explanation,
                        triggered_at_ns=ctda_violation_at_ns or monotonic_ns(),
                        state_before=fallback_state_before,
                    )
                    observation = fallback_observation
                    after = fallback_state
                    reward_total += fallback_reward
                    done = bool(done or fallback_done)
                    env_time += fallback_env_time
                    executed_actions.append(self.ctda_session.fallback_command())
                    info["proofalign_fallback_env_info"] = fallback_info
                    self._update_trace_summary(
                        summary,
                        before,
                        fallback_state_before,
                        fallback_state,
                        fallback_info,
                        symbolic_action,
                    )
                    summary.num_raw_steps += 1
                    summary.boundary_reason = (
                        f"{summary.boundary_reason}+ctda_fallback"
                        if summary.boundary_reason
                        else "ctda_fallback"
                    )
                    ctda_metadata["fallback_switch"] = _fallback_switch_metadata(
                        self.ctda_session, fallback_receipt
                    )
                    ctda_metadata["fallback_trace"] = fallback_trace
                    if not self.ctda_session.fallback_established_for_timing_policy(
                        fallback_receipt
                    ):
                        issue = "configured simulator fallback did not establish its immediate postcondition"
                        ctda_effect_result = CheckResult(
                            passed=False,
                            layer="ctda_fallback",
                            violations=list(ctda_effect_result.violations) + [issue],
                            explanation=f"{ctda_effect_result.explanation}; {issue}",
                            suggested_decision=Decision.SAFE_STOP,
                            lean_mode="ctda-python-reference",
                        )
                except Exception as exc:
                    ctda_effect_result = CheckResult(
                        passed=False,
                        layer="ctda_fallback",
                        violations=list(ctda_effect_result.violations)
                        + [f"configured fallback dispatch failed: {exc}"],
                        explanation=(
                            f"{ctda_effect_result.explanation}; "
                            f"configured fallback dispatch failed: {exc}"
                        ),
                        suggested_decision=Decision.SAFE_STOP,
                        lean_mode="ctda-python-reference",
                    )
                    ctda_metadata["fallback_error"] = str(exc)
            ctda_monitor_time = perf_counter() - ctda_start
        effect_start = perf_counter()
        legacy_effect_result = self.checker.check_chunk_effect_alignment(
            before,
            symbolic_action,
            after,
            summary,
            self.spec,
            post_certs,
            len(self.trace),
        )
        effect_time = perf_counter() - effect_start
        effect_result = _merge_effect_results(
            legacy_effect_result,
            ctda_effect_result,
            ctda_monitor_verdict,
        )
        decision = effect_result.suggested_decision
        done = bool(done or decision in {Decision.REJECT, Decision.SAFE_STOP})
        info.update(self._info(decision, effect_result))
        info["proofalign_chunk_summary"] = summary.to_dict()
        info["proofalign_chunk_boundary"] = summary.boundary_reason
        if ctda_metadata:
            info["proofalign_ctda"] = ctda_metadata
        step = ExecutionStep(
            symbolic_action,
            intent_result,
            effect_result,
            decision,
            before,
            after,
            pre_certificates=pre_certs.to_dicts(),
            post_certificates=post_certs.to_dicts(),
            raw_action=executed_actions,
            proofalign_action=action_to_dict(symbolic_action),
            env_info=dict(info),
            reward=float(reward_total),
            done=done,
            runtime_seconds={
                "action_abstractor": abstract_time,
                "intent_check": intent_time,
                "ctda_prefix_pre": ctda_pre_time,
                "ctda_monitor": ctda_monitor_time,
                "effect_check": effect_time,
                "env_step": env_time,
                "wrapper_step_wall": perf_counter() - total_start,
            },
            chunk_id=chunk_id or f"chunk_{len(self.trace)}",
            contract=action_to_dict(symbolic_action),
            raw_actions=list(executed_actions),
            policy_call_id=policy_call_id,
            policy_metadata=policy_metadata,
            proposed_action_chunk=proposed_action_chunk,
            executed_policy_actions=executed_policy_actions,
            discarded_action_chunk_tail=proposed_action_chunk[
                len(executed_policy_actions) :
            ],
            trace_summary=summary,
            ctda=ctda_metadata,
        )
        self.trace.append(step)
        self.current_observation = observation
        self.current_state = after
        return LiberoStepResult(observation, float(reward_total), done, info, decision, step)

    def run_episode(self, policy: VLAActionProvider, *, max_steps: int) -> ExecutionDecision:
        if self.current_observation is None:
            self.reset()
        final_decision = Decision.ALLOW
        explanation = "episode completed without ProofAlign violations"
        raw_steps_executed = 0
        while raw_steps_executed < max_steps:
            policy_start = perf_counter()
            raw_action = policy(self.instruction, self.current_observation, self.trace)
            policy_time = perf_counter() - policy_start
            remaining_steps = max_steps - raw_steps_executed
            result = self.step_chunk(raw_action, max_chunk_steps=min(self.max_chunk_steps, remaining_steps))
            result.step.runtime_seconds["policy"] = policy_time
            summary = result.step.trace_summary
            raw_steps_executed += summary.num_raw_steps if summary else 1
            final_decision = result.decision
            if result.decision != Decision.ALLOW:
                explanation = result.step.effect_result.explanation if result.step.effect_result else result.step.intent_result.explanation
            if result.decision in {Decision.REJECT, Decision.SAFE_STOP}:
                break
            if result.decision == Decision.REPLAN and self.stop_on_replan:
                break
            if result.done:
                break
        if (
            self.ctda_session is not None
            and self.ctda_session.supervisor.active_contract is not None
            and final_decision is Decision.ALLOW
        ):
            final_decision = Decision.REPLAN
            explanation = "episode ended with a pending CTDA contract obligation"
            try:
                fallback_state_before = (
                    self.current_state
                    or self.state_observer.observe(self.env, self.current_observation)
                )
                fallback_triggered_at_ns = monotonic_ns()
                (
                    observation,
                    fallback_reward,
                    fallback_done,
                    fallback_info,
                    fallback_state,
                    fallback_receipt,
                    fallback_trace,
                    fallback_env_time,
                ) = self._execute_ctda_fallback(
                    trigger=explanation,
                    triggered_at_ns=fallback_triggered_at_ns,
                    state_before=fallback_state_before,
                )
                self.current_observation = observation
                self.current_state = fallback_state
                if not self.ctda_session.fallback_established_for_timing_policy(
                    fallback_receipt
                ):
                    final_decision = Decision.SAFE_STOP
                    explanation += "; configured simulator fallback did not establish its immediate postcondition"
                if self.trace:
                    last_step = self.trace[-1]
                    last_step.ctda["fallback_switch"] = _fallback_switch_metadata(
                        self.ctda_session, fallback_receipt
                    )
                    last_step.ctda["fallback_trace"] = fallback_trace
                    last_step.env_info["proofalign_fallback_env_info"] = fallback_info
                    last_step.after = fallback_state
                    last_step.reward = float(last_step.reward or 0.0) + float(
                        fallback_reward
                    )
                    last_step.done = bool(
                        last_step.done
                        or fallback_done
                        or final_decision in {Decision.REJECT, Decision.SAFE_STOP}
                    )
                    last_step.runtime_seconds["env_step"] = float(
                        last_step.runtime_seconds.get("env_step", 0.0)
                    ) + fallback_env_time
                    fallback_command = self.ctda_session.fallback_command()
                    last_step.raw_actions.append(fallback_command)
                    if isinstance(last_step.raw_action, list):
                        last_step.raw_action.append(fallback_command)
                    fallback_result = CheckResult(
                        passed=False,
                        layer="ctda_fallback",
                        violations=[explanation],
                        explanation=explanation,
                        suggested_decision=final_decision,
                        lean_mode="ctda-python-reference",
                    )
                    last_step.effect_result = fallback_result
                    last_step.decision = final_decision
                    last_step.env_info.update(self._info(final_decision, fallback_result))
                    if last_step.trace_summary is not None:
                        last_summary = last_step.trace_summary
                        self._update_trace_summary(
                            last_summary,
                            last_step.before,
                            fallback_state_before,
                            fallback_state,
                            fallback_info,
                            last_step.action,
                        )
                        last_summary.num_raw_steps += 1
                        last_summary.boundary_reason = (
                            f"{last_summary.boundary_reason}+ctda_fallback"
                            if last_summary.boundary_reason
                            else "ctda_fallback"
                        )
                        last_step.env_info[
                            "proofalign_chunk_summary"
                        ] = last_summary.to_dict()
                        last_step.env_info[
                            "proofalign_chunk_boundary"
                        ] = last_summary.boundary_reason
            except Exception as exc:
                final_decision = Decision.SAFE_STOP
                explanation += f"; configured fallback dispatch failed: {exc}"
                if self.trace:
                    self.trace[-1].ctda["fallback_error"] = str(exc)
        final_state = self.current_state or self.state_observer.observe(self.env, self.current_observation)
        return ExecutionDecision(final_decision, final_state, list(self.trace), explanation)

    def _execute_ctda_fallback(
        self,
        *,
        trigger: str,
        triggered_at_ns: int,
        state_before: WorldState,
    ) -> tuple[Any, float, bool, dict[str, Any], WorldState, Any, dict[str, Any], float]:
        if self.ctda_session is None:
            raise RuntimeError("no CTDA session is configured")
        command = self.ctda_session.fallback_command()
        requested_at = monotonic_ns()
        dispatched_at = monotonic_ns()
        env_start = perf_counter()
        actuator_attestation = None
        state_after_observed: WorldState | None = None
        observation_error: str | None = None
        try:
            observation, reward, done, env_info = normalize_env_step(self.env.step(command))
            applied_at = monotonic_ns()
            try:
                actuator_attestation = self.ctda_session.attest_fallback_actuation(
                    command,
                    dispatched_at_ns=dispatched_at,
                    applied_at_ns=applied_at,
                )
            except Exception as exc:
                env_info = dict(env_info)
                env_info["fallback_actuator_evidence_error"] = str(exc)
            try:
                state_after_observed = self.state_observer.observe(
                    self.env, observation, env_info
                )
            except Exception as exc:
                observation_error = str(exc)
                env_info = dict(env_info)
                env_info["fallback_observation_exception"] = observation_error
                done = True
        except Exception as exc:
            observation_error = str(exc)
            observation = self.current_observation
            reward = 0.0
            done = True
            env_info = {"fallback_exception": str(exc)}
        observed_at = monotonic_ns()
        fallback_env_time = perf_counter() - env_start
        receipt = self.ctda_session.record_fallback_switch(
            trigger=trigger,
            state_before=state_before,
            state_after=state_after_observed,
            command=command,
            triggered_at_ns=triggered_at_ns,
            requested_at_ns=requested_at,
            dispatched_at_ns=dispatched_at,
            observed_at_ns=observed_at,
            safety_spec=self.spec,
            environment_info=env_info,
            observation_error=observation_error,
            actuator_attestation=actuator_attestation,
        )
        if state_after_observed is None:
            state_after = state_before.clone()
            state_after.notes.append(
                f"{_CTDA_UNKNOWN_OBSERVATION_PREFIX}fallback_post_state"
            )
        else:
            state_after = state_after_observed
        fallback_trace = {
            "kind": "ctda_fallback",
            "trigger": trigger,
            "requested_command": list(command),
            "command_application": receipt.command_application,
            "applied_command_digest": receipt.applied_command_digest,
            "triggered_at_ns": triggered_at_ns,
            "requested_at_ns": requested_at,
            "dispatched_at_ns": dispatched_at,
            "observed_at_ns": observed_at,
            "reward": float(reward),
            "done": bool(done),
            "env_info": dict(env_info),
            "state_before_digest": receipt.state_before_digest,
            "state_after_digest": receipt.state_after_digest,
            "state_after": (
                state_after_observed.to_dict()
                if state_after_observed is not None
                else None
            ),
            "observation_error": observation_error,
            "receipt": asdict(receipt),
        }
        return (
            observation,
            float(reward),
            bool(done),
            dict(env_info),
            state_after,
            receipt,
            fallback_trace,
            fallback_env_time,
        )

    def _update_trace_summary(
        self,
        summary: TraceSummary,
        before: WorldState,
        previous: WorldState,
        after: WorldState,
        info: dict[str, Any],
        action: Action,
    ) -> None:
        cost = _cost_dict(info)
        summary.cost.update(cost)
        summary.cost_observed = summary.cost_observed or _cost_observed(cost)
        summary.collision = summary.collision or after.collision or _collision_from_info(info)
        summary.min_human_hand_distance = min(summary.min_human_hand_distance, after.min_distance_to_human_hand)
        summary.min_obstacle_distance = min(summary.min_obstacle_distance, after.min_distance_to_obstacle)
        if previous.gripper_holding is None and after.gripper_holding is not None:
            summary.object_became_held = True
        if previous.gripper_holding is not None and after.gripper_holding is None:
            summary.object_released = True

        moved = _moved_objects(before, after, self.object_move_epsilon)
        if before.gripper_holding != after.gripper_holding:
            for obj_id in (before.gripper_holding, after.gripper_holding):
                if obj_id and obj_id not in moved:
                    moved.append(obj_id)
        for obj_id in moved:
            if obj_id not in summary.moved_objects:
                summary.moved_objects.append(obj_id)
            if obj_id != action.object_id and _matches_any_symbol(obj_id, self.spec.protected_objects):
                summary.protected_object_moved = True

    def _chunk_boundary_reason(
        self,
        before: WorldState,
        previous: WorldState,
        after: WorldState,
        action: Action,
        info: dict[str, Any],
        env_action: Any,
        done: bool,
        no_progress_count: int,
    ) -> str | None:
        if done:
            return "env_done"
        if _collision_from_info(info) or after.collision:
            return "collision"
        if _cost_observed(_cost_dict(info)):
            return "cost"
        gripper = _last_scalar(env_action)
        if gripper is not None:
            if previous.gripper_holding is None and gripper >= self.gripper_close_threshold:
                return "gripper_close"
            if previous.gripper_holding is not None and gripper <= self.gripper_open_threshold:
                return "gripper_open"
        if previous.gripper_holding is None and after.gripper_holding is not None:
            return "object_became_held"
        if previous.gripper_holding is not None and after.gripper_holding is None:
            return "object_released"
        if action.object_id and action.region and _object_in_region(after, action.object_id, action.region):
            before_in_region = _object_in_region(before, action.object_id, action.region)
            if not before_in_region:
                return "target_region_reached"
        if no_progress_count >= self.no_progress_patience:
            return "no_progress"
        return None

    def _progress_distance(self, action: Action, state: WorldState) -> float | None:
        if action.object_id and action.region and action.object_id in state.objects and action.region in state.regions:
            return state.objects[action.object_id].pose.distance_to(state.regions[action.region].center)
        return None

    def _info(self, decision: Decision, result: CheckResult) -> dict[str, Any]:
        return {
            "proofalign_decision": decision.value,
            "proofalign_layer": result.layer,
            "proofalign_explanation": result.explanation,
            "proofalign_violations": list(result.violations),
        }


def _ctda_static_check(
    result: StaticCheckResult,
    evaluator_mode: str = "ctda-python-reference",
) -> CheckResult:
    passed = result.verdict is StaticVerdict.PROVEN
    if result.verdict is StaticVerdict.INCONSISTENT:
        decision = Decision.SAFE_STOP
    elif passed:
        decision = Decision.ALLOW
    else:
        decision = Decision.REPLAN
    issues = list(result.issues)
    explanation = (
        "CTDA prefix authorization proven"
        if passed
        else "; ".join(issues) or f"CTDA prefix authorization returned {result.verdict.value}"
    )
    return CheckResult(
        passed=passed,
        layer="ctda_prefix_pre",
        violations=[] if passed else issues,
        explanation=explanation,
        suggested_decision=decision,
        lean_mode=evaluator_mode,
    )


def _ctda_monitor_check(
    result: MonitorCheckResult,
    evaluator_mode: str = "ctda-python-reference",
) -> CheckResult:
    passed = result.verdict in {MonitorVerdict.COMPLETE, MonitorVerdict.SAFE_PENDING}
    if result.verdict in {MonitorVerdict.VIOLATED, MonitorVerdict.INCONSISTENT}:
        decision = Decision.SAFE_STOP
    elif result.verdict is MonitorVerdict.UNKNOWN:
        decision = Decision.REPLAN
    else:
        decision = Decision.ALLOW
    issues = list(result.issues)
    explanation = (
        f"CTDA monitor {result.verdict.value}"
        if passed
        else "; ".join(issues) or f"CTDA monitor returned {result.verdict.value}"
    )
    return CheckResult(
        passed=passed,
        layer="ctda_monitor",
        violations=[] if passed else issues,
        explanation=explanation,
        suggested_decision=decision,
        lean_mode=evaluator_mode,
    )


def _merge_effect_results(
    legacy: CheckResult,
    ctda: CheckResult | None,
    monitor_verdict: MonitorVerdict | None,
) -> CheckResult:
    if ctda is None:
        return legacy
    if not ctda.passed:
        return ctda
    if legacy.passed:
        return ctda
    if monitor_verdict in {
        MonitorVerdict.SAFE_PENDING,
        MonitorVerdict.COMPLETE,
    } and _only_postcondition_failures(legacy):
        # The legacy Pick/Place effect checker uses ``holding`` / ``released``
        # postconditions.  In CTDA mode the mission-rooted monitor is authoritative
        # for task-specific completion (for example exact contact-part goals), while
        # collision, clearance, frame, and certificate failures remain authoritative.
        return ctda
    return legacy


def _only_postcondition_failures(result: CheckResult) -> bool:
    return bool(result.violation_reports) and all(
        report.violation_type is ViolationType.POSTCONDITION
        for report in result.violation_reports
    )


def _ctda_observation_issues(state: WorldState, spec: SafetySpec) -> tuple[str, ...]:
    missing = {
        note.removeprefix(_CTDA_UNKNOWN_OBSERVATION_PREFIX)
        for note in state.notes
        if note.startswith(_CTDA_UNKNOWN_OBSERVATION_PREFIX)
    }
    required: set[str] = set()
    protected = {str(item).lower() for item in spec.protected_objects}
    if any("hand" in item for item in protected):
        required.add("min_distance_to_human_hand")
    if any("obstacle" in item for item in protected):
        required.add("min_distance_to_obstacle")
    if spec.require_no_collision:
        required.update(("collision", "cost"))
    return tuple(
        f"missing trusted CTDA observation: {name}"
        for name in sorted(missing & required)
    )


def _ctda_state_for_spec(state: WorldState, spec: SafetySpec) -> WorldState:
    relevant_missing = {
        issue.removeprefix("missing trusted CTDA observation: ")
        for issue in _ctda_observation_issues(state, spec)
    }
    result = state.clone()
    result.notes = [
        note
        for note in result.notes
        if not note.startswith(_CTDA_UNKNOWN_OBSERVATION_PREFIX)
        or note.removeprefix(_CTDA_UNKNOWN_OBSERVATION_PREFIX) in relevant_missing
    ]
    return result


def _frozen_action_copy(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return _frozen_action_copy(value.tolist())
    if isinstance(value, (list, tuple)):
        return tuple(_frozen_action_copy(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise LiberoOnlineIntegrationError(
        f"authorized action contains unsupported value: {type(value).__name__}"
    )


def _ctda_dispatch_check(prepared: PreparedPrefix, dispatch_ns: int) -> StaticCheckResult:
    candidate = prepared.candidate
    if not candidate.verify_integrity():
        return StaticCheckResult.inconsistent("CTDA candidate integrity failed before dispatch")
    if len(prepared.authorized_actions) != 1:
        return StaticCheckResult.refuted("CTDA runtime authorizations must contain exactly one raw step")
    try:
        frozen_actions = tuple(
            _frozen_action_copy(action) for action in prepared.authorized_actions
        )
        command_digest = digest_payload(frozen_actions)
    except (TypeError, ValueError, LiberoOnlineIntegrationError) as exc:
        return StaticCheckResult.inconsistent(f"cannot bind authorized dispatch command: {exc}")
    authorization = candidate.authorization
    if command_digest != authorization.authorized_command_digest:
        return StaticCheckResult.inconsistent(
            "frozen dispatch command digest differs from its CTDA authorization"
        )
    if not authorization.is_fresh(dispatch_ns):
        return StaticCheckResult.refuted("CTDA authorization expired before command dispatch")
    if dispatch_ns + authorization.max_authorized_duration_ns > authorization.valid_until_ns:
        return StaticCheckResult.refuted(
            "remaining CTDA authorization window cannot cover the dispatched prefix"
        )
    return StaticCheckResult.success(authorization.authorization_digest)


def _ctda_metadata(
    session: CTDARuntimeSession,
    *,
    static_verdict: str | None = None,
    monitor_verdict: str | None = None,
    witness_ref: str | None = None,
    issues: Iterable[str] = (),
    contract_id: str | None = None,
    record_digest: str | None = None,
    candidate_digest: str | None = None,
    plant_trace_digest: str | None = None,
    event_trace_digest: str | None = None,
    record_payload: dict[str, Any] | None = None,
    dispatch_ns: int | None = None,
    observe_ns: int | None = None,
    bounded_stutter: bool | None = None,
    bounded_stutter_count_before: int | None = None,
    bounded_stutter_count_after: int | None = None,
    bounded_stutter_translation_before_m: float | None = None,
    bounded_stutter_translation_after_m: float | None = None,
    bounded_stutter_motion_before: float | None = None,
    bounded_stutter_motion_after: float | None = None,
) -> dict[str, Any]:
    active_contract = session.supervisor.active_contract
    monitor = session.supervisor.monitor_state
    wire_artifacts = [
        {
            "mode": item.mode.value,
            "stage": item.stage.value,
            "request_id": item.request_id,
            "verdict": item.verdict,
            "proof_verified": item.proof_verified,
            "elapsed_ns": item.elapsed_ns,
            "checker_source_digest": item.checker_source_digest,
            "checker_build_digest": item.checker_build_digest,
            "cache_key": item.cache_key,
            "artifact_dir": item.artifact_dir,
            "cache_hit": item.cache_hit,
            "parity_match": item.parity_match,
            "stdout": item.stdout,
            "stderr": item.stderr,
        }
        for item in session.evaluation_artifacts
    ]
    return {
        "spec_digest": session.supervisor.mission.spec_digest,
        "contract_id": contract_id or (active_contract.contract_id if active_contract else None),
        "active_phase": session.supervisor.active_phase,
        "monitor_state_digest": monitor.monitor_state_digest if monitor else None,
        "static_verdict": static_verdict,
        "monitor_verdict": monitor_verdict,
        "witness_ref": witness_ref,
        "issues": list(issues),
        "candidate_digest": candidate_digest,
        "record_digest": record_digest,
        "plant_trace_digest": plant_trace_digest,
        "symbolic_event_trace_digest": event_trace_digest,
        "record": record_payload,
        "dispatch_monotonic_ns": dispatch_ns,
        "observe_monotonic_ns": observe_ns,
        "performance_timing": _observation_timing_metadata(
            session,
            dispatch_ns=dispatch_ns,
            observe_ns=observe_ns,
        ),
        "bounded_stutter": (
            {
                "enabled": bounded_stutter,
                "count_before": bounded_stutter_count_before,
                "count_after": bounded_stutter_count_after,
                "persistent_no_progress_limit": (
                    session.config.raw_binder.stutter_no_progress_limit
                ),
                "translation_increment_m": (
                    None
                    if bounded_stutter_translation_before_m is None
                    or bounded_stutter_translation_after_m is None
                    else bounded_stutter_translation_after_m
                    - bounded_stutter_translation_before_m
                ),
                "translation_consumed_before_m": bounded_stutter_translation_before_m,
                "translation_consumed_after_m": bounded_stutter_translation_after_m,
                "cumulative_translation_budget_m": (
                    session.config.raw_binder.stutter_translation_bound_m
                ),
                "motion_command_increment": (
                    None
                    if bounded_stutter_motion_before is None
                    or bounded_stutter_motion_after is None
                    else bounded_stutter_motion_after
                    - bounded_stutter_motion_before
                ),
                "motion_command_consumed_before": bounded_stutter_motion_before,
                "motion_command_consumed_after": bounded_stutter_motion_after,
                "cumulative_motion_command_budget": (
                    session.config.raw_binder.stutter_motion_command_bound
                ),
                "contract_deadline_ns": (
                    session.bounded_stutter_deadline_ns
                    or (active_contract.deadline_ns if active_contract else None)
                ),
            }
            if bounded_stutter is not None
            else None
        ),
        "evaluator_mode": session.evaluator_mode,
        "wire_artifacts": wire_artifacts,
        "assurance_scope": getattr(
            session,
            "assurance_scope",
            "conditional-simulator-kinematic-test-only",
        ),
        "proof_verified": session.kernel_proof_verified,
    }


def _observation_timing_metadata(
    session: CTDARuntimeSession,
    *,
    dispatch_ns: int | None,
    observe_ns: int | None,
) -> dict[str, Any]:
    latency_ns = (
        None
        if dispatch_ns is None or observe_ns is None
        else observe_ns - dispatch_ns
    )
    sla_ns = session.config.control_period_ns
    missed = None if latency_ns is None else latency_ns > sla_ns
    return {
        "timing_policy_id": session.config.timing_policy_id,
        "realtime_timing_enforced": session.config.realtime_timing_enforced,
        "dispatch_to_observation_ns": latency_ns,
        "dispatch_to_observation_sla_ns": sla_ns,
        "dispatch_to_observation_sla_missed": missed,
        "miss_is_performance_only": bool(
            missed and not session.config.realtime_timing_enforced
        ),
    }


def _fallback_switch_metadata(
    session: CTDARuntimeSession,
    receipt: Any,
) -> dict[str, Any]:
    return {
        **asdict(receipt),
        "command": list(session.fallback_command()),
        "actuation_and_postcondition_established": (
            receipt.actuation_and_postcondition_established
        ),
        "established_for_timing_policy": (
            session.fallback_established_for_timing_policy(receipt)
        ),
        "performance_timing": {
            "timing_policy_id": session.config.timing_policy_id,
            "realtime_timing_enforced": session.config.realtime_timing_enforced,
            "trigger_to_observation_ns": receipt.switch_latency_ns,
            "switch_latency_sla_ns": receipt.switch_latency_bound_ns,
            "switch_latency_sla_missed": (
                not receipt.within_switch_latency_bound
            ),
            "miss_is_performance_only": bool(
                not receipt.within_switch_latency_bound
                and not session.config.realtime_timing_enforced
            ),
        },
    }


def make_libero_offscreen_env(bddl_file_name: str, **kwargs: Any) -> Any:
    """Create LIBERO-Safety's native OffScreenRenderEnv on a configured GPU box."""

    try:
        from libero.libero.envs import OffScreenRenderEnv
    except Exception as exc:  # pragma: no cover - depends on external benchmark install.
        raise LiberoOnlineIntegrationError(
            "Could not import LIBERO-Safety. Install the benchmark and its "
            "third_party/robosuite-1.4 dependency, then set LIBERO_SAFETY_ROOT."
        ) from exc
    return OffScreenRenderEnv(bddl_file_name=bddl_file_name, **kwargs)


def normalize_env_step(result: Any) -> tuple[Any, float, bool, dict[str, Any]]:
    if not isinstance(result, tuple):
        raise LiberoOnlineIntegrationError(f"LIBERO env.step returned unsupported value: {type(result).__name__}")
    if len(result) == 4:
        observation, reward, done, info = result
        return observation, float(reward), bool(done), dict(info or {})
    if len(result) == 5:
        observation, reward, terminated, truncated, info = result
        return observation, float(reward), bool(terminated or truncated), dict(info or {})
    raise LiberoOnlineIntegrationError(f"LIBERO env.step returned tuple of length {len(result)}")


def env_action_from_raw(raw_action: Any) -> Any:
    if isinstance(raw_action, dict) and "raw_action" in raw_action:
        return raw_action["raw_action"]
    return raw_action


def raw_actions_from_raw(raw_action: Any, max_chunk_steps: int) -> list[Any]:
    env_action = env_action_from_raw(raw_action)
    if _looks_like_action_chunk(env_action):
        try:
            return [env_action[index] for index in range(min(len(env_action), max_chunk_steps))]
        except Exception:
            return list(env_action)[:max_chunk_steps]
    return [env_action]


def _policy_action_audit(
    raw_action: Any,
    *,
    default_call_id: str,
) -> tuple[str, list[Any], dict[str, Any]]:
    """Return policy-call identity, untruncated chunk, and audit metadata."""

    policy_call_id = default_call_id
    complete_chunk: Any = env_action_from_raw(raw_action)
    policy_metadata: dict[str, Any] = {}
    if isinstance(raw_action, dict):
        supplied_call_id = raw_action.get("policy_call_id")
        if isinstance(supplied_call_id, str) and supplied_call_id.strip():
            policy_call_id = supplied_call_id
        if "policy_action_chunk" in raw_action:
            complete_chunk = raw_action["policy_action_chunk"]
        elif "raw_action" not in raw_action:
            return policy_call_id, [], policy_metadata
        supplied_metadata = raw_action.get("vla_metadata")
        if isinstance(supplied_metadata, dict):
            policy_metadata = _frozen_action_copy(supplied_metadata)
    if _looks_like_action_chunk(complete_chunk):
        try:
            values = [complete_chunk[index] for index in range(len(complete_chunk))]
        except Exception:
            values = list(complete_chunk)
    else:
        values = [complete_chunk]
    return (
        policy_call_id,
        [_frozen_action_copy(value) for value in values],
        policy_metadata,
    )


def _ctda_mission_action(session: CTDARuntimeSession) -> Action:
    """Create a logging-only symbolic view from the frozen residual obligation."""

    contract = session.supervisor.active_contract
    if contract is not None:
        payload = {
            "type": contract.skill,
            "object": contract.target,
            "part": contract.part,
            "region": contract.region,
        }
    else:
        obligations = tuple(
            item
            for item in session.supervisor.mission.phase_obligations
            if item.source_phase == session.supervisor.active_phase
        )
        bindings = {
            (item.skill, item.target, item.part, item.region) for item in obligations
        }
        if len(bindings) != 1:
            raise LiberoOnlineIntegrationError(
                "frozen mission phase has no unique Pick/Place logging view"
            )
        skill, target, part, region = next(iter(bindings))
        payload = {"type": skill, "object": target, "part": part, "region": region}
    return action_from_dict({key: value for key, value in payload.items() if value is not None})


def action_to_dict(action: Action) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": action.kind.value}
    if action.object_id is not None:
        payload["object"] = action.object_id
    if action.part is not None:
        payload["part"] = action.part
    if action.region is not None:
        payload["region"] = action.region
    if action.pose is not None:
        payload["pose"] = action.pose.to_dict()
    if action.avoid_object is not None:
        payload["avoid_object"] = action.avoid_object
    payload.update(action.params)
    return payload


def unwrap_libero_env(env: Any) -> Any:
    current = env
    seen: set[int] = set()
    while hasattr(current, "env") and id(current) not in seen:
        seen.add(id(current))
        nested = getattr(current, "env")
        if nested is current:
            break
        current = nested
    return current


def _flatten_geom_names(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        result: set[str] = set()
        for item in value:
            result.update(_flatten_geom_names(item))
        return result
    return set()


def _trailing_geom_id(name: str) -> str | None:
    match = re.search(r"(\d+)$", name)
    return str(int(match.group(1))) if match else None


def _libero_contact_name(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    # Deliberately mirror the pinned benchmark's _check_contact normalization.
    return name[9:] if "pad_collision" in name else name


def _contacted_object_geoms(
    first: str | None,
    second: str | None,
    finger_geoms: set[str],
    object_geoms: set[str],
) -> set[str]:
    result: set[str] = set()
    if first in finger_geoms and second in object_geoms and second is not None:
        result.add(second)
    if second in finger_geoms and first in object_geoms and first is not None:
        result.add(first)
    return result


def _pose_from_xyz(value: Any) -> Pose:
    return Pose(float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else 0.0)


def _part_from_dict(data: dict[str, Any]) -> Any:
    from proofalign.models import ObjectPart

    return ObjectPart.from_dict(data)


def _looks_like_human_hand(object_id: str, kind: str) -> bool:
    text = f"{object_id} {kind}".lower()
    return "human_hand" in text or "hand" in text


def _looks_like_action_chunk(value: Any) -> bool:
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            return len(shape) >= 2
        except TypeError:
            pass
    if not isinstance(value, (list, tuple)) or not value:
        return False
    return not _is_scalar(value[0])


def _is_scalar(value: Any) -> bool:
    if isinstance(value, (int, float, bool)):
        return True
    try:
        import numpy as np

        return isinstance(value, np.generic)
    except Exception:
        return False


def _last_scalar(value: Any) -> float | None:
    numbers = _flatten_numbers(value)
    return numbers[-1] if numbers else None


def _flatten_numbers(value: Any) -> list[float]:
    if _is_scalar(value):
        return [float(value)]
    if hasattr(value, "tolist"):
        try:
            return _flatten_numbers(value.tolist())
        except Exception:
            return []
    if isinstance(value, dict):
        numbers: list[float] = []
        for key in sorted(value):
            numbers.extend(_flatten_numbers(value[key]))
        return numbers
    if isinstance(value, (list, tuple)):
        numbers = []
        for item in value:
            numbers.extend(_flatten_numbers(item))
        return numbers
    return []


def _cost_dict(info: dict[str, Any]) -> dict[str, Any]:
    cost = info.get("cost", {})
    if isinstance(cost, dict):
        return dict(cost)
    return {"cost": cost}


def _cost_observed(cost: dict[str, Any]) -> bool:
    return any(bool(value) for value in cost.values())


def _collision_from_info(info: dict[str, Any]) -> bool:
    if "collision" in info:
        return bool(info["collision"])
    return _cost_observed(_cost_dict(info))


def _moved_objects(before: WorldState, after: WorldState, epsilon: float) -> list[str]:
    moved: list[str] = []
    for obj_id, before_obj in before.objects.items():
        after_obj = after.objects.get(obj_id)
        if not after_obj:
            continue
        if before_obj.pose.distance_to(after_obj.pose) > epsilon or before_obj.held_by != after_obj.held_by:
            moved.append(obj_id)
    return moved


def _object_in_region(state: WorldState, object_id: str, region_id: str) -> bool:
    obj = state.objects.get(object_id)
    region = state.regions.get(region_id)
    return bool(obj and region and region.contains(obj.pose))


def _matches_any_symbol(value: str | None, candidates: list[str]) -> bool:
    return any(_symbol_key(value) == _symbol_key(candidate) for candidate in candidates if value)


def _symbol_key(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in value.lower().replace("_", "") if ch.isalnum())
