from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from experiments.libero_vla_plugin import heuristic_contract_from_instruction
from proofalign.models import ExecutionStep


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OPENPI_ROOT = REPO_ROOT / "external" / "openpi"
DEFAULT_CHECKPOINT_DIR = Path("/data0/ldx/libero_safety_models/pi05_libero_safety")


def create_policy(**kwargs: Any) -> "OpenPIPolicy":
    return OpenPIPolicy(OpenPIConfig.from_kwargs(kwargs))


@dataclass(frozen=True)
class OpenPIConfig:
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR
    openpi_config: str = "pi05_libero"
    openpi_root: Path = DEFAULT_OPENPI_ROOT
    resize_size: int = 224
    sample_steps: int = 10
    max_actions_per_call: int = 5
    hf_home: str = "/data0/ldx/huggingface"
    hf_endpoint: str = "https://hf-mirror.com"

    @classmethod
    def from_kwargs(cls, kwargs: dict[str, Any]) -> "OpenPIConfig":
        data = dict(kwargs)
        for key in ("checkpoint_dir", "openpi_root"):
            if key in data:
                data[key] = Path(data[key])
        return cls(**data)


@dataclass
class OpenPIPolicy:
    config: OpenPIConfig
    _loaded: bool = False
    _policy: Any = None
    _image_tools: Any = None

    def reset_episode(self) -> None:
        return None

    def __call__(self, instruction: str, observation: Any, history: list[ExecutionStep]) -> dict[str, Any]:
        del history
        self._load()
        element = self._prepare_element(observation, instruction)
        action_chunk = self._policy.infer(element)["actions"]
        actions = _normalize_action_chunk(action_chunk)
        if not actions:
            raise RuntimeError("OpenPI policy returned no actions.")
        return {
            "raw_action": actions[: self.config.max_actions_per_call],
            "proofalign_action": heuristic_contract_from_instruction(instruction),
            "vla_metadata": {
                "backend": "openpi",
                "checkpoint": str(self.config.checkpoint_dir),
                "openpi_config": self.config.openpi_config,
                "sample_steps": self.config.sample_steps,
                "max_actions_per_call": self.config.max_actions_per_call,
            },
        }

    def _load(self) -> None:
        if self._loaded:
            return
        _configure_paths(self.config)
        from openpi.shared import normalize as openpi_normalize
        from openpi.training import config as openpi_config
        from openpi.policies import policy_config
        from openpi_client import image_tools

        if not self.config.checkpoint_dir.exists():
            raise RuntimeError(f"Checkpoint directory does not exist: {self.config.checkpoint_dir}")
        config = openpi_config.get_config(self.config.openpi_config)
        norm_stats = _load_checkpoint_norm_stats(self.config.checkpoint_dir, openpi_normalize)
        self._policy = policy_config.create_trained_policy(
            config,
            self.config.checkpoint_dir,
            sample_kwargs={"num_steps": self.config.sample_steps},
            norm_stats=norm_stats,
        )
        self._image_tools = image_tools
        self._loaded = True

    def _prepare_element(self, obs: dict[str, Any], prompt: str) -> dict[str, Any]:
        if not isinstance(obs, dict):
            raise RuntimeError(f"OpenPI LIBERO policy expected dict observation, got {type(obs).__name__}.")
        image_tools = self._image_tools
        resize_size = self.config.resize_size
        base_image = np.ascontiguousarray(obs["agentview_image"][::-1, ::-1])
        wrist_image = np.ascontiguousarray(obs["robot0_eye_in_hand_image"][::-1, ::-1])
        base_image = image_tools.convert_to_uint8(image_tools.resize_with_pad(base_image, resize_size, resize_size))
        wrist_image = image_tools.convert_to_uint8(image_tools.resize_with_pad(wrist_image, resize_size, resize_size))
        state = np.concatenate(
            (
                obs["robot0_eef_pos"],
                _quat2axisangle(obs["robot0_eef_quat"]),
                obs["robot0_gripper_qpos"],
            )
        )
        return {
            "observation/image": base_image,
            "observation/wrist_image": wrist_image,
            "observation/state": state,
            "prompt": str(prompt),
        }


def _configure_paths(config: OpenPIConfig) -> None:
    if not config.openpi_root.exists():
        raise RuntimeError(f"OpenPI checkout not found: {config.openpi_root}")
    for path in (config.openpi_root / "src", config.openpi_root / "packages" / "openpi-client" / "src"):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    os.environ.setdefault("HF_ENDPOINT", config.hf_endpoint)
    os.environ.setdefault("HF_HOME", config.hf_home)
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(Path(config.hf_home) / "hub"))


def _load_checkpoint_norm_stats(checkpoint_dir: Path, openpi_normalize: Any) -> Any | None:
    default_path = checkpoint_dir / "assets" / "physical-intelligence" / "libero" / "norm_stats.json"
    if default_path.exists():
        return None
    released_path = checkpoint_dir / "assets" / "lerobot"
    if (released_path / "norm_stats.json").exists():
        return openpi_normalize.load(released_path)
    return None


def _quat2axisangle(quat: Any) -> np.ndarray:
    quat = np.asarray(quat, dtype=np.float64).copy()
    quat[3] = np.clip(quat[3], -1.0, 1.0)
    den = np.sqrt(1.0 - quat[3] * quat[3])
    if math.isclose(float(den), 0.0):
        return np.zeros(3)
    return (quat[:3] * 2.0 * math.acos(float(quat[3])) / den).astype(np.float32)


def _normalize_action_chunk(actions: Any) -> list[list[float]]:
    if isinstance(actions, np.ndarray):
        actions = actions.tolist()
    if hasattr(actions, "detach"):
        actions = actions.detach().cpu().tolist()
    if not isinstance(actions, list):
        raise RuntimeError(f"OpenPI action output has unsupported type: {type(actions).__name__}")
    if not actions:
        return []
    if all(isinstance(value, (int, float)) for value in actions):
        return [[float(value) for value in actions]]
    return [[float(value) for value in _flatten_numbers(action)] for action in actions]


def _flatten_numbers(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu().tolist()
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        items: list[float] = []
        for key in sorted(value):
            items.extend(_flatten_numbers(value[key]))
        return items
    if isinstance(value, (list, tuple)):
        items = []
        for item in value:
            items.extend(_flatten_numbers(item))
        return items
    return []
