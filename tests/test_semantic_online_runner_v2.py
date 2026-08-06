from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from proofalign.benchmark.libero_runtime import LiberoTaskRuntime
from scripts import run_l2_execution_attack_eval_v2 as runner


BDDL = """
(define (problem online-v2)
  (:domain robosuite)
  (:objects red_mug_1 - red_mug plate_1 - plate)
  (:init (On red_mug_1 main_table_region))
  (:goal (And (On red_mug_1 plate_1)))
)
"""


def _observation() -> dict[str, np.ndarray]:
    return {
        "agentview_image": np.zeros((4, 4, 3), dtype=np.uint8),
        "robot0_eye_in_hand_image": np.ones(
            (4, 4, 3), dtype=np.uint8
        ),
        "robot0_eef_pos": np.asarray(
            (0.0, 0.0, 0.25), dtype=np.float64
        ),
        "robot0_eef_quat": np.asarray(
            (0.0, 0.0, 0.0, 1.0), dtype=np.float64
        ),
        "robot0_gripper_qpos": np.asarray(
            (0.04, -0.04), dtype=np.float64
        ),
        "red_mug_1_pos": np.asarray(
            (0.15, 0.0, 0.25), dtype=np.float64
        ),
    }


class _Model:
    nsite = 1

    @staticmethod
    def site_name2id(name: str) -> int:
        if name != "plate_1":
            raise KeyError(name)
        return 0


class _Data:
    body_xpos = np.zeros((1, 3), dtype=np.float64)

    @staticmethod
    def get_site_xpos(name: str) -> np.ndarray:
        if name != "plate_1":
            raise KeyError(name)
        return np.asarray((0.4, 0.0, 0.25), dtype=np.float64)


class _Environment:
    def __init__(self) -> None:
        self.observation = _observation()
        self.applied: list[list[float]] = []
        self.sim = SimpleNamespace(model=_Model(), data=_Data())
        self.obj_body_id: dict[str, int] = {}

    def reset(self):
        return self.observation

    def _get_observations(self):
        return self.observation

    def step(self, action):
        self.applied.append(list(action))
        updated = dict(self.observation)
        updated["robot0_eef_pos"] = np.asarray(
            (
                float(self.observation["robot0_eef_pos"][0])
                + float(action[0]) * 0.05,
                float(self.observation["robot0_eef_pos"][1]),
                float(self.observation["robot0_eef_pos"][2]),
            ),
            dtype=np.float64,
        )
        self.observation = updated
        return self.observation, 0.0, True, {}

    def check_success(self):
        return bool(self.applied)

    def close(self):
        return None


class _Policy:
    def __init__(self, deltas: tuple[float, ...]) -> None:
        self.deltas = deltas
        self.calls = 0

    def infer(self, element):
        del element
        delta = self.deltas[self.calls % len(self.deltas)]
        self.calls += 1
        return {
            "actions": np.asarray(
                ((delta, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),),
                dtype=np.float64,
            )
        }


class _ImageTools:
    @staticmethod
    def resize_with_pad(value, height, width):
        del height, width
        return np.asarray(value)

    @staticmethod
    def convert_to_uint8(value):
        return np.asarray(value, dtype=np.uint8)


def _run(
    monkeypatch,
    tmp_path: Path,
    *,
    deltas: tuple[float, ...],
    semantic_runtime: bool = True,
):
    bddl_path = tmp_path / "task.bddl"
    bddl_path.write_text(BDDL, encoding="utf-8")
    runtime = LiberoTaskRuntime(
        benchmark=None,
        task=None,
        task_id=0,
        task_name="put_red_mug_on_plate",
        instruction="put the red mug on the plate",
        bddl_file=bddl_path,
        init_state=None,
        init_state_id=0,
        metadata={
            "benchmark_name": "unit_suite",
            "task_id": 0,
            "task_name": "put_red_mug_on_plate",
            "init_state_id": 0,
        },
    )
    environment = _Environment()
    policy = _Policy(deltas)
    output_dir = tmp_path / "output"
    (output_dir / "episodes").mkdir(parents=True)
    (output_dir / "videos").mkdir()
    monkeypatch.setattr(
        runner.base,
        "load_libero_task_runtime",
        lambda **_kwargs: runtime,
    )
    monkeypatch.setattr(
        runner.base,
        "create_env",
        lambda *_args, **_kwargs: environment,
    )
    args = SimpleNamespace(
        max_steps=1,
        num_steps_wait=0,
        resize_size=4,
        replan_steps=1,
        seed=7,
        semantic_runtime=semantic_runtime,
        semantic_policy_mode="deployment",
        semantic_max_projection_l2=0.5,
        semantic_min_progress_m=None,
        semantic_candidate_count=3,
        semantic_authorization_ttl_ns=60_000_000_000,
        checkpoint_dir=Path("/checkpoint"),
        openpi_config="pi05_libero",
        env_img_res=4,
        sample_steps=10,
        save_video=False,
        _multiple_policy_seeds=False,
        output_dir=output_dir,
        execution_attack_family="none",
        execution_attack_placement="pre_boundary",
        l1_semantic_alignment="on" if semantic_runtime else "off",
        l2_execution_integrity="on" if semantic_runtime else "off",
    )
    payload = runner.run_episode(
        args=args,
        policy=policy,
        jax=SimpleNamespace(),
        policy_seed=0,
        image_tools=_ImageTools(),
        suite="unit_suite",
        task_id=0,
        init_state_id=0,
        attack_records={},
        output_dir=output_dir,
        observation_transform=None,
        wrist_observation_transform=None,
        constraint_signal_extractor=lambda *_args: {
            "schema": "proofalign.saber-independent-constraint-signals.v1",
            "robot_contact_count": 0,
            "joint_limit_violation": False,
            "max_robot_contact_force_newtons": 0.0,
            "excessive_force": False,
            "raw_action_l2": 0.0,
            "raw_action_magnitude_violation": False,
            "action_clipping_ratio": 0.0,
            "official_saber_source_sha256": "0" * 64,
        },
    )
    return payload, environment, policy


def test_v2_resolves_exact_site_and_selects_feasible_candidate(
    monkeypatch,
    tmp_path,
) -> None:
    payload, environment, policy = _run(
        monkeypatch,
        tmp_path,
        deltas=(0.01, 1.0, 0.5),
    )

    assert policy.calls == 3
    assert environment.applied[0][0] == 1.0
    assert payload["decision"] == "env_done"
    audit = payload["observation_frame_audits"][0][
        "bounded_candidate_selection_v2"
    ]
    assert audit["candidate_count"] == 3
    assert audit["eligible_selected_source_candidate_index"] == 1
    assert not audit["fallback_for_fail_closed_recheck"]
    geometry = payload["trusted_geometry_audit_v2"]
    assert geometry["required_entity_ids"] == ("plate_1",)
    assert geometry["source_counts"]["plate_1:exact_sim_site"] >= 1
    assert geometry["unresolved_counts"] == {}


def test_v2_keeps_fail_closed_when_no_candidate_passes(
    monkeypatch,
    tmp_path,
) -> None:
    payload, environment, policy = _run(
        monkeypatch,
        tmp_path,
        deltas=(0.01, 0.02, 0.03),
    )

    assert policy.calls == 3
    assert environment.applied == []
    assert payload["decision"] == "semantic_action_rejected"
    audit = payload["observation_frame_audits"][0][
        "bounded_candidate_selection_v2"
    ]
    assert audit["eligible_selected_source_candidate_index"] is None
    assert audit["fallback_for_fail_closed_recheck"]


def test_v2_does_not_change_non_l1_policy_budget(
    monkeypatch,
    tmp_path,
) -> None:
    payload, environment, policy = _run(
        monkeypatch,
        tmp_path,
        deltas=(1.0,),
        semantic_runtime=False,
    )

    assert policy.calls == 1
    assert environment.applied
    assert not payload["metadata"]["l1_availability_repair_active"]
    assert "trusted_geometry_audit_v2" not in payload
