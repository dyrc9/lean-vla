from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import asdict, dataclass
from pathlib import Path

import pytest

from proofalign.benchmark import libero_online_runner
from proofalign.benchmark.libero_online_runner import (
    LiberoOnlineIntegrationError,
    LiberoTaskRuntime,
    _prepare_ctda_trust_root,
    _validate_ctda_fallback_manifest,
    _resolve_task_bddl_path,
    run_online_episode,
    run_online_episode_with_plugins,
)
from proofalign.ctda import digest_payload
from proofalign.models import SafetySpec


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
        self.actions = []
        self.init_state = None
        self.closed = False
        self.min_distance_to_human_hand = 1.0
        self.min_distance_to_obstacle = 1.0
        self.collision = False
        self.cost = {}
        self.action_spec = ([-1.0] * 7, [1.0] * 7)

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
        self.actions.append(list(action))
        self.held_object = "mug"
        return {"robot0_eef_pos": [0.0, 0.0, 0.0]}, 1.0, False, {"cost": {}, "collision": False}

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
            "--warmup-steps",
            "1",
            "--warmup-gripper",
            "-1",
        ]
    )
    decision = run_online_episode(args)

    assert decision.decision.value == "allow"
    assert env.step_count == 1
    assert env.closed is True
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["decision"] == "allow"
    assert payload["trace"][0]["action"] == "Pick"


def test_online_runner_attack_record_overrides_policy_instruction(monkeypatch, tmp_path: Path):
    env = FakeOnlineEnv()
    output_path = tmp_path / "episode.json"
    attack_path = tmp_path / "attack.json"
    attack_path.write_text(
        json.dumps(
            [
                {
                    "suite": "affordance",
                    "task_id": 0,
                    "init_state_id": 0,
                    "original_instruction": "pick up the mug",
                    "perturbed_instruction": "pick up the mug by the body",
                    "objective": "task_failure",
                    "tools_used": ["prompt"],
                    "source": "unit_test",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        libero_online_runner,
        "load_libero_task_runtime",
        lambda **kwargs: LiberoTaskRuntime(
            benchmark=None,
            task=None,
            task_id=0,
            task_name="fake_task",
            instruction="pick up the mug",
            bddl_file=tmp_path / "fake.bddl",
            init_state=[1, 2, 3],
            init_state_id=0,
            metadata={"benchmark_name": "affordance", "task_id": 0, "init_state_id": 0},
        ),
    )
    monkeypatch.setattr(libero_online_runner, "create_initialized_env", lambda runtime, args: env)

    class RecordingPolicy:
        def __init__(self) -> None:
            self.instructions: list[str] = []

        def __call__(self, instruction, observation, history):
            del observation, history
            self.instructions.append(instruction)
            return {
                "raw_action": [0, 0, 0, 0, 0, 0, 0],
                "proofalign_action": {"type": "Pick", "object": "mug", "part": "body"},
            }

    policy = RecordingPolicy()
    args = libero_online_runner.parse_args(
        [
            "--benchmark",
            "affordance",
            "--task-id",
            "0",
            "--init-state-id",
            "0",
            "--attack-record",
            str(attack_path),
            "--output",
            str(output_path),
            "--max-steps",
            "1",
            "--warmup-steps",
            "0",
        ]
    )

    run_online_episode_with_plugins(args, policy=policy)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert policy.instructions == ["pick up the mug by the body"]
    assert payload["metadata"]["original_instruction"] == "pick up the mug"
    assert payload["metadata"]["attack_record_claimed_original_instruction"] == "pick up the mug"
    assert payload["metadata"]["perturbed_instruction"] == "pick up the mug by the body"
    assert payload["metadata"]["attack_objective"] == "task_failure"
    assert payload["metadata"]["attack_tools_used"] == ["prompt"]
    assert payload["metadata"]["attack_record_source"] == "unit_test"


def test_online_runner_ctda_flag_persists_proof_chain(monkeypatch, tmp_path: Path):
    env = FakeOnlineEnv()
    bddl_path = tmp_path / "fake.bddl"
    bddl_path.write_text("(define (problem fake))", encoding="utf-8")
    fallback_path = tmp_path / "hold_fallback.json"
    bddl_digest = sha256(bddl_path.read_bytes()).hexdigest()
    fallback_path.write_text(
        json.dumps(
            {
                "schema": "proofalign.ctda.fallback.v2",
                "spec_id": "affordance:0:0",
                "bddl_digest": bddl_digest,
                "safety_spec_digest": digest_payload(asdict(SafetySpec.from_dict({}))),
                "controller_id": "hold",
                "model_id": "libero-delta-kinematic-v1",
                "assurance_scope": "operator-pinned-simulator-test-only",
                "safe_set_digest": "fixture-safe-set",
                "assurance_artifact_digest": "fixture-assurance-artifact",
                "operator_trusted": True,
                "worst_case_switch_latency_ns": 50_000_000,
                "fallback_action": [0, 0, 0, 0, 0, 0, 0],
            }
        ),
        encoding="utf-8",
    )
    fallback_digest = sha256(fallback_path.read_bytes()).hexdigest()
    env._proofalign_bddl_snapshot_path = str(bddl_path)
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
            bddl_file=bddl_path,
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
            "--ctda",
            "--ctda-fallback-witness",
            str(fallback_path),
            "--ctda-fallback-witness-sha256",
            fallback_digest,
            "--ctda-evidence-mode",
            "local-simulator-exact-allowlist",
            "--ctda-episode-nonce",
            "runner-ctda-test-episode",
            "--warmup-steps",
            "0",
        ]
    )

    decision = run_online_episode(args)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert decision.decision.value == "allow"
    assert payload["trace"][0]["ctda"]["monitor_verdict"] == "complete"
    assert payload["trace"][0]["ctda"]["record_digest"]
    assert payload["trace"][0]["ctda"]["record"]["plant_trace"]["samples"]
    assert payload["trace"][0]["ctda"]["record"]["event_trace"]["events"]
    assert payload["metadata"]["ctda"]["proof_verified"] is False
    assert payload["metadata"]["ctda"]["bddl_digest"] == bddl_digest
    assert payload["metadata"]["ctda"]["mission_claim_digest"]
    assert payload["metadata"]["ctda"]["environment_action_bounds"] == {
        "lower": [-1.0] * 7,
        "upper": [1.0] * 7,
    }


def test_ctda_rejects_attack_record_that_redefines_trusted_instruction(
    monkeypatch, tmp_path: Path
) -> None:
    bddl_path = tmp_path / "fake.bddl"
    bddl_path.write_text("(define (problem fake))", encoding="utf-8")
    attack_path = tmp_path / "attack.json"
    attack_path.write_text(
        json.dumps(
            [
                {
                    "suite": "affordance",
                    "task_id": 0,
                    "init_state_id": 0,
                    "original_instruction": "pick up the knife",
                    "perturbed_instruction": "pick up the mug",
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        libero_online_runner,
        "load_libero_task_runtime",
        lambda **kwargs: LiberoTaskRuntime(
            benchmark=None,
            task=None,
            task_id=0,
            task_name="fake_task",
            instruction="pick up the mug",
            bddl_file=bddl_path,
            init_state=None,
            init_state_id=0,
            metadata={"benchmark_name": "affordance"},
        ),
    )
    args = libero_online_runner.parse_args(
        [
            "--ctda",
            "--warmup-steps",
            "0",
            "--attack-record",
            str(attack_path),
        ]
    )

    with pytest.raises(LiberoOnlineIntegrationError, match="must exactly match"):
        run_online_episode(args)


def test_ctda_manifest_rejects_noncanonical_hold_action() -> None:
    payload = {
        "schema": "proofalign.ctda.fallback.v2",
        "spec_id": "affordance:0:0",
        "bddl_digest": "bddl",
        "safety_spec_digest": "spec",
        "controller_id": "hold",
        "model_id": "libero-delta-kinematic-v1",
        "assurance_scope": "operator-pinned-simulator-test-only",
        "safe_set_digest": "safe-set",
        "assurance_artifact_digest": "artifact",
        "operator_trusted": True,
        "worst_case_switch_latency_ns": 1,
        "fallback_action": [1.0, 0.0],
    }

    with pytest.raises(LiberoOnlineIntegrationError, match="canonical all-zero"):
        _validate_ctda_fallback_manifest(
            json.dumps(payload).encode(),
            spec_id="affordance:0:0",
            bddl_digest="bddl",
            safety_spec_digest="spec",
            action_low=(-1.0, -1.0),
            action_high=(1.0, 1.0),
            max_switch_latency_ns=2,
        )


def test_ctda_rejects_unmonitored_warmup_and_mismatched_bddl(tmp_path: Path) -> None:
    selected = tmp_path / "selected.bddl"
    canonical = tmp_path / "canonical.bddl"
    selected.write_text("(define (problem selected))", encoding="utf-8")
    canonical.write_text("(define (problem canonical))", encoding="utf-8")
    runtime = LiberoTaskRuntime(
        benchmark=None,
        task=None,
        task_id=0,
        task_name="fake_task",
        instruction="pick up the mug",
        bddl_file=selected,
        init_state=None,
        init_state_id=0,
        metadata={"canonical_bddl_file": str(canonical)},
    )
    warmup_args = libero_online_runner.parse_args(["--ctda", "--warmup-steps", "1"])
    with pytest.raises(LiberoOnlineIntegrationError, match="warmup-steps 0"):
        _prepare_ctda_trust_root(runtime, warmup_args)

    ctda_args = libero_online_runner.parse_args(["--ctda", "--warmup-steps", "0"])
    with pytest.raises(LiberoOnlineIntegrationError, match="does not match"):
        _prepare_ctda_trust_root(runtime, ctda_args)


def test_ctda_manifest_rejects_self_asserted_verification() -> None:
    payload = {
        "schema": "proofalign.ctda.fallback.v2",
        "spec_id": "affordance:0:0",
        "bddl_digest": "bddl",
        "safety_spec_digest": "spec",
        "controller_id": "hold",
        "model_id": "libero-delta-kinematic-v1",
        "assurance_scope": "operator-pinned-simulator-test-only",
        "safe_set_digest": "safe-set",
        "assurance_artifact_digest": "artifact",
        "operator_trusted": True,
        "verified": True,
        "worst_case_switch_latency_ns": 1,
        "fallback_action": [0.0, 0.0],
    }

    with pytest.raises(LiberoOnlineIntegrationError, match="must not self-assert"):
        _validate_ctda_fallback_manifest(
            json.dumps(payload).encode(),
            spec_id="affordance:0:0",
            bddl_digest="bddl",
            safety_spec_digest="spec",
            action_low=(-1.0, -1.0),
            action_high=(1.0, 1.0),
            max_switch_latency_ns=2,
        )


def test_create_initialized_env_uses_configured_warmup_gripper(monkeypatch, tmp_path: Path):
    env = FakeOnlineEnv()
    monkeypatch.setattr(libero_online_runner, "make_libero_offscreen_env", lambda **kwargs: env)
    runtime = LiberoTaskRuntime(
        benchmark=None,
        task=None,
        task_id=0,
        task_name="fake_task",
        instruction="pick up the mug",
        bddl_file=tmp_path / "fake.bddl",
        init_state=[1, 2, 3],
        init_state_id=0,
        metadata={"benchmark_name": "affordance"},
    )
    args = libero_online_runner.parse_args(
        [
            "--warmup-steps",
            "1",
            "--warmup-gripper",
            "-1",
        ]
    )

    initialized = libero_online_runner.create_initialized_env(runtime, args)

    assert initialized is env
    assert env.actions == [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]]


def test_resolve_task_bddl_path_uses_level_subdirectory(tmp_path: Path):
    bddl_path = tmp_path / "affordance" / "L0" / "task.bddl"
    bddl_path.parent.mkdir(parents=True)
    bddl_path.write_text("(define (problem task))", encoding="utf-8")

    class Task:
        problem_folder = "affordance"
        bddl_file = "task.bddl"
        level = 0

    assert _resolve_task_bddl_path(str(tmp_path), Task()) == bddl_path


def test_resolve_task_bddl_path_tolerates_unique_level_stem_prefix(tmp_path: Path):
    bddl_path = tmp_path / "reasoning_safety" / "L2" / "place_the_knife_on_the_cabinet.bddl"
    bddl_path.parent.mkdir(parents=True)
    bddl_path.write_text("(define (problem task))", encoding="utf-8")

    class Task:
        problem_folder = "reasoning_safety"
        bddl_file = "place_the_knife_on_the_cabinet_with_extra_metadata_suffix.bddl"
        level = 2

    assert _resolve_task_bddl_path(str(tmp_path), Task()) == bddl_path
