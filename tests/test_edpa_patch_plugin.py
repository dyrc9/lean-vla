from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from experiments.edpa_patch_plugin import (
    EDPA_COMMIT,
    EDPAPatchConfig,
    EDPAPatchTransform,
    PLUGIN_SCHEMA,
)


def _patch(tmp_path: Path, value: float = 1.0) -> tuple[Path, str]:
    path = tmp_path / "patch.npy"
    np.save(path, np.full((3, 4, 5), value, dtype=np.float32))
    return path, sha256(path.read_bytes()).hexdigest()


def _image() -> np.ndarray:
    y, x = np.mgrid[0:12, 0:14]
    return np.stack((x * 5, y * 7, x + y), axis=-1).astype(np.uint8)


def test_fixed_patch_is_deterministic_and_auditable(tmp_path: Path) -> None:
    path, digest = _patch(tmp_path)
    transform = EDPAPatchTransform(
        EDPAPatchConfig(
            patch_path=path,
            patch_sha256=digest,
            camera="agentview",
            position=(2, 3),
        )
    )

    first, first_record = transform(_image())
    second, second_record = transform(_image())

    assert np.array_equal(first, second)
    assert first_record == second_record
    assert first_record["schema"] == PLUGIN_SCHEMA
    assert first_record["upstream_commit"] == EDPA_COMMIT
    assert first_record["checkout_commit"] == EDPA_COMMIT
    assert first_record["patch_sha256"] == digest
    assert first_record["position_top_left"] == [2, 3]
    assert first_record["changed"] is True
    assert np.all(first[2:6, 3:8] == 255)
    assert np.array_equal(first[:2], _image()[:2])


def test_patch_digest_and_numeric_domain_fail_closed(tmp_path: Path) -> None:
    path, digest = _patch(tmp_path)
    bad_digest = EDPAPatchTransform(
        EDPAPatchConfig(
            patch_path=path,
            patch_sha256="0" * 64,
            camera="agentview",
            position=(0, 0),
        )
    )
    with pytest.raises(RuntimeError, match="patch digest mismatch"):
        bad_digest(_image())

    invalid_path, invalid_digest = _patch(tmp_path, value=1.5)
    invalid = EDPAPatchTransform(
        EDPAPatchConfig(
            patch_path=invalid_path,
            patch_sha256=invalid_digest,
            camera="agentview",
            position=(0, 0),
        )
    )
    with pytest.raises(RuntimeError, match=r"lie in \[0, 1\]"):
        invalid(_image())


def test_patch_must_fit_preregistered_position(tmp_path: Path) -> None:
    path, digest = _patch(tmp_path)
    transform = EDPAPatchTransform(
        EDPAPatchConfig(
            patch_path=path,
            patch_sha256=digest,
            camera="robot0_eye_in_hand",
            position=(10, 10),
        )
    )

    with pytest.raises(RuntimeError, match="does not fit"):
        transform(_image())
