"""Outcome-blind adapter from victim traces to executed ActionBlock prefixes.

The existing LIBERO runner stores the original policy-chunk digest plus every
raw action actually consumed from that chunk.  It does not store the unused
tail.  This adapter therefore exports the exact executed prefix as the research
ActionBlock and preserves the original chunk digest only as source provenance.
It never reads reward, success, cost, collision, or future observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from proofalign.digests import digest_payload
from proofalign.integrity_models import ActionProposal


TRACE_ADAPTER_ID = "proofalign-executed-action-block-prefix-adapter"
TRACE_ADAPTER_VERSION = "1"
TRACE_SOURCE_SCHEMA = "proofalign.native-action-block-trace.v1"


class ActionBlockTraceError(ValueError):
    """Raised when a victim trace cannot be adapted without outcome leakage."""


def _require_sha256(value: Any, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ActionBlockTraceError(f"{name} is not a lowercase SHA-256 digest")
    return value


def _finite_action(value: Any, *, name: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ActionBlockTraceError(f"{name} must be a numeric sequence")
    try:
        action = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ActionBlockTraceError(f"{name} is not numeric") from exc
    # ActionProposal performs the finite/non-empty check.
    return action


@dataclass(frozen=True)
class NativeActionBlockRecord:
    proposal: ActionProposal
    policy_call_index: int
    action_count: int
    action_dimension: int
    source_policy_action_chunk_sha256: str
    policy_observation_binding_digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "adapter_id": TRACE_ADAPTER_ID,
            "adapter_version": TRACE_ADAPTER_VERSION,
            "policy_call_index": self.policy_call_index,
            "action_count": self.action_count,
            "action_dimension": self.action_dimension,
            "source_policy_action_chunk_sha256": (
                self.source_policy_action_chunk_sha256
            ),
            "policy_observation_binding_digest": (
                self.policy_observation_binding_digest
            ),
            "action_block": {
                **self.proposal.payload(),
                "command": list(self.proposal.command),
                "action_block_digest": self.proposal.action_block_digest,
            },
        }


def adapt_victim_episode(
    payload: Mapping[str, Any],
    *,
    episode_nonce: str,
    proposed_at_origin_ns: int = 1,
) -> dict[str, Any]:
    """Extract exact consumed prefixes without consulting episode outcomes."""

    if not episode_nonce:
        raise ActionBlockTraceError("episode_nonce must be non-empty")
    trace = payload.get("trace")
    if not isinstance(trace, list) or not trace:
        raise ActionBlockTraceError("victim trace is empty")

    groups: list[tuple[Mapping[str, Any], list[tuple[float, ...]]]] = []
    current_audit: Mapping[str, Any] | None = None
    current_actions: list[tuple[float, ...]] = []
    for row_index, row in enumerate(trace):
        if not isinstance(row, Mapping) or row.get("phase") != "policy":
            continue
        policy_call = row.get("policy_call")
        if policy_call is not None:
            if not isinstance(policy_call, Mapping):
                raise ActionBlockTraceError(
                    f"trace[{row_index}].policy_call is not an object"
                )
            if current_audit is not None:
                groups.append((current_audit, current_actions))
            current_audit = policy_call
            current_actions = []
        if current_audit is None:
            raise ActionBlockTraceError(
                "policy action appears before its policy-call audit"
            )
        current_actions.append(
            _finite_action(row.get("raw_action"), name=f"trace[{row_index}].raw_action")
        )
    if current_audit is not None:
        groups.append((current_audit, current_actions))
    if not groups:
        raise ActionBlockTraceError("victim trace contains no policy ActionBlock")

    records: list[NativeActionBlockRecord] = []
    for proposal_index, (audit, actions) in enumerate(groups):
        call_index = audit.get("policy_call_index")
        if type(call_index) is not int or call_index != proposal_index:
            raise ActionBlockTraceError("policy-call indices are not contiguous")
        source_digest = _require_sha256(
            audit.get("policy_action_chunk_sha256"),
            name="policy action chunk digest",
        )
        _require_sha256(
            audit.get("attacked_frame_sha256"),
            name="policy observation frame digest",
        )
        if not actions:
            raise ActionBlockTraceError("policy call has no consumed action")
        dimensions = {len(action) for action in actions}
        if len(dimensions) != 1:
            raise ActionBlockTraceError("action dimension changes within a prefix")
        observation_payload = {
            "policy_call_index": call_index,
            "clean_frame_sha256": audit.get("clean_frame_sha256"),
            "attacked_frame_sha256": audit.get("attacked_frame_sha256"),
            "clean_wrist_frame_sha256": audit.get("clean_wrist_frame_sha256"),
            "attacked_wrist_frame_sha256": audit.get("attacked_wrist_frame_sha256"),
            "observation_attack_type": audit.get("attack_type"),
            "observation_changed": audit.get("changed"),
        }
        observation_digest = digest_payload(observation_payload)
        proposal = ActionProposal(
            episode_nonce=episode_nonce,
            proposal_index=proposal_index,
            proposed_at_ns=proposed_at_origin_ns + proposal_index,
            observation_digest=observation_digest,
            state_epoch=proposal_index,
            command=tuple(value for action in actions for value in action),
            command_shape=(len(actions), dimensions.copy().pop()),
        )
        records.append(
            NativeActionBlockRecord(
                proposal=proposal,
                policy_call_index=call_index,
                action_count=len(actions),
                action_dimension=dimensions.pop(),
                source_policy_action_chunk_sha256=source_digest,
                policy_observation_binding_digest=observation_digest,
            )
        )

    return {
        "schema": TRACE_SOURCE_SCHEMA,
        "adapter_id": TRACE_ADAPTER_ID,
        "adapter_version": TRACE_ADAPTER_VERSION,
        "episode_nonce": episode_nonce,
        "outcome_fields_read": [],
        "unused_policy_chunk_tail_reconstructed": False,
        "action_blocks": [record.payload() for record in records],
    }


__all__ = [
    "ActionBlockTraceError",
    "NativeActionBlockRecord",
    "TRACE_ADAPTER_ID",
    "TRACE_ADAPTER_VERSION",
    "TRACE_SOURCE_SCHEMA",
    "adapt_victim_episode",
]
