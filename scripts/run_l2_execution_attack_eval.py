#!/usr/bin/env python3
"""Successor runner for source-grounded L2 execution-attack experiments.

The frozen OpenPI/LIBERO runner is imported rather than edited so historical
source bindings and the active M2 path remain byte-identical.  This successor
injects an attack at the v4 dispatch boundary (semantic runtime) or at an
environment proxy (VLA-only), then appends a separate privileged attack audit
to each episode artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.execution_attack_relay import (  # noqa: E402
    AttackPlacement,
    PostBoundaryAffineAttackSink,
    PublishedAffineFamily,
    PublishedAffineRelay,
    build_published_affine_relay,
)
from proofalign.integrity_v4_runtime import (  # noqa: E402
    SingleUsePrefixDispatchBoundary,
)
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402


_BASE_RUN_EPISODE = base.run_episode
_BASE_PARSE_ARGS = base.parse_args
_BASE_COPY_SELF = base.copy_self


class _AttackedEnvironmentProxy:
    """Apply the attack after the base runner's common action clipping."""

    def __init__(
        self,
        env: Any,
        relay: PublishedAffineRelay,
        *,
        wait_steps: int,
    ) -> None:
        self._env = env
        self._relay = relay
        self._wait_steps = wait_steps
        self._call_index = 0

    def step(self, action: list[float]) -> Any:
        runner_step_id = self._call_index
        self._call_index += 1
        if runner_step_id < self._wait_steps:
            return self._env.step(action)
        env_input = self._relay.transform(
            action,
            runner_step_id=runner_step_id,
        )
        transition = self._env.step(list(env_input))
        reported = (
            action
            if self._relay.placement
            is AttackPlacement.POST_BOUNDARY_FORGED
            else env_input
        )
        self._relay.mark_dispatch_result(
            env_step_reached=True,
            reported_action=reported,
        )
        return transition

    def __getattr__(self, name: str) -> Any:
        return getattr(self._env, name)


def _attack_boundary_class(
    relay: PublishedAffineRelay,
    *,
    first_policy_step_id: int,
) -> type[SingleUsePrefixDispatchBoundary]:
    """Create an episode-local boundary without mutating the frozen source."""

    class L2AttackDispatchBoundary(SingleUsePrefixDispatchBoundary):
        def __init__(self, sink: Any) -> None:
            if relay.placement is not AttackPlacement.PRE_BOUNDARY:
                sink = PostBoundaryAffineAttackSink(
                    inner=sink,
                    relay=relay,
                    report_forged_nominal=(
                        relay.placement
                        is AttackPlacement.POST_BOUNDARY_FORGED
                    ),
                )
            super().__init__(sink)

        def dispatch_next(
            self,
            session: Any,
            action: tuple[float, ...],
            *,
            now_ns: int,
        ) -> Any:
            if relay.placement is not AttackPlacement.PRE_BOUNDARY:
                relay.bind_runner_step(
                    first_policy_step_id + len(relay.records)
                )
                return super().dispatch_next(
                    session,
                    action,
                    now_ns=now_ns,
                )
            attacked = relay.transform(
                action,
                runner_step_id=(
                    first_policy_step_id + len(relay.records)
                ),
            )
            result = super().dispatch_next(
                session,
                attacked,
                now_ns=now_ns,
            )
            relay.mark_dispatch_result(
                env_step_reached=result.transition is not None,
                reported_action=(
                    None
                    if result.receipt is None
                    else result.receipt.applied_action
                ),
            )
            return result

    return L2AttackDispatchBoundary


def _annotate_payload(
    payload: dict[str, Any],
    relay: PublishedAffineRelay | None,
) -> dict[str, Any]:
    metadata = dict(payload["metadata"])
    metadata.update(
        {
            "runner_variant": "proofalign_l2_execution_attack_successor_v1",
            "frozen_base_runner_modified": False,
            "execution_attack_family": (
                PublishedAffineFamily.NONE.value
                if relay is None
                else relay.scenario.family.value
            ),
            "execution_attack_placement": (
                None if relay is None else relay.placement.value
            ),
            "execution_attack_fidelity": (
                None
                if relay is None
                else "source_command_operator_transfer"
            ),
            "perfect_undetectability_claim_eligible": False,
            "measured_execution_value": "env.step input",
        }
    )
    payload["metadata"] = metadata
    payload["execution_attack_audit"] = (
        None if relay is None else relay.audit_payload()
    )

    if relay is not None:
        records_by_step = {
            record["runner_step_id"]: record
            for record in relay.records
            if record["env_step_reached"]
        }
        for row in payload.get("trace", []):
            record = records_by_step.get(row.get("step_id"))
            if record is not None:
                row["execution_attack"] = record

        if (
            relay.placement
            is AttackPlacement.POST_BOUNDARY_TRUTHFUL
            and payload.get("decision") == "env_done"
            and any(
                transaction.get("dispatch_status") == "rejected"
                for frame in payload.get(
                    "observation_frame_audits", ()
                )
                for transaction in (
                    frame.get("semantic_transaction") or {},
                )
            )
        ):
            # The frozen base runner gives terminal ``done`` precedence over a
            # same-step execution rejection.  The successor security decision
            # must preserve the rejection without rewriting historical code.
            payload["decision"] = "semantic_execution_rejected"
            payload["success_by_done"] = False
    return payload


def _persist_annotated_episode(payload: dict[str, Any]) -> None:
    path_text = payload.get("_path")
    if not path_text:
        return
    serializable = {
        key: value for key, value in payload.items() if key != "_path"
    }
    Path(path_text).write_text(
        json.dumps(serializable, indent=2, default=base.json_default),
        encoding="utf-8",
    )


def run_episode(**kwargs: Any) -> dict[str, Any]:
    """Run one base episode through an episode-local L2 attack boundary."""

    args = kwargs["args"]
    relay = build_published_affine_relay(
        family=getattr(
            args,
            "execution_attack_family",
            PublishedAffineFamily.NONE.value,
        ),
        placement=getattr(
            args,
            "execution_attack_placement",
            AttackPlacement.PRE_BOUNDARY.value,
        ),
    )
    if relay is None:
        payload = _BASE_RUN_EPISODE(**kwargs)
        _annotate_payload(payload, None)
        _persist_annotated_episode(payload)
        return payload

    original_boundary = base.SingleUsePrefixDispatchBoundary
    original_create_env = base.create_env
    if bool(getattr(args, "semantic_runtime", False)):
        base.SingleUsePrefixDispatchBoundary = _attack_boundary_class(
            relay,
            first_policy_step_id=int(args.num_steps_wait),
        )
    else:
        def attacked_create_env(*create_args: Any, **create_kwargs: Any) -> Any:
            return _AttackedEnvironmentProxy(
                original_create_env(*create_args, **create_kwargs),
                relay,
                wait_steps=int(args.num_steps_wait),
            )

        base.create_env = attacked_create_env
    try:
        payload = _BASE_RUN_EPISODE(**kwargs)
    finally:
        base.SingleUsePrefixDispatchBoundary = original_boundary
        base.create_env = original_create_env

    _annotate_payload(payload, relay)
    _persist_annotated_episode(payload)
    return payload


def parse_args() -> argparse.Namespace:
    if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
        print(
            "L2 successor options:\n"
            "  --execution-attack-family "
            "{none,ueda_blevins_scaling,ueda_blevins_reflection,"
            "ueda_blevins_shear}\n"
            "  --execution-attack-placement "
            "{pre_boundary,post_boundary_truthful,"
            "post_boundary_forged}\n"
        )
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--execution-attack-family",
        choices=[family.value for family in PublishedAffineFamily],
        default=PublishedAffineFamily.NONE.value,
    )
    parser.add_argument(
        "--execution-attack-placement",
        choices=[placement.value for placement in AttackPlacement],
        default=AttackPlacement.PRE_BOUNDARY.value,
    )
    l2_args, remaining = parser.parse_known_args()
    original_argv = sys.argv
    try:
        sys.argv = [original_argv[0], *remaining]
        args = _BASE_PARSE_ARGS()
    finally:
        sys.argv = original_argv
    args.execution_attack_family = l2_args.execution_attack_family
    args.execution_attack_placement = l2_args.execution_attack_placement
    return args


def copy_self(output_dir: Path) -> None:
    _BASE_COPY_SELF(output_dir)
    shutil.copy2(Path(__file__), output_dir / Path(__file__).name)


def main() -> None:
    original_parse_args = base.parse_args
    original_run_episode = base.run_episode
    original_copy_self = base.copy_self
    base.parse_args = parse_args
    base.run_episode = run_episode
    base.copy_self = copy_self
    try:
        base.main()
    finally:
        base.parse_args = original_parse_args
        base.run_episode = original_run_episode
        base.copy_self = original_copy_self


if __name__ == "__main__":
    main()
