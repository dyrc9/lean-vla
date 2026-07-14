from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.phantom_menace_plugin import (
    ATTACK_PARAMETERS,
    LOCAL_PATCH_COMMIT,
    UPSTREAM_COMMIT,
    PhantomMenaceConfig,
    PhantomMenaceObservationTransform,
    upstream_manifest,
)


def _image() -> np.ndarray:
    y, x = np.mgrid[0:32, 0:32]
    return np.stack((x * 8, y * 8, (x + y) * 4), axis=-1).astype(np.uint8)


@pytest.mark.parametrize("attack_type", sorted(ATTACK_PARAMETERS))
@pytest.mark.parametrize("strength", ["weak", "medium", "strong"])
def test_frozen_upstream_transforms_are_deterministic_and_auditable(attack_type, strength):
    transform = PhantomMenaceObservationTransform(
        PhantomMenaceConfig(attack_type=attack_type, attack_strength=strength)
    )

    first, first_record = transform(_image())
    second, second_record = transform(_image())

    assert np.array_equal(first, second)
    assert first_record == second_record
    assert first_record["upstream_commit"] == UPSTREAM_COMMIT
    assert first_record["checkout_commit"] == LOCAL_PATCH_COMMIT
    assert first_record["changed"] is True
    assert first_record["clean_frame_sha256"] != first_record["attacked_frame_sha256"]
    assert first.shape == _image().shape
    assert first.dtype == np.uint8


def test_transform_rejects_missing_upstream_source_before_use(tmp_path: Path):
    transform = PhantomMenaceObservationTransform(
        PhantomMenaceConfig(
            attack_type="em_truncation",
            repo_root=tmp_path,
        )
    )

    with pytest.raises(RuntimeError, match="source is missing"):
        transform(_image())


def test_upstream_manifest_matches_frozen_checkout():
    manifest = upstream_manifest()

    assert manifest["upstream_commit"] == UPSTREAM_COMMIT
    assert manifest["checkout_commit"] == manifest["expected_checkout_commit"] == LOCAL_PATCH_COMMIT
    assert len(manifest["source_sha256"]) == 4
