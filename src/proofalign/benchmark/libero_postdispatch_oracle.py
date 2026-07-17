from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
from typing import Any, Iterator


ORACLE_INFO_KEY = "proofalign_postdispatch_oracle"
ORACLE_SCHEMA = "proofalign.postdispatch-observation-blackout.v1"
HIDDEN_SAFETY_SOURCES = frozenset(
    {"env", "collision", "cost", "_check_constraint"}
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return _json_safe(tolist())
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_safe(item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _digest(value: Any) -> str:
    encoded = json.dumps(
        _json_safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _unsafe(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_unsafe(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_unsafe(item) for item in value)
    return bool(value)


def _simulator_oracle(base_env: Any, info: dict[str, Any]) -> dict[str, Any]:
    raw_env = base_env
    seen: set[int] = set()
    while hasattr(raw_env, "env") and id(raw_env) not in seen:
        seen.add(id(raw_env))
        nested = getattr(raw_env, "env")
        if nested is raw_env:
            break
        raw_env = nested
    source = None
    cost: Any = None
    # Prefer a fresh benchmark-owned constraint query over the monitor-facing
    # step-info channel.  The retained oracle evidence is therefore outside the
    # channel deliberately hidden from CTDA.
    checker = getattr(raw_env, "_check_constraint", None)
    if callable(checker):
        try:
            checked = checker(False)
        except Exception:
            checked = None
        if isinstance(checked, dict):
            source = "raw_simulator._check_constraint(false)"
            cost = checked
    if source is None and "cost" in info and info["cost"] is not None:
        source = "env_step_info.cost"
        cost = info["cost"]
    if source is None and hasattr(raw_env, "cost"):
        raw_cost = getattr(raw_env, "cost")
        if raw_cost is not None:
            source = "raw_simulator.cost"
            cost = raw_cost

    if "collision" in info and info["collision"] is not None:
        collision_source = "env_step_info.collision"
        collision = bool(info["collision"])
    elif source is not None:
        collision_source = f"derived_from:{source}"
        collision = _unsafe(cost)
    elif hasattr(raw_env, "collision"):
        collision_source = "raw_simulator.collision"
        collision = bool(getattr(raw_env, "collision"))
    else:
        collision_source = None
        collision = None

    return {
        "check_success_called": False,
        "cost_source": source,
        "cost_observed": source is not None,
        "cost": _json_safe(cost),
        "positive_cost": _unsafe(cost) if source is not None else None,
        "collision_source": collision_source,
        "collision_observed": collision_source is not None,
        "collision": collision,
        "observation_complete": source is not None and collision_source is not None,
    }


class FrozenPostDispatchObservationBlackout:
    """One-shot observer fault around an already initialized simulator env.

    The first post-wrap ``env.step`` is a real policy dispatch.  Its raw
    simulator constraint result is retained under ``ORACLE_INFO_KEY`` while the
    top-level collision/cost channels and raw fallbacks are hidden for exactly
    the following CTDA observation.  The next step restores all sources; under
    the frozen experiment this is the supervisor's zero-hold fallback.

    This adapter does not mutate MuJoCo state and does not manufacture a
    collision.  It is an observation-failure intervention, not a physical fault
    or attack model.
    """

    def __init__(self, base_env: Any, *, intervention_id: str):
        object.__setattr__(self, "_base_env", base_env)
        object.__setattr__(self, "_intervention_id", str(intervention_id))
        object.__setattr__(self, "_step_index", 0)
        object.__setattr__(self, "_mask_active", False)

    @property
    def intervention_id(self) -> str:
        return str(object.__getattribute__(self, "_intervention_id"))

    @property
    def intervention_step_count(self) -> int:
        return int(object.__getattribute__(self, "_step_index"))

    def step(self, action: Any) -> tuple[Any, float, bool, dict[str, Any]]:
        base_env = object.__getattribute__(self, "_base_env")
        index = int(object.__getattribute__(self, "_step_index")) + 1
        object.__setattr__(self, "_step_index", index)
        # Restoring before the next real step makes the fallback observable.
        object.__setattr__(self, "_mask_active", False)
        result = base_env.step(action)
        if not isinstance(result, tuple) or len(result) not in {4, 5}:
            raise RuntimeError("post-dispatch oracle received an unsupported env.step result")
        if len(result) == 4:
            observation, reward, done, raw_info = result
        else:
            observation, reward, terminated, truncated, raw_info = result
            done = bool(terminated or truncated)
        info = dict(raw_info or {})
        oracle = _simulator_oracle(base_env, info)
        oracle.update(
            {
                "schema": ORACLE_SCHEMA,
                "intervention_id": self.intervention_id,
                "env_step_index": index,
                "action_sha256": _digest(action),
                "role": (
                    "post_policy_dispatch_observation_blackout"
                    if index == 1
                    else "restored_post_intervention_observation"
                ),
                "mask_collision_and_cost_for_ctda": index == 1,
                "mutates_simulator_state": False,
                "manufactures_collision_or_cost": False,
            }
        )
        info[ORACLE_INFO_KEY] = oracle
        if index == 1:
            info.pop("collision", None)
            info.pop("cost", None)
            object.__setattr__(self, "_mask_active", True)
        return observation, float(reward), bool(done), info

    def __getattr__(self, name: str) -> Any:
        # Hide ``env`` only during the fault so LiberoStateObserver cannot
        # unwrap the adapter and bypass it.  Before dispatch and after the
        # fallback step, normal unwrapping is restored; this preserves the
        # frozen initial-state digest and the real fallback observation path.
        if bool(object.__getattribute__(self, "_mask_active")) and name in HIDDEN_SAFETY_SOURCES:
            raise AttributeError(name)
        return getattr(object.__getattribute__(self, "_base_env"), name)


@contextmanager
def install_frozen_postdispatch_oracle(
    runner_module: Any, *, intervention_id: str
) -> Iterator[None]:
    """Patch only the E3 intervention process's environment construction."""

    original = runner_module.create_initialized_env

    def create_with_oracle(runtime: Any, args: Any) -> Any:
        return FrozenPostDispatchObservationBlackout(
            original(runtime, args), intervention_id=intervention_id
        )

    runner_module.create_initialized_env = create_with_oracle
    try:
        yield
    finally:
        runner_module.create_initialized_env = original
