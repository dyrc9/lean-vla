from __future__ import annotations

import os
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from proofalign.action_abstraction import action_from_dict
from proofalign.benchmark.libero_online_wrapper import LiberoOnlineIntegrationError
from proofalign.models import Action, ActionKind, ExecutionStep, Pose, SafetySpec, WorldState


DEFAULT_CACHE_DIR = "/data0/ldx/huggingface"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
DEFAULT_OPENVLA_OFT_ROOT = "external/openvla-oft"
DEFAULT_OFT_MODEL = "moojink/openvla-7b-oft-finetuned-libero-spatial"
DEFAULT_OFT_UNNORM_KEY = "libero_spatial_no_noops"


def create_policy(**kwargs: Any) -> "OpenVLAPolicy":
    """Factory used by scripts/run_libero_online.py --policy.

    The default backend is OpenVLA-OFT because the published checkpoint is
    already fine-tuned for LIBERO-style 7D control and has an official LIBERO
    inference path. Set backend="hf_openvla" for the generic Hugging Face
    OpenVLA predict_action API.
    """

    return OpenVLAPolicy(OpenVLAConfig.from_kwargs(kwargs))


def create_abstractor(**kwargs: Any) -> "LiberoVLAActionAbstractor":
    """Factory used by scripts/run_libero_online.py --abstractor."""

    return LiberoVLAActionAbstractor(**kwargs)


@dataclass(frozen=True)
class OpenVLAConfig:
    backend: str = "openvla_oft"
    model_id: str = DEFAULT_OFT_MODEL
    unnorm_key: str = DEFAULT_OFT_UNNORM_KEY
    cache_dir: str = DEFAULT_CACHE_DIR
    hf_endpoint: str | None = DEFAULT_HF_ENDPOINT
    openvla_oft_root: str = DEFAULT_OPENVLA_OFT_ROOT
    device: str = "cuda:0"
    torch_dtype: str = "bfloat16"
    trust_remote_code: bool = True
    load_in_8bit: bool = False
    load_in_4bit: bool = False
    center_crop: bool = True
    num_images_in_input: int = 2
    use_proprio: bool = True
    use_l1_regression: bool = True
    use_diffusion: bool = False
    num_diffusion_steps_train: int = 50
    num_diffusion_steps_inference: int = 50
    use_film: bool = False
    lora_rank: int = 32
    open_loop_steps: int | None = None
    prompt_template: str = "In: What action should the robot take to {instruction}?\nOut:"
    image_key: str | None = None
    wrist_image_key: str | None = None
    state_key: str | None = None

    @classmethod
    def from_kwargs(cls, kwargs: dict[str, Any]) -> "OpenVLAConfig":
        data = dict(kwargs)
        if "pretrained_checkpoint" in data and "model_id" not in data:
            data["model_id"] = data.pop("pretrained_checkpoint")
        return cls(**data)


@dataclass
class OpenVLAPolicy:
    config: OpenVLAConfig
    _loaded: bool = False
    _pending_actions: deque[list[float]] = field(default_factory=deque)
    _model: Any = None
    _processor: Any = None
    _action_head: Any = None
    _proprio_projector: Any = None
    _oft_cfg: Any = None

    def reset_episode(self) -> None:
        self._pending_actions.clear()

    def __call__(self, instruction: str, observation: Any, history: list[ExecutionStep]) -> dict[str, Any]:
        if self._pending_actions:
            raw_action = self._pending_actions.popleft()
        else:
            raw_actions = self.predict_actions(instruction, observation)
            if not raw_actions:
                raise LiberoOnlineIntegrationError("OpenVLA returned no actions")
            raw_action = raw_actions[0]
            self._pending_actions.extend(raw_actions[1:])
        return {
            "raw_action": raw_action,
            "proofalign_action": heuristic_contract_from_instruction(instruction),
            "vla_metadata": {
                "backend": self.config.backend,
                "model_id": self.config.model_id,
                "unnorm_key": self.config.unnorm_key,
                "history_len": len(history),
            },
        }

    def predict_actions(self, instruction: str, observation: Any) -> list[list[float]]:
        self._load()
        if self.config.backend == "openvla_oft":
            return self._predict_oft(instruction, observation)
        if self.config.backend == "hf_openvla":
            return self._predict_hf_openvla(instruction, observation)
        raise LiberoOnlineIntegrationError(f"Unsupported VLA backend: {self.config.backend!r}")

    def _load(self) -> None:
        if self._loaded:
            return
        _configure_cache(self.config.cache_dir, self.config.hf_endpoint)
        if self.config.backend == "openvla_oft":
            self._load_oft()
        elif self.config.backend == "hf_openvla":
            self._load_hf_openvla()
        else:
            raise LiberoOnlineIntegrationError(f"Unsupported VLA backend: {self.config.backend!r}")
        self._loaded = True

    def _load_oft(self) -> None:
        _ensure_openvla_oft_importable(self.config.openvla_oft_root)
        try:
            from experiments.robot.openvla_utils import (
                get_action_head,
                get_processor,
                get_proprio_projector,
                get_vla,
            )
            from prismatic.vla.constants import NUM_ACTIONS_CHUNK, PROPRIO_DIM
        except Exception as exc:  # pragma: no cover - depends on external OpenVLA-OFT checkout.
            raise LiberoOnlineIntegrationError(
                "OpenVLA-OFT backend requires the moojink/openvla-oft checkout on PYTHONPATH. "
                "Clone it under this repository's external/openvla-oft or another code workspace, "
                "install its environment, then run with PYTHONPATH=/path/to/openvla-oft:$PYTHONPATH. "
                "Keep only large shared caches such as model weights under /data0/ldx."
            ) from exc

        open_loop_steps = self.config.open_loop_steps or NUM_ACTIONS_CHUNK
        self._oft_cfg = SimpleNamespace(
            model_family="openvla",
            pretrained_checkpoint=self.config.model_id,
            use_l1_regression=self.config.use_l1_regression,
            use_diffusion=self.config.use_diffusion,
            num_diffusion_steps_train=self.config.num_diffusion_steps_train,
            num_diffusion_steps_inference=self.config.num_diffusion_steps_inference,
            use_film=self.config.use_film,
            lora_rank=self.config.lora_rank,
            num_images_in_input=self.config.num_images_in_input,
            use_proprio=self.config.use_proprio,
            load_in_8bit=self.config.load_in_8bit,
            load_in_4bit=self.config.load_in_4bit,
            center_crop=self.config.center_crop,
            num_open_loop_steps=open_loop_steps,
            unnorm_key=self.config.unnorm_key,
        )
        self._model = get_vla(self._oft_cfg)
        self._processor = get_processor(self._oft_cfg)
        self._action_head = get_action_head(self._oft_cfg, llm_dim=self._model.llm_dim)
        self._proprio_projector = get_proprio_projector(
            self._oft_cfg,
            llm_dim=self._model.llm_dim,
            proprio_dim=PROPRIO_DIM,
        )

    def _load_hf_openvla(self) -> None:
        try:
            import torch
            from transformers import AutoModelForVision2Seq, AutoProcessor
        except Exception as exc:  # pragma: no cover - dependency-sensitive.
            raise LiberoOnlineIntegrationError(
                "Generic OpenVLA backend requires torch and a transformers version with "
                "AutoModelForVision2Seq. Install the OpenVLA/OpenVLA-OFT requirements first."
            ) from exc

        dtype = _torch_dtype(torch, self.config.torch_dtype)
        self._processor = AutoProcessor.from_pretrained(
            self.config.model_id,
            trust_remote_code=self.config.trust_remote_code,
            cache_dir=self.config.cache_dir,
        )
        self._model = AutoModelForVision2Seq.from_pretrained(
            self.config.model_id,
            torch_dtype=dtype,
            low_cpu_mem_usage=True,
            trust_remote_code=self.config.trust_remote_code,
            cache_dir=self.config.cache_dir,
        )
        if self.config.device:
            self._model = self._model.to(self.config.device)

    def _predict_oft(self, instruction: str, observation: Any) -> list[list[float]]:
        try:
            from experiments.robot.openvla_utils import get_vla_action
            from prismatic.vla.constants import PROPRIO_DIM
        except Exception as exc:  # pragma: no cover - loaded with external OpenVLA-OFT.
            raise LiberoOnlineIntegrationError("OpenVLA-OFT helpers are not importable.") from exc

        obs = make_oft_observation(
            observation,
            instruction,
            image_key=self.config.image_key,
            wrist_image_key=self.config.wrist_image_key,
            state_key=self.config.state_key,
            proprio_dim=PROPRIO_DIM,
        )
        actions = get_vla_action(
            self._oft_cfg,
            self._model,
            self._processor,
            obs,
            instruction,
            self._action_head,
            self._proprio_projector,
        )
        return _normalize_action_output(actions)

    def _predict_hf_openvla(self, instruction: str, observation: Any) -> list[list[float]]:
        import torch

        image = extract_image(observation, self.config.image_key)
        prompt = self.config.prompt_template.format(instruction=instruction)
        try:
            inputs = self._processor(prompt, image, return_tensors="pt")
        except TypeError:
            inputs = self._processor(prompt, image)
        inputs = _move_inputs(inputs, self.config.device, _torch_dtype(torch, self.config.torch_dtype))
        with torch.inference_mode():
            action = self._model.predict_action(
                **inputs,
                unnorm_key=self.config.unnorm_key,
                do_sample=False,
            )
        return _normalize_action_output(action)


@dataclass
class LiberoVLAActionAbstractor:
    """Map a VLA control chunk to a conservative ProofAlign contract."""

    gripper_close_threshold: float = -0.2
    near_object_distance: float = 0.12
    default_part: str = "body"
    safe_tool_part: str = "handle"
    contract_key: str = "proofalign_action"

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
        del observation, spec, history
        if isinstance(raw_action, dict) and isinstance(raw_action.get(self.contract_key), dict):
            base = dict(raw_action[self.contract_key])
        else:
            base = heuristic_contract_from_instruction(instruction)

        resolved = self._resolve_contract(base, raw_action, state)
        return action_from_dict(resolved)

    def _resolve_contract(self, contract: dict[str, Any], raw_action: Any, state: WorldState) -> dict[str, Any]:
        kind = str(contract.get("type", contract.get("kind", ""))).lower()
        if kind in {"reject", "stop"}:
            return contract

        obj_id = resolve_object_id(str(contract.get("object") or ""), state)
        if obj_id:
            contract["object"] = obj_id

        if kind in {"pick", "grasp"}:
            if not self._should_emit_terminal_pick(raw_action, obj_id, state):
                return self._move_contract(contract, obj_id, state)
            contract.setdefault("part", self._safe_part_for_object(obj_id, state))
            return contract

        if kind in {"place", "put"} and obj_id and state.gripper_holding != obj_id:
            return self._move_contract(contract, obj_id, state)

        return contract

    def _move_contract(self, contract: dict[str, Any], obj_id: str | None, state: WorldState) -> dict[str, Any]:
        pose = state.objects[obj_id].pose.to_dict() if obj_id in state.objects else {"x": 0.0, "y": 0.0, "z": 0.0}
        move = {
            "type": "MoveTo",
            "object": obj_id or contract.get("object"),
            "pose": pose,
            "metadata": {"source_contract": contract},
        }
        if contract.get("region"):
            move["region"] = contract["region"]
        return move

    def _should_emit_terminal_pick(self, raw_action: Any, obj_id: str | None, state: WorldState) -> bool:
        if not obj_id or obj_id not in state.objects:
            return False
        if state.robot_pose.distance_to(state.objects[obj_id].pose) > self.near_object_distance:
            return False
        gripper = _last_scalar(env_action_from_policy_output(raw_action))
        return gripper is not None and gripper <= self.gripper_close_threshold

    def _safe_part_for_object(self, obj_id: str | None, state: WorldState) -> str:
        obj = state.objects.get(obj_id or "")
        if not obj:
            return self.default_part
        for part in obj.parts.values():
            if part.name == self.safe_tool_part and part.safe_to_grasp and not part.dangerous:
                return part.name
        for part in obj.parts.values():
            if part.safe_to_grasp and not part.dangerous:
                return part.name
        return self.default_part


def heuristic_contract_from_instruction(instruction: str) -> dict[str, Any]:
    text = instruction.lower()
    if text.startswith("do not ") or any(word in text for word in ("stab", "hurt", "harm", "attack", "smash")):
        return {"type": "Reject", "metadata": {"source": "instruction_heuristic"}}

    obj = first_known_object(text) or "object"
    region = first_known_region(text)
    if any(word in text for word in ("place", "put", "deliver", "bring", "pass", "onto", "inside", "in the")):
        return {"type": "Place", "object": obj, "region": region, "metadata": {"source": "instruction_heuristic"}}
    if any(word in text for word in ("move", "push")):
        return {
            "type": "MoveTo",
            "object": obj,
            "region": region,
            "pose": {"x": 0.0, "y": 0.0, "z": 0.0},
            "metadata": {"source": "instruction_heuristic"},
        }
    if any(word in text for word in ("pick", "grab", "grasp", "retrieve", "get", "pour")):
        part = "blade" if "blade" in text else "handle"
        return {"type": "Pick", "object": obj, "part": part, "metadata": {"source": "instruction_heuristic"}}
    return {"type": "Stop", "metadata": {"source": "instruction_heuristic"}}


def make_oft_observation(
    observation: Any,
    instruction: str,
    *,
    image_key: str | None,
    wrist_image_key: str | None,
    state_key: str | None,
    proprio_dim: int,
) -> dict[str, Any]:
    import numpy as np

    return {
        "full_image": extract_image(observation, image_key, as_pil=False),
        "wrist_image": extract_image(observation, wrist_image_key, prefer_wrist=True, as_pil=False),
        "state": np.asarray(extract_proprio(observation, state_key, proprio_dim), dtype=np.float64),
        "task_description": instruction,
    }


def extract_image(
    observation: Any,
    key: str | None = None,
    *,
    prefer_wrist: bool = False,
    as_pil: bool = True,
) -> Any:
    if not isinstance(observation, dict):
        return _to_pil_image(observation) if as_pil else _to_numpy_image(observation)
    keys = []
    if key:
        keys.append(key)
    keys.extend(
        ["robot0_eye_in_hand_image", "wrist_image"] if prefer_wrist else ["agentview_image", "full_image"]
    )
    keys.extend(["image", "rgb", "pixels"])
    for candidate in keys:
        if candidate in observation:
            return _to_pil_image(observation[candidate]) if as_pil else _to_numpy_image(observation[candidate])
    raise LiberoOnlineIntegrationError(f"Could not find image in observation keys: {sorted(observation)}")


def extract_proprio(observation: Any, key: str | None, dim: int) -> list[float]:
    if not isinstance(observation, dict):
        return [0.0] * dim
    values: list[float] = []
    if key and key in observation:
        values.extend(_flatten_numbers(observation[key]))
    for candidate in ("robot0_eef_pos", "robot0_eef_quat", "robot0_gripper_qpos", "robot0_gripper_qvel"):
        if candidate in observation:
            values.extend(_flatten_numbers(observation[candidate]))
    if len(values) < dim:
        values.extend([0.0] * (dim - len(values)))
    return values[:dim]


def env_action_from_policy_output(raw_action: Any) -> Any:
    if isinstance(raw_action, dict) and "raw_action" in raw_action:
        return raw_action["raw_action"]
    return raw_action


def resolve_object_id(name: str, state: WorldState) -> str | None:
    if not name:
        return None
    if name in state.objects:
        return name
    key = _name_key(name)
    for obj in state.objects.values():
        if _name_key(obj.object_id) == key or _name_key(obj.kind) == key:
            return obj.object_id
    for obj in state.objects.values():
        obj_key = _name_key(obj.object_id)
        kind_key = _name_key(obj.kind)
        if key and (key in obj_key or key in kind_key or kind_key in key):
            return obj.object_id
    return None


def first_known_object(text: str) -> str | None:
    names = (
        "knife",
        "scissors",
        "hammer",
        "fork",
        "mug",
        "bowl",
        "banana",
        "apple",
        "soda_can",
        "soda can",
        "plate",
        "book",
        "frypan",
        "moka_pot",
        "moka pot",
        "vase",
        "ketchup",
        "milk",
        "butter",
        "cream_cheese",
        "cream cheese",
        "alphabet_soup",
        "alphabet soup",
    )
    for name in names:
        if name in text:
            return name.replace(" ", "_")
    return None


def first_known_region(text: str) -> str:
    for region in ("target_region", "plate", "basket", "stove", "microwave", "cabinet", "cutting_board", "drawer"):
        if region.replace("_", " ") in text or region in text:
            return region
    return "target_region"


def _normalize_action_output(actions: Any) -> list[list[float]]:
    try:
        import numpy as np

        if isinstance(actions, np.ndarray):
            actions = actions.tolist()
    except Exception:
        pass
    if hasattr(actions, "detach"):
        actions = actions.detach().cpu().tolist()
    if isinstance(actions, tuple):
        actions = list(actions)
    if not isinstance(actions, list):
        raise LiberoOnlineIntegrationError(f"VLA action output has unsupported type: {type(actions).__name__}")
    if not actions:
        return []
    if all(isinstance(value, (int, float)) for value in actions):
        return [[float(value) for value in actions]]
    return [[float(value) for value in _flatten_numbers(action)] for action in actions]


def _move_inputs(inputs: Any, device: str, dtype: Any) -> Any:
    if hasattr(inputs, "to"):
        try:
            return inputs.to(device=device, dtype=dtype)
        except TypeError:
            return inputs.to(device)
    if isinstance(inputs, dict):
        moved = {}
        for key, value in inputs.items():
            if hasattr(value, "to"):
                kwargs = {"device": device}
                if getattr(value, "is_floating_point", lambda: False)():
                    kwargs["dtype"] = dtype
                moved[key] = value.to(**kwargs)
            else:
                moved[key] = value
        return moved
    return inputs


def _to_pil_image(value: Any) -> Any:
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:  # pragma: no cover - pillow/numpy are external deps.
        raise LiberoOnlineIntegrationError("Image observations require pillow and numpy.") from exc
    if isinstance(value, Image.Image):
        return value
    array = np.asarray(value)
    if array.ndim == 3 and array.shape[0] in {1, 3, 4} and array.shape[-1] not in {1, 3, 4}:
        array = np.moveaxis(array, 0, -1)
    if array.dtype != np.uint8:
        array = array.clip(0, 255).astype(np.uint8)
    return Image.fromarray(array)


def _to_numpy_image(value: Any) -> Any:
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:  # pragma: no cover - pillow/numpy are external deps.
        raise LiberoOnlineIntegrationError("Image observations require pillow and numpy.") from exc
    if isinstance(value, Image.Image):
        array = np.asarray(value.convert("RGB"))
    else:
        array = np.asarray(value)
    if array.ndim == 3 and array.shape[0] in {1, 3, 4} and array.shape[-1] not in {1, 3, 4}:
        array = np.moveaxis(array, 0, -1)
    if array.dtype != np.uint8:
        array = array.clip(0, 255).astype(np.uint8)
    if array.ndim == 2:
        array = np.repeat(array[..., None], 3, axis=-1)
    if array.shape[-1] == 4:
        array = array[..., :3]
    return array


def _flatten_numbers(value: Any) -> list[float]:
    if hasattr(value, "detach"):
        value = value.detach().cpu().tolist()
    try:
        import numpy as np

        if isinstance(value, np.ndarray):
            value = value.tolist()
    except Exception:
        pass
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


def _last_scalar(value: Any) -> float | None:
    flat = _flatten_numbers(value)
    return flat[-1] if flat else None


def _name_key(name: str) -> str:
    key = re.sub(r"__?\d+", "", name.lower())
    key = key.replace("_", "")
    return re.sub(r"[^a-z0-9]", "", key)


def _configure_cache(cache_dir: str, hf_endpoint: str | None = None) -> None:
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", cache_dir)
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(Path(cache_dir) / "hub"))
        os.environ.setdefault("TRANSFORMERS_CACHE", str(Path(cache_dir) / "transformers"))
    if hf_endpoint:
        os.environ.setdefault("HF_ENDPOINT", hf_endpoint)


def _ensure_openvla_oft_importable(root: str) -> None:
    path = Path(root)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise LiberoOnlineIntegrationError(
            f"OpenVLA-OFT checkout not found at {path}. Clone the code into external/openvla-oft "
            "or set policy config openvla_oft_root to its checkout path."
        )
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

    # This project exposes experiments.libero_vla_plugin, while OpenVLA-OFT also
    # exposes experiments.robot. Extend the already-imported package path so both
    # modules can coexist under the same top-level namespace.
    local_experiments = sys.modules.get("experiments")
    external_experiments = path / "experiments"
    if local_experiments is not None and external_experiments.exists():
        package_path = getattr(local_experiments, "__path__", None)
        if package_path is not None and str(external_experiments) not in package_path:
            package_path.append(str(external_experiments))


def _torch_dtype(torch: Any, name: str) -> Any:
    return {
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }.get(name.lower(), torch.bfloat16)


__all__ = [
    "LiberoVLAActionAbstractor",
    "OpenVLAConfig",
    "OpenVLAPolicy",
    "create_abstractor",
    "create_policy",
    "extract_image",
    "extract_proprio",
    "heuristic_contract_from_instruction",
    "make_oft_observation",
]
