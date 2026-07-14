from __future__ import annotations

import hashlib
import importlib.util
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PHANTOM_ROOT = REPO_ROOT / "external" / "Phantom-Menace"
UPSTREAM_COMMIT = "a0e4c8b2a661ea2fe64bdb9055353b2e12575729"
LOCAL_PATCH_COMMIT = "9ceb030f0313ded029acedb1c5a8f76e57c654bc"
PLUGIN_VERSION = "proofalign.phantom-menace-observation-transform.v1"

# These hashes freeze the upstream implementations used by the adapter.  The
# functions are imported from that checkout at runtime; their algorithms are
# not copied into ProofAlign.
UPSTREAM_SHA256 = {
    "sensor_attacks/em_truncation.py": "3ec0b487ce240ef07b595341d3da9cafcf80ad83f218070a393c4af96d2eedbb",
    "sensor_attacks/laser_blinding.py": "ca45904b4ef05a70eb9b46296a442fb0670ed09ebaa8ee92cd968e7936fd2cb8",
    "sensor_attacks/patterns/red.png": "b6986054dc24900d573a610ca586bb77c72f522f9e6c4d43e9bcae83f31054f8",
    "sensor_attacks/ultrasound_blur.py": "fbf423cdb7c97d7e172efe45ad3641048921e343406720769a188395fa8e636e",
}

ATTACK_PARAMETERS: dict[str, dict[str, dict[str, Any]]] = {
    "laser_blinding": {
        "weak": {"alpha": 0.1},
        "medium": {"alpha": 0.5},
        "strong": {"alpha": 0.9},
    },
    "ultrasound_blur": {
        "weak": {"theta": 0, "dx": 5, "dy": 5, "S": 0},
        "medium": {"theta": 0, "dx": 10, "dy": 10, "S": 0},
        "strong": {"theta": 0, "dx": 20, "dy": 20, "S": 0},
    },
    "em_truncation": {
        "weak": {"truncate_ratio": 0.1},
        "medium": {"truncate_ratio": 0.2},
        "strong": {"truncate_ratio": 0.3},
    },
}


@dataclass(frozen=True)
class PhantomMenaceConfig:
    attack_type: str
    attack_strength: str = "medium"
    repo_root: Path = DEFAULT_PHANTOM_ROOT
    camera: str = "agentview"
    expected_commit: str = LOCAL_PATCH_COMMIT
    verify_upstream: bool = True

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> "PhantomMenaceConfig":
        if "repo_root" in kwargs:
            kwargs["repo_root"] = Path(kwargs["repo_root"])
        return cls(**kwargs)


class PhantomMenaceObservationTransform:
    def __init__(self, config: PhantomMenaceConfig):
        self.config = config
        self._apply: Callable[[np.ndarray], np.ndarray] | None = None
        self._source_paths: list[str] = []
        self._source_sha256: dict[str, str] = {}
        self._upstream_commit: str | None = None

    def __call__(self, image: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        self._load()
        clean = _validate_image(image, label="clean")
        assert self._apply is not None
        attacked = _validate_image(self._apply(clean.copy()), label="attacked")
        if attacked.shape != clean.shape:
            raise RuntimeError(
                f"Phantom Menace transform changed image shape: {clean.shape} -> {attacked.shape}."
            )
        record = {
            "schema": PLUGIN_VERSION,
            "upstream_commit": UPSTREAM_COMMIT,
            "checkout_commit": self._upstream_commit,
            "attack_type": self.config.attack_type,
            "attack_strength": self.config.attack_strength,
            "attack_parameters": ATTACK_PARAMETERS[self.config.attack_type][self.config.attack_strength],
            "camera": self.config.camera,
            "clean_frame_sha256": _array_sha256(clean),
            "attacked_frame_sha256": _array_sha256(attacked),
            "frame_shape": list(clean.shape),
            "frame_dtype": str(clean.dtype),
            "changed": not np.array_equal(clean, attacked),
            "mean_absolute_delta": float(
                np.mean(np.abs(attacked.astype(np.int16) - clean.astype(np.int16)))
            ),
            "source_paths": self._source_paths,
            "source_sha256": self._source_sha256,
        }
        return attacked, record

    def _load(self) -> None:
        if self._apply is not None:
            return
        config = self.config
        if config.camera != "agentview":
            raise RuntimeError("Phantom Menace R0 adapter only supports the upstream agentview camera.")
        if config.attack_type not in ATTACK_PARAMETERS:
            raise RuntimeError(f"Unsupported Phantom Menace attack: {config.attack_type}")
        if config.attack_strength not in ATTACK_PARAMETERS[config.attack_type]:
            raise RuntimeError(f"Unsupported attack strength: {config.attack_strength}")
        if not config.repo_root.is_dir():
            raise RuntimeError(f"Phantom Menace checkout not found: {config.repo_root}")

        source_paths = [f"sensor_attacks/{config.attack_type}.py"]
        if config.attack_type == "laser_blinding":
            source_paths.append("sensor_attacks/patterns/red.png")
        source_sha256 = {path: _file_sha256(config.repo_root / path) for path in source_paths}
        upstream_commit = _git_head(config.repo_root)
        if config.verify_upstream:
            if upstream_commit != config.expected_commit:
                raise RuntimeError(
                    f"Phantom Menace commit mismatch: expected {config.expected_commit}, got {upstream_commit}."
                )
            for path, digest in source_sha256.items():
                if digest != UPSTREAM_SHA256[path]:
                    raise RuntimeError(
                        f"Phantom Menace source digest mismatch for {path}: "
                        f"expected {UPSTREAM_SHA256[path]}, got {digest}."
                    )

        params = dict(ATTACK_PARAMETERS[config.attack_type][config.attack_strength])
        module = _load_module(config.repo_root / source_paths[0], config.attack_type)
        if config.attack_type == "laser_blinding":
            function = module.laser_blinding
            pattern_path = config.repo_root / "sensor_attacks" / "patterns" / "red.png"
            self._apply = lambda image: function(image, str(pattern_path), **params)
        elif config.attack_type == "ultrasound_blur":
            function = module.ultrasound_blur
            self._apply = lambda image: function(image, **params)
        else:
            function = module.em_truncation
            self._apply = lambda image: function(image, **params)
        self._source_paths = source_paths
        self._source_sha256 = source_sha256
        self._upstream_commit = upstream_commit


def upstream_manifest(repo_root: Path = DEFAULT_PHANTOM_ROOT) -> dict[str, Any]:
    repo_root = Path(repo_root)
    return {
        "repository": "https://github.com/ZJUshine/Phantom-Menace",
        "upstream_commit": UPSTREAM_COMMIT,
        "checkout_commit": _git_head(repo_root),
        "expected_checkout_commit": LOCAL_PATCH_COMMIT,
        "plugin_schema": PLUGIN_VERSION,
        "source_sha256": {
            path: _file_sha256(repo_root / path) for path in sorted(UPSTREAM_SHA256)
        },
    }


def _load_module(path: Path, label: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"proofalign_phantom_{label}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import Phantom Menace module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_image(image: Any, *, label: str) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        raise RuntimeError(f"Phantom Menace {label} image must be a numpy array.")
    if image.ndim != 3 or image.shape[2] != 3:
        raise RuntimeError(f"Phantom Menace {label} image must have shape HxWx3, got {image.shape}.")
    if image.dtype != np.uint8:
        raise RuntimeError(f"Phantom Menace {label} image must be uint8, got {image.dtype}.")
    return np.ascontiguousarray(image)


def _array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"Required Phantom Menace source is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
