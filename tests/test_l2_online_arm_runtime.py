from __future__ import annotations

from proofalign.benchmark.execution_attack_relay import (
    AttackPlacement,
    PostBoundaryAffineAttackSink,
    PublishedAffineFamily,
    build_published_affine_relay,
)
from proofalign.benchmark.l2_online_arm_runtime import (
    ExecutionOnlyPrefixAuthorization,
    ExecutionOnlyPrefixDispatchBoundary,
    execution_only_receipt_audit,
)
from proofalign.benchmark.libero_runtime import AuthorizedLiberoActionSink
from proofalign.digests import digest_text
from proofalign.integrity_v4_runtime import (
    AppliedAction,
    InMemoryActionSink,
    TransactionVerdict,
)


ACTIONS = (
    (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
    (0.2, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
)


def _authorization() -> ExecutionOnlyPrefixAuthorization:
    return ExecutionOnlyPrefixAuthorization(
        episode_nonce="execution-only-test",
        proposal_index=0,
        source_policy_chunk_digest=digest_text("source-chunk"),
        policy_observation_digest=digest_text("policy-observation"),
        actions=ACTIONS,
        issued_at_ns=10,
        valid_until_ns=100,
    )


def test_execution_only_exact_prefix_is_one_use_and_sealable() -> None:
    authorization = _authorization()
    sink = InMemoryActionSink()
    boundary = ExecutionOnlyPrefixDispatchBoundary(sink)
    opened = boundary.open(authorization, now_ns=11)
    assert opened.session is not None

    for index, action in enumerate(ACTIONS):
        result = boundary.dispatch_next(
            opened.session,
            action,
            now_ns=12 + index,
        )
        assert result.verdict is TransactionVerdict.ALLOW
        assert result.receipt is not None
        assert result.receipt.step_index == index
        assert execution_only_receipt_audit(result.receipt)[
            "receipt_digest"
        ]

    sealed = boundary.seal(
        opened.session,
        effects_known=True,
    )
    replay = boundary.open(authorization, now_ns=20)

    assert sealed.verdict is TransactionVerdict.ALLOW
    assert len(sink.applied) == 2
    assert replay.verdict is TransactionVerdict.REJECT


def test_execution_only_p1_substitution_is_rejected_before_sink() -> None:
    authorization = _authorization()
    sink = InMemoryActionSink()
    boundary = ExecutionOnlyPrefixDispatchBoundary(sink)
    opened = boundary.open(authorization, now_ns=11)
    assert opened.session is not None

    rejected = boundary.dispatch_next(
        opened.session,
        (0.4, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        now_ns=12,
    )

    assert rejected.verdict is TransactionVerdict.REJECT
    assert rejected.transition is None
    assert sink.applied == []


class _Environment:
    def __init__(self) -> None:
        self.applied: list[tuple[float, ...]] = []

    def step(self, action):
        frozen = tuple(float(value) for value in action)
        self.applied.append(frozen)
        return {"observation": len(self.applied)}, 0.0, False, {}


def test_execution_only_p2_truthful_detects_after_one_sink_step() -> None:
    authorization = _authorization()
    relay = build_published_affine_relay(
        family=PublishedAffineFamily.SCALING,
        placement=AttackPlacement.POST_BOUNDARY_TRUTHFUL,
    )
    assert relay is not None
    environment = _Environment()
    sink = PostBoundaryAffineAttackSink(
        inner=AuthorizedLiberoActionSink(environment),
        relay=relay,
        report_forged_nominal=False,
    )
    boundary = ExecutionOnlyPrefixDispatchBoundary(sink)
    opened = boundary.open(authorization, now_ns=11)
    assert opened.session is not None
    relay.bind_runner_step(0)

    rejected = boundary.dispatch_next(
        opened.session,
        ACTIONS[0],
        now_ns=12,
    )

    assert rejected.verdict is TransactionVerdict.REJECT
    assert rejected.transition is not None
    assert environment.applied[0][0] == 0.4
    assert relay.records[0]["env_step_reached"] is True
    assert boundary.seal(
        opened.session,
        effects_known=True,
    ).verdict is TransactionVerdict.REJECT


def test_execution_only_p3_forged_receipt_exposes_observer_limit() -> None:
    authorization = _authorization()
    relay = build_published_affine_relay(
        family=PublishedAffineFamily.SCALING,
        placement=AttackPlacement.POST_BOUNDARY_FORGED,
    )
    assert relay is not None
    environment = _Environment()
    sink = PostBoundaryAffineAttackSink(
        inner=AuthorizedLiberoActionSink(environment),
        relay=relay,
        report_forged_nominal=True,
    )
    boundary = ExecutionOnlyPrefixDispatchBoundary(sink)
    opened = boundary.open(authorization, now_ns=11)
    assert opened.session is not None
    relay.bind_runner_step(0)

    allowed = boundary.dispatch_next(
        opened.session,
        ACTIONS[0],
        now_ns=12,
    )

    assert allowed.verdict is TransactionVerdict.ALLOW
    assert allowed.receipt is not None
    assert allowed.receipt.reported_action == ACTIONS[0]
    assert environment.applied[0][0] == 0.4
    assert relay.records[0]["reported_action"] == ACTIONS[0]


def test_execution_only_sink_substitution_without_transition_is_rejected() -> None:
    class _SubstitutingSink:
        sink_id = "substituting-no-transition"

        def apply(self, action, *, now_ns):
            return AppliedAction(
                action=(action[0] * 2.0, *action[1:]),
                applied_at_ns=now_ns,
            )

    authorization = _authorization()
    boundary = ExecutionOnlyPrefixDispatchBoundary(
        _SubstitutingSink()
    )
    opened = boundary.open(authorization, now_ns=11)
    assert opened.session is not None

    rejected = boundary.dispatch_next(
        opened.session,
        ACTIONS[0],
        now_ns=12,
    )

    assert rejected.verdict is TransactionVerdict.REJECT
    assert rejected.receipt is not None
