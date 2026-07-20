from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import subprocess
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EDPA_ROOT = REPO_ROOT / "external" / "EDPA_attack_defense"
EDPA_COMMIT = "0c9959796380e0b429df4f1d21db01a888c3f115"
PLUGIN_SCHEMA = "proofalign.edpa-fixed-patch-transform.v1"
UPSTREAM_SOURCE_SHA256 = {
    "VLAAttacker/jax/EDPA.py": "fb04e0ad25d73ecb1b12a62f9b5810533043f5f13291d10fcbd1da873ef0d239",
    "cp_pi0.py": "7c87d66e914f810806f7735c30b54eec9ba2d80f7745a52b2a4c6e8cfd0db430",
    "eval/simulation/Libero/pi0.py": "f358933f45aa8d93570c292089e70f6af48fc1bf6a6b09fb8d5ff9f981a8dc87",
    "utils/pi0/__init__.py": "ea75537f398dff7dbf32accfec8499c6f2ea46b1ec99ca3f628b10a0d500622e",
}


@dataclass(frozen=True)
class EDPAPatchConfig:
    patch_path: Path
    patch_sha256: str
    camera: str
    position: tuple[int, int]
    edpa_root: Path = DEFAULT_EDPA_ROOT
    expected_commit: str = EDPA_COMMIT
    verify_upstream: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "patch_path", Path(self.patch_path))
        object.__setattr__(self, "edpa_root", Path(self.edpa_root))


class EDPAPatchTransform:
    """Apply one frozen EDPA patch at one preregistered camera position.

    EDPA's released LIBERO evaluator samples a patch position once per episode
    and then reuses it for every policy frame.  The experiment orchestrator
    freezes that sampled position in advance and constructs one transform per
    camera and episode.
    """

    def __init__(self, config: EDPAPatchConfig):
        self.config = config
        self._patch: np.ndarray | None = None
        self._patch_uint8: np.ndarray | None = None
        self._checkout_commit: str | None = None

    def __call__(self, image: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        self._load()
        clean = _validate_image(image)
        assert self._patch is not None and self._patch_uint8 is not None
        top, left = self.config.position
        _, patch_height, patch_width = self._patch.shape
        height, width, _ = clean.shape
        if top < 0 or left < 0 or top + patch_height > height or left + patch_width > width:
            raise RuntimeError(
                "EDPA patch position does not fit the camera frame: "
                f"position={(top, left)} patch={(patch_height, patch_width)} "
                f"frame={(height, width)}"
            )

        attacked = clean.copy()
        attacked[top : top + patch_height, left : left + patch_width, :] = np.transpose(
            self._patch_uint8, (1, 2, 0)
        )
        clean_digest = _array_sha256(clean)
        attacked_digest = _array_sha256(attacked)
        return attacked, {
            "schema": PLUGIN_SCHEMA,
            "attack_type": "edpa_fixed_patch",
            "camera": self.config.camera,
            "position_top_left": [top, left],
            "patch_shape_chw": list(self._patch.shape),
            "patch_dtype": str(self._patch.dtype),
            "patch_min": float(self._patch.min()),
            "patch_max": float(self._patch.max()),
            "patch_path": str(self.config.patch_path),
            "patch_sha256": self.config.patch_sha256,
            "clean_frame_sha256": clean_digest,
            "attacked_frame_sha256": attacked_digest,
            "frame_shape": list(clean.shape),
            "frame_dtype": str(clean.dtype),
            "changed": clean_digest != attacked_digest,
            "mean_absolute_delta": float(
                np.mean(np.abs(attacked.astype(np.int16) - clean.astype(np.int16)))
            ),
            "upstream_repository": "https://github.com/trustmlyoungscientist/EDPA_attack_defense",
            "upstream_commit": EDPA_COMMIT,
            "checkout_commit": self._checkout_commit,
            "source_sha256": dict(UPSTREAM_SOURCE_SHA256),
        }

    def _load(self) -> None:
        if self._patch is not None:
            return
        config = self.config
        if config.camera not in {"agentview", "robot0_eye_in_hand"}:
            raise RuntimeError(f"Unsupported EDPA camera: {config.camera}")
        if not config.patch_path.is_file():
            raise RuntimeError(f"EDPA patch is missing: {config.patch_path}")
        observed_patch_digest = _file_sha256(config.patch_path)
        if observed_patch_digest != config.patch_sha256:
            raise RuntimeError(
                "EDPA patch digest mismatch: "
                f"expected {config.patch_sha256}, got {observed_patch_digest}"
            )

        patch = np.load(config.patch_path, allow_pickle=False)
        if patch.ndim != 3 or patch.shape[0] != 3:
            raise RuntimeError(f"EDPA patch must have CHW shape with three channels: {patch.shape}")
        if patch.shape[1] <= 0 or patch.shape[2] <= 0:
            raise RuntimeError(f"EDPA patch spatial dimensions are empty: {patch.shape}")
        if not np.issubdtype(patch.dtype, np.floating):
            raise RuntimeError(f"EDPA patch must use a floating dtype: {patch.dtype}")
        if not np.isfinite(patch).all() or float(patch.min()) < 0.0 or float(patch.max()) > 1.0:
            raise RuntimeError("EDPA patch values must be finite and lie in [0, 1]")

        checkout_commit = _git_head(config.edpa_root)
        if config.verify_upstream:
            if checkout_commit != config.expected_commit:
                raise RuntimeError(
                    f"EDPA checkout commit mismatch: expected {config.expected_commit}, got {checkout_commit}"
                )
            for relative, expected in UPSTREAM_SOURCE_SHA256.items():
                observed = _file_sha256(config.edpa_root / relative)
                if observed != expected:
                    raise RuntimeError(
                        f"EDPA source digest mismatch for {relative}: expected {expected}, got {observed}"
                    )

        contiguous = np.ascontiguousarray(patch)
        self._patch = contiguous
        self._patch_uint8 = np.clip(contiguous * 255.0, 0.0, 255.0).astype(np.uint8)
        self._checkout_commit = checkout_commit


def _validate_image(image: Any) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        raise RuntimeError("EDPA camera image must be a numpy array")
    if image.ndim != 3 or image.shape[2] != 3:
        raise RuntimeError(f"EDPA camera image must have HWC RGB shape: {image.shape}")
    if image.dtype != np.uint8:
        raise RuntimeError(f"EDPA camera image must use uint8: {image.dtype}")
    return np.ascontiguousarray(image)


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"Required EDPA source is missing: {path}")
    return sha256(path.read_bytes()).hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    return sha256(np.ascontiguousarray(value).tobytes(order="C")).hexdigest()


def _git_head(path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Cannot read EDPA checkout HEAD: {completed.stderr.strip()}")
    return completed.stdout.strip()
