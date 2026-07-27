from __future__ import annotations

import pytest

from proofalign.benchmark.execution_attack_relay import (
    AttackPlacement,
    ExecutionAttackError,
    PublishedAffineFamily,
    build_published_affine_relay,
    published_affine_scenario,
)


def test_scaling_uses_source_control_matrix_and_preserves_gripper() -> None:
    scenario = published_affine_scenario(PublishedAffineFamily.SCALING)

    transformed = scenario.apply_control_operator(
        (0.1, -0.2, 0.3, -0.4, 0.5, -0.6, -1.0)
    )

    assert transformed == (
        0.4,
        -0.8,
        1.2,
        -1.6,
        2.0,
        -2.4,
        -1.0,
    )
    assert scenario.source_control_matrix[0][0] == 4.0
    assert scenario.source_observable_matrix[0][0] == 0.25
    assert scenario.source_control_offset == (0.0,) * 6


def test_reflection_and_shear_match_published_su() -> None:
    reflection = published_affine_scenario(
        PublishedAffineFamily.REFLECTION
    )
    shear = published_affine_scenario(PublishedAffineFamily.SHEAR)
    action = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0.25)

    assert reflection.apply_control_operator(action) == (
        -1.0,
        -2.0,
        -3.0,
        -4.0,
        -5.0,
        -6.0,
        0.25,
    )
    assert shear.apply_control_operator(action) == (
        -3.0,
        4.0,
        -2.0,
        5.0,
        -1.0,
        6.0,
        0.25,
    )
    for row in range(6):
        for column in range(6):
            product = sum(
                shear.source_observable_matrix[row][inner]
                * shear.source_control_matrix[inner][column]
                for inner in range(6)
            )
            assert product == (1.0 if row == column else 0.0)


def test_relay_audit_forbids_perfect_undetectability_claim() -> None:
    relay = build_published_affine_relay(
        family=PublishedAffineFamily.SCALING,
        placement=AttackPlacement.PRE_BOUNDARY,
    )
    assert relay is not None

    env_input = relay.transform(
        (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        runner_step_id=9,
    )
    relay.mark_dispatch_result(
        env_step_reached=False,
        reported_action=None,
    )
    audit = relay.audit_payload()

    assert env_input[0] == 0.4
    assert audit["perfect_undetectability_claim_eligible"] is False
    assert audit["records"][0]["runner_step_id"] == 9
    assert audit["records"][0]["env_step_reached"] is False
    assert audit["records"][0]["adaptation"][
        "coordinated_observation_attack_implemented"
    ] is False
    assert audit["records"][0]["post_transform_clipping"] is False


def test_affine_transfer_rejects_non_libero_action_shapes() -> None:
    scenario = published_affine_scenario(PublishedAffineFamily.SCALING)

    with pytest.raises(ExecutionAttackError, match="7D LIBERO"):
        scenario.apply_control_operator((0.1,) * 6)


def test_none_builds_no_relay() -> None:
    assert (
        build_published_affine_relay(
            family=PublishedAffineFamily.NONE,
            placement=AttackPlacement.PRE_BOUNDARY,
        )
        is None
    )
