#!/usr/bin/env python3
"""Runtime bridge for frozen, LLM-proposed trusted semantic templates."""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import re
import sys
from typing import Any, Iterator, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.digests import digest_text  # noqa: E402
from proofalign.llm_semantic_templates import (  # noqa: E402
    catalog_index,
    compile_from_catalog,
)
from proofalign.semantic_local_checker import EntityPosition, TrustedLocalObservation  # noqa: E402
from proofalign.semantic_local_checker import (  # noqa: E402
    LocalActionAssessment,
    SemanticExecutablePrefixChecker,
    parse_semantic_subtask,
)
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402
from scripts import run_v15_bounded_state_triggered_task_utility_qualification as clean_runner  # noqa: E402


RUNTIME_SCHEMA = "proofalign.llm-semantic-template-runtime-audit.v1"


class LLMTemplateRuntimeError(RuntimeError):
    pass


class LLMTemplateExecutablePrefixChecker(SemanticExecutablePrefixChecker):
    """Extend the analytic checker with target-directed articulation prefixes.

    This checker deliberately certifies only current-geometry compatibility.  It
    never claims that an unobserved joint predicate has become true; task success
    remains owned by the benchmark environment.
    """

    def assess(
        self,
        *,
        semantic_subtask: str,
        observation: TrustedLocalObservation,
        command: Any,
        command_shape: Any,
        expected_state_epoch: int,
        release_destination: str | None = None,
    ) -> LocalActionAssessment:
        try:
            subtask = parse_semantic_subtask(semantic_subtask)
        except Exception:
            return super().assess(
                semantic_subtask=semantic_subtask,
                observation=observation,
                command=command,
                command_shape=command_shape,
                expected_state_epoch=expected_state_epoch,
                release_destination=release_destination,
            )
        if subtask.verb not in {"open", "close", "actuate"}:
            return super().assess(
                semantic_subtask=semantic_subtask,
                observation=observation,
                command=command,
                command_shape=command_shape,
                expected_state_epoch=expected_state_epoch,
                release_destination=release_destination,
            )
        if observation.state_epoch != expected_state_epoch:
            return self._unknown(
                "stale_observation_state_epoch",
                target=subtask.target,
                part=subtask.part,
            )
        try:
            steps = self._steps(command, command_shape)
        except Exception as exc:
            return self._unknown(
                f"malformed_checker_input:{exc}",
                target=subtask.target,
                part=subtask.part,
            )
        target = observation.position(subtask.target or "")
        if target is None:
            return self._unknown(
                "missing_articulation_target_geometry",
                target=subtask.target,
                part=subtask.part,
            )
        violations = self._hard_violations(
            observation,
            steps,
            allowed_contact_entities={str(subtask.target)},
        )
        trajectory = self._trajectory(observation.eef_position, steps)
        initial_distance = sum(
            (observation.eef_position[index] - target[index]) ** 2
            for index in range(3)
        ) ** 0.5
        closest_distance = min(
            sum((position[index] - target[index]) ** 2 for index in range(3)) ** 0.5
            for position in trajectory
        )
        progress = initial_distance - closest_distance
        manipulates_near_target = any(
            (
                sum((position[index] - target[index]) ** 2 for index in range(3)) ** 0.5
                <= self.config.target_neighborhood_m
            )
            and (
                sum(float(value) ** 2 for value in step[3:6]) ** 0.5 >= 0.05
                or abs(float(step[6])) >= 0.2
            )
            for position, step in zip(trajectory, steps, strict=True)
        )
        compatible = (
            not violations
            and (
                progress >= self.config.min_progress_m
                or manipulates_near_target
            )
        )
        return LocalActionAssessment(
            known=True,
            semantic_compatible=compatible,
            motion_atoms=(
                ("interact_with_articulation_target",)
                if manipulates_near_target
                else ("approach_articulation_target",)
            ),
            precondition_atoms=(
                "trusted_articulation_target_geometry_known",
                "articulation_completion_not_inferred",
            ),
            predicted_effect_atoms=(
                (
                    "articulation_interaction_prefix"
                    if manipulates_near_target
                    else "closer_to_articulation_target"
                ),
            ),
            violation_atoms=violations,
            progress_margin=progress,
            target=subtask.target,
            part=subtask.part,
            region=None,
        )


def _underlying_env(env: Any) -> Any:
    current = env
    seen: set[int] = set()
    while id(current) not in seen:
        seen.add(id(current))
        candidate = getattr(current, "_env", None)
        if candidate is not None:
            current = candidate
            continue
        candidate = getattr(current, "env", None)
        if candidate is not None and candidate is not current:
            current = candidate
            continue
        break
    return current


class TemplateGeometryBridge:
    """Bind frozen part IDs to exact MuJoCo contact-geom positions."""

    def __init__(self, catalog_path: Path) -> None:
        self.catalog_path = catalog_path
        self.catalog = load_json_object(catalog_path)
        self.index = catalog_index(self.catalog)
        self.catalog_sha256 = file_sha256(catalog_path)
        self.env: Any | None = None
        self.current_template: Mapping[str, Any] | None = None
        self.resolution_count = 0
        self.resolution_failures = 0
        self.selected_geom_counts: dict[str, int] = {}

    def begin_episode(self) -> None:
        self.env = None
        self.current_template = None
        self.resolution_count = 0
        self.resolution_failures = 0
        self.selected_geom_counts = {}

    def compile(self, bddl_text: str) -> Any:
        digest = digest_text(bddl_text)
        template = self.index.get(digest)
        if template is None:
            raise LLMTemplateRuntimeError(
                "runtime trusted BDDL is absent from the frozen LLM catalog"
            )
        self.current_template = template
        return compile_from_catalog(bddl_text, self.catalog)

    def bind_env(self, env: Any) -> None:
        if self.env is not None:
            raise LLMTemplateRuntimeError(
                "more than one simulator was created in one episode"
            )
        self.env = env

    def resolve_part_target(
        self, eef_position: tuple[float, float, float]
    ) -> EntityPosition | None:
        template = self.current_template
        if template is None:
            raise LLMTemplateRuntimeError("semantic template was not compiled")
        frozen = template["template"]
        part_goals = [
            row
            for row in frozen["goals"]
            if row["family"] == "grasp_allowed_part"
        ]
        if not part_goals:
            return None
        if len(part_goals) != 1:
            raise LLMTemplateRuntimeError(
                "runtime supports one grasp-part goal per trusted task"
            )
        frozen_goal = part_goals[0]
        if self.env is None:
            raise LLMTemplateRuntimeError("semantic part geometry has no simulator")
        raw = _underlying_env(self.env)
        sim = getattr(raw, "sim", None)
        objects = getattr(raw, "objects_dict", None)
        target = str(frozen_goal["target"])
        if sim is None or not isinstance(objects, Mapping) or target not in objects:
            self.resolution_failures += 1
            raise LLMTemplateRuntimeError(
                f"trusted simulator object is unavailable: {target}"
            )
        allowed = {
            int(value) for value in frozen_goal["allowed_part_ids"]
        }
        positions = []
        for geom_name in objects[target].contact_geoms:
            match = re.search(r"(\d+)$", str(geom_name))
            if match is None or int(match.group(1)) not in allowed:
                continue
            try:
                geom_id = sim.model.geom_name2id(str(geom_name))
                value = np.asarray(sim.data.geom_xpos[geom_id], dtype=np.float64)
            except Exception:
                continue
            if value.shape == (3,) and np.isfinite(value).all():
                position = tuple(float(item) for item in value)
                distance = sum(
                    (position[index] - eef_position[index]) ** 2
                    for index in range(3)
                )
                positions.append((distance, str(geom_name), position))
        if not positions:
            self.resolution_failures += 1
            raise LLMTemplateRuntimeError(
                f"no exact contact geom matches frozen parts for {target}"
            )
        _distance, geom_name, position = min(positions)
        self.resolution_count += 1
        self.selected_geom_counts[geom_name] = (
            self.selected_geom_counts.get(geom_name, 0) + 1
        )
        return EntityPosition(target, position)

    def audit(self, *, l1_enabled: bool) -> dict[str, Any]:
        template = self.current_template
        return {
            "schema": RUNTIME_SCHEMA,
            "l1_enabled": l1_enabled,
            "catalog_path": self.catalog_path.relative_to(REPO_ROOT).as_posix(),
            "catalog_sha256": self.catalog_sha256,
            "template_sha256": (
                template.get("template_sha256") if template is not None else None
            ),
            "template_family": (
                [row["family"] for row in template["template"]["goals"]]
                if template is not None
                else None
            ),
            "llm_output_authoritative": False,
            "attacked_prompt_visible_to_generator": False,
            "runtime_llm_call_count": 0,
            "exact_simulator_part_resolution_count": self.resolution_count,
            "part_resolution_failure_count": self.resolution_failures,
            "selected_geom_counts": dict(sorted(self.selected_geom_counts.items())),
        }


def _patched_observation_class(bridge: TemplateGeometryBridge) -> type:
    original = TrustedLocalObservation

    class LLMTemplateTrustedObservation(original):
        @classmethod
        def from_libero_observation(
            cls,
            observation: Mapping[str, Any],
            *,
            state_epoch: int,
        ) -> TrustedLocalObservation:
            current = original.from_libero_observation(
                observation, state_epoch=state_epoch
            )
            entities = {
                item.entity_id: item for item in current.entity_positions
            }
            resolved = bridge.resolve_part_target(current.eef_position)
            if resolved is not None:
                entities[resolved.entity_id] = resolved
            return original(
                state_epoch=current.state_epoch,
                eef_position=current.eef_position,
                gripper_qpos=current.gripper_qpos,
                entity_positions=tuple(entities.values()),
            )

    return LLMTemplateTrustedObservation


@contextmanager
def patched_llm_template_runtime(catalog_path: Path) -> Iterator[TemplateGeometryBridge]:
    from proofalign import semantic_policy_wrapper

    bridge = TemplateGeometryBridge(catalog_path)
    original_compile = semantic_policy_wrapper.compile_libero_task_graph
    original_checker = semantic_policy_wrapper.SemanticExecutablePrefixChecker
    original_create_env = base.create_env
    original_observation = base.TrustedLocalObservation
    original_online = clean_runner.online.run_episode
    original_disabled = clean_runner.disabled_online.run_episode

    def create_env(*args: Any, **kwargs: Any) -> Any:
        env = original_create_env(*args, **kwargs)
        bridge.bind_env(env)
        return env

    def annotate(original: Any) -> Any:
        def wrapped(**kwargs: Any) -> dict[str, Any]:
            bridge.begin_episode()
            payload = original(**kwargs)
            metadata = dict(payload.get("metadata") or {})
            l1_enabled = bool(metadata.get("l1_semantic_alignment"))
            audit = bridge.audit(l1_enabled=l1_enabled)
            metadata.update(
                {
                    "llm_semantic_template_active": l1_enabled,
                    "llm_semantic_template_catalog_sha256": bridge.catalog_sha256,
                    "llm_semantic_template_sha256": audit["template_sha256"],
                    "llm_semantic_template_runtime_llm_calls": 0,
                    "llm_semantic_template_attacked_prompt_visible": False,
                    "post_failure_exploratory_method_extension": True,
                }
            )
            payload["metadata"] = metadata
            payload["llm_semantic_template_audit"] = audit
            clean_runner.disabled_online.v1._persist_annotated_episode(payload)
            return payload

        return wrapped

    semantic_policy_wrapper.compile_libero_task_graph = bridge.compile
    semantic_policy_wrapper.SemanticExecutablePrefixChecker = (
        LLMTemplateExecutablePrefixChecker
    )
    base.create_env = create_env
    base.TrustedLocalObservation = _patched_observation_class(bridge)
    clean_runner.online.run_episode = annotate(original_online)
    clean_runner.disabled_online.run_episode = annotate(original_disabled)
    try:
        yield bridge
    finally:
        semantic_policy_wrapper.compile_libero_task_graph = original_compile
        semantic_policy_wrapper.SemanticExecutablePrefixChecker = original_checker
        base.create_env = original_create_env
        base.TrustedLocalObservation = original_observation
        clean_runner.online.run_episode = original_online
        clean_runner.disabled_online.run_episode = original_disabled


__all__ = [
    "LLMTemplateRuntimeError",
    "LLMTemplateExecutablePrefixChecker",
    "RUNTIME_SCHEMA",
    "TemplateGeometryBridge",
    "patched_llm_template_runtime",
]
