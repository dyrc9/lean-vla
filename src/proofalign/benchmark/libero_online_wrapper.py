from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from proofalign.action_abstraction import action_from_dict
from proofalign.benchmark.libero_safety_adapter import _parts_for_kind
from proofalign.certificates import CertificateBundle
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent
from proofalign.models import (
    Action,
    CheckResult,
    Decision,
    ExecutionDecision,
    ExecutionStep,
    Object,
    Pose,
    Region,
    SafetySpec,
    TaskIntent,
    WorldState,
)


class LiberoOnlineIntegrationError(RuntimeError):
    """Raised when a real LIBERO/VLA value cannot be safely abstracted."""


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

    def observe(self, env: Any, observation: Any | None = None, info: dict[str, Any] | None = None) -> WorldState:
        info = info or {}
        raw_env = unwrap_libero_env(env)
        sim = getattr(raw_env, "sim", getattr(env, "sim", None))
        objects = self._objects(raw_env, sim)
        regions = self._regions(raw_env, sim)
        gripper_holding = next((obj.object_id for obj in objects.values() if obj.held_by == "gripper"), None)
        robot_pose = self._robot_pose(raw_env, sim, observation)
        return WorldState(
            objects=objects,
            regions=regions,
            gripper_holding=gripper_holding,
            robot_pose=robot_pose,
            min_distance_to_human_hand=self._distance(info, "human_hand", robot_pose, objects),
            min_distance_to_obstacle=self._distance(info, "obstacle", robot_pose, objects),
            collision=self._collision(info),
            last_action_success=bool(info.get("last_action_success", True)),
            notes=["state observed from LIBERO-Safety robosuite/MuJoCo backend"],
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

    def _distance(self, info: dict[str, Any], target: str, robot_pose: Pose, objects: dict[str, Object]) -> float:
        keys = (
            f"min_distance_to_{target}",
            f"{target}_distance",
            f"min_{target}_distance",
        )
        for key in keys:
            if key in info:
                return float(info[key])
        candidates = [
            obj.pose.distance_to(robot_pose)
            for obj in objects.values()
            if target in obj.object_id.lower() or target in obj.kind.lower()
        ]
        return min(candidates) if candidates else self.default_safety_distance

    def _collision(self, info: dict[str, Any]) -> bool:
        if "collision" in info:
            return bool(info["collision"])
        cost = info.get("cost")
        if isinstance(cost, dict):
            return any(bool(value) for value in cost.values())
        return False


@dataclass
class ProofAlignLiberoWrapper:
    """Online ProofAlign gate around a LIBERO-Safety env."""

    env: Any
    instruction: str
    spec: SafetySpec
    checker: DualAlignmentChecker = field(default_factory=DualAlignmentChecker)
    state_observer: LiberoStateObserver = field(default_factory=LiberoStateObserver)
    action_abstractor: LiberoActionAbstractor = field(default_factory=DefaultLiberoActionAbstractor)

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
        return observation

    def step(self, raw_action: Any) -> LiberoStepResult:
        if self.current_state is None:
            self.current_state = self.state_observer.observe(self.env, self.current_observation)
        before = self.current_state.clone()
        symbolic_action = self.action_abstractor.abstract(
            raw_action,
            instruction=self.instruction,
            observation=self.current_observation,
            state=before,
            spec=self.spec,
            history=self.trace,
        )
        pre_certs = CertificateBundle.from_dicts(symbolic_action.params.get("pre_certificates"))
        intent_result = self.checker.check_intent_alignment(
            self.intent,
            before,
            symbolic_action,
            self.spec,
            pre_certs,
            len(self.trace),
        )
        if not intent_result.passed:
            step = ExecutionStep(
                symbolic_action,
                intent_result,
                None,
                intent_result.suggested_decision,
                before,
                pre_certificates=pre_certs.to_dicts(),
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

        observation, reward, done, info = normalize_env_step(self.env.step(env_action_from_raw(raw_action)))
        self.current_observation = observation
        info = dict(info)
        after = self.state_observer.observe(self.env, observation, info)
        post_certs = CertificateBundle.from_dicts(symbolic_action.params.get("post_certificates"))
        effect_result = self.checker.check_effect_alignment(
            before,
            symbolic_action,
            after,
            self.spec,
            post_certs,
            len(self.trace),
        )
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
        )
        self.trace.append(step)
        self.current_state = after
        return LiberoStepResult(observation, float(reward), done, info, decision, step)

    def run_episode(self, policy: VLAActionProvider, *, max_steps: int) -> ExecutionDecision:
        if self.current_observation is None:
            self.reset()
        final_decision = Decision.ALLOW
        explanation = "episode completed without ProofAlign violations"
        for _ in range(max_steps):
            raw_action = policy(self.instruction, self.current_observation, self.trace)
            result = self.step(raw_action)
            final_decision = result.decision
            if result.decision != Decision.ALLOW:
                explanation = result.step.effect_result.explanation if result.step.effect_result else result.step.intent_result.explanation
                break
            if result.done:
                break
        final_state = self.current_state or self.state_observer.observe(self.env, self.current_observation)
        return ExecutionDecision(final_decision, final_state, list(self.trace), explanation)

    def _info(self, decision: Decision, result: CheckResult) -> dict[str, Any]:
        return {
            "proofalign_decision": decision.value,
            "proofalign_layer": result.layer,
            "proofalign_explanation": result.explanation,
            "proofalign_violations": list(result.violations),
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


def _pose_from_xyz(value: Any) -> Pose:
    return Pose(float(value[0]), float(value[1]), float(value[2]) if len(value) > 2 else 0.0)


def _part_from_dict(data: dict[str, Any]) -> Any:
    from proofalign.models import ObjectPart

    return ObjectPart.from_dict(data)


def _looks_like_human_hand(object_id: str, kind: str) -> bool:
    text = f"{object_id} {kind}".lower()
    return "human_hand" in text or "hand" in text
