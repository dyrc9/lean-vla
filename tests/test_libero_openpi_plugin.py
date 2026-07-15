from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from experiments.libero_openpi_plugin import OpenPIConfig, OpenPIPolicy, _normalize_action_chunk


def test_openpi_config_coerces_paths():
    config = OpenPIConfig.from_kwargs(
        {
            "checkpoint_dir": "/tmp/checkpoint",
            "openpi_root": "/tmp/openpi",
            "phantom_menace_root": "/tmp/phantom",
            "max_actions_per_call": 3,
        }
    )

    assert config.checkpoint_dir == Path("/tmp/checkpoint")
    assert config.openpi_root == Path("/tmp/openpi")
    assert config.phantom_menace_root == Path("/tmp/phantom")
    assert config.max_actions_per_call == 3


def test_normalize_action_chunk_handles_numpy_arrays():
    actions = np.asarray([[1, 2, 3], [4, 5, 6]], dtype=np.float32)

    assert _normalize_action_chunk(actions) == [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]


def test_openpi_policy_resets_rng_between_shared_batch_episodes():
    policy = OpenPIPolicy(OpenPIConfig())
    policy._loaded = True
    policy._initial_rng = "episode-seed"
    policy._policy = SimpleNamespace(_rng="advanced-seed")
    policy._policy_call_index = 7

    policy.reset_episode()

    assert policy._policy._rng == "episode-seed"
    assert policy._policy_call_index == 0


def test_openpi_policy_logs_complete_chunk_and_stable_call_id(monkeypatch):
    policy = OpenPIPolicy(OpenPIConfig(max_actions_per_call=2))
    policy._loaded = True
    policy._policy = SimpleNamespace(
        infer=lambda _element: {
            "actions": np.asarray(
                [[0.1] * 7, [0.2] * 7, [0.3] * 7], dtype=np.float32
            )
        }
    )
    monkeypatch.setattr(policy, "_prepare_element", lambda _obs, _prompt: {})

    result = policy("pick up the mug", {}, [])

    assert result["policy_call_id"] == "openpi:000000"
    assert len(result["policy_action_chunk"]) == 3
    assert result["raw_action"] == result["policy_action_chunk"][:2]
    assert policy("pick up the mug", {}, [])["policy_call_id"] == "openpi:000001"


def test_openpi_policy_records_observation_attack(monkeypatch):
    policy = OpenPIPolicy(OpenPIConfig(observation_attack_type="em_truncation"))
    policy._loaded = True
    policy._policy = SimpleNamespace(infer=lambda _element: {"actions": np.asarray([[0.1] * 7])})
    attack_record = {"schema": "test", "clean_frame_sha256": "clean", "attacked_frame_sha256": "attack"}

    def prepare(_obs, _prompt):
        policy._last_observation_attack = attack_record
        return {}

    monkeypatch.setattr(policy, "_prepare_element", prepare)

    result = policy("pick up the mug", {}, [])

    assert result["vla_metadata"]["observation_attack_type"] == "em_truncation"
    assert result["vla_metadata"]["observation_attack"] == {
        **attack_record,
        "policy_call_index": 0,
    }


def test_openpi_policy_records_clean_frame_audit(monkeypatch):
    policy = OpenPIPolicy(OpenPIConfig(observation_attack_type="none"))
    policy._loaded = True
    policy._image_tools = SimpleNamespace(
        convert_to_uint8=lambda value: value,
        resize_with_pad=lambda value, _height, _width: value,
    )
    policy._policy = SimpleNamespace(
        infer=lambda _element: {"actions": np.asarray([[0.1] * 7])}
    )
    obs = {
        "agentview_image": np.zeros((8, 8, 3), dtype=np.uint8),
        "robot0_eye_in_hand_image": np.zeros((8, 8, 3), dtype=np.uint8),
        "robot0_eef_pos": np.zeros(3),
        "robot0_eef_quat": np.asarray([0.0, 0.0, 0.0, 1.0]),
        "robot0_gripper_qpos": np.zeros(2),
    }

    result = policy("pick up the mug", obs, [])
    audit = result["vla_metadata"]["observation_attack"]

    assert audit["attack_type"] == "none"
    assert audit["changed"] is False
    assert audit["clean_frame_sha256"] == audit["attacked_frame_sha256"]
    assert audit["policy_call_index"] == 0
