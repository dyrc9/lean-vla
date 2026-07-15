from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from scripts.run_liberosafety_pi05_openpi_eval import (
    frame_digest,
    make_trace_record,
    prepare_openpi_element,
)


IMAGE_TOOLS = SimpleNamespace(
    convert_to_uint8=lambda value: value,
    resize_with_pad=lambda value, _height, _width: value,
)


def observation() -> dict:
    return {
        "agentview_image": np.arange(8 * 8 * 3, dtype=np.uint8).reshape(8, 8, 3),
        "robot0_eye_in_hand_image": np.zeros((8, 8, 3), dtype=np.uint8),
        "robot0_eef_pos": np.zeros(3),
        "robot0_eef_quat": np.asarray([0.0, 0.0, 0.0, 1.0]),
        "robot0_gripper_qpos": np.zeros(2),
    }


def test_clean_policy_input_records_unchanged_frame_digest() -> None:
    element, replay, audit = prepare_openpi_element(
        observation(), "pick up the mug", IMAGE_TOOLS, 224
    )

    assert audit["attack_type"] == "none"
    assert audit["changed"] is False
    assert audit["clean_frame_sha256"] == audit["attacked_frame_sha256"]
    assert frame_digest(replay) == audit["clean_frame_sha256"]
    assert np.array_equal(element["observation/image"], replay)


def test_attacked_policy_input_preserves_pre_attack_digest() -> None:
    def transform(clean: np.ndarray):
        attacked = np.full_like(clean, 255)
        return attacked, {
            "schema": "fixture",
            "attack_type": "laser_blinding",
            "attack_strength": "strong",
            "clean_frame_sha256": frame_digest(clean),
            "attacked_frame_sha256": frame_digest(attacked),
            "changed": True,
        }

    element, replay, audit = prepare_openpi_element(
        observation(),
        "pick up the mug",
        IMAGE_TOOLS,
        224,
        observation_transform=transform,
    )

    assert audit["changed"] is True
    expected_clean = np.ascontiguousarray(observation()["agentview_image"][::-1, ::-1])
    assert audit["clean_frame_sha256"] == frame_digest(expected_clean)
    assert audit["attacked_frame_sha256"] == frame_digest(element["observation/image"])
    assert np.array_equal(replay, element["observation/image"])


def test_trace_record_embeds_policy_call_audit_only_on_replan_step() -> None:
    audit = {"policy_call_index": 0, "changed": True}
    record = make_trace_record(10, "policy", [0.0] * 7, 0.0, False, {}, 0.5, 0.1, audit)
    continuation = make_trace_record(11, "policy", [0.0] * 7, 0.0, False, {}, 0.0, 0.1)

    assert record["policy_call"] == audit
    assert "policy_call" not in continuation
