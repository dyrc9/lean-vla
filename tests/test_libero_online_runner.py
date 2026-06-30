from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from proofalign.benchmark import libero_online_runner
from proofalign.benchmark.libero_online_runner import LiberoTaskRuntime, _resolve_task_bddl_path, run_online_episode


@dataclass
class FakeObjectModel:
    category_name: str
    root_body: str
    contact_geoms: list[str]


class FakeSimData:
    body_xpos = [[0.2, 0.1, 0.0]]
    site_xpos = [[0.0, 0.0, 0.0]]


class FakeSim:
    data = FakeSimData()


class FakeOnlineEnv:
    def __init__(self) -> None:
        self.sim = FakeSim()
        self.objects_dict = {"mug": FakeObjectModel("mug", "mug_main", ["mug_g0"])}
        self.fixtures_dict = {}
        self.object_sites_dict = {}
        self.obj_body_id = {"mug": 0}
        self.held_object = None
        self.step_count = 0
        self.init_state = None
        self.closed = False

    def seed(self, seed):
        self.seed_value = seed

    def reset(self):
        return self._get_observations()

    def set_init_state(self, init_state):
        self.init_state = init_state
        return self._get_observations()

    def _get_observations(self):
        return {"robot0_eef_pos": [0.0, 0.0, 0.0]}

    def step(self, action):
        self.step_count += 1
        self.held_object = "mug"
        return {"robot0_eef_pos": [0.2, 0.1, 0.0]}, 1.0, False, {"cost": {}}

    def close(self):
        self.closed = True


def test_online_runner_uses_initialized_real_env_shape(monkeypatch, tmp_path: Path):
    env = FakeOnlineEnv()
    action_path = tmp_path / "actions.json"
    action_path.write_text(
        json.dumps(
            [
                {
                    "raw_action": [0, 0, 0, 0, 0, 0, 0],
                    "proofalign_action": {"type": "Pick", "object": "mug", "part": "body"},
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "episode.json"

    monkeypatch.setattr(
        libero_online_runner,
        "load_libero_task_runtime",
        lambda **kwargs: LiberoTaskRuntime(
            benchmark=None,
            task=None,
            task_id=0,
            task_name="fake_task",
            instruction="pick up the mug by the body",
            bddl_file=tmp_path / "fake.bddl",
            init_state=[1, 2, 3],
            init_state_id=0,
            metadata={"benchmark_name": "affordance"},
        ),
    )
    monkeypatch.setattr(libero_online_runner, "create_initialized_env", lambda runtime, args: env)

    args = libero_online_runner.parse_args(
        [
            "--action-file",
            str(action_path),
            "--output",
            str(output_path),
            "--max-steps",
            "1",
        ]
    )
    decision = run_online_episode(args)

    assert decision.decision.value == "allow"
    assert env.step_count == 1
    assert env.closed is True
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "allow"
    assert payload["trace"][0]["action"] == "Pick"


def test_resolve_task_bddl_path_uses_level_subdirectory(tmp_path: Path):
    bddl_path = tmp_path / "affordance" / "L0" / "task.bddl"
    bddl_path.parent.mkdir(parents=True)
    bddl_path.write_text("(define (problem task))", encoding="utf-8")

    class Task:
        problem_folder = "affordance"
        bddl_file = "task.bddl"
        level = 0

    assert _resolve_task_bddl_path(str(tmp_path), Task()) == bddl_path
