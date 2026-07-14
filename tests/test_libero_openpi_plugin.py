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
            "max_actions_per_call": 3,
        }
    )

    assert config.checkpoint_dir == Path("/tmp/checkpoint")
    assert config.openpi_root == Path("/tmp/openpi")
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
