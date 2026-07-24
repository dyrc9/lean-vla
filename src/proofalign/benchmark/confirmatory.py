"""Outcome-blind contracts for the confirmatory and four-arm experiment line.

This module deliberately contains no simulator, policy, GPU, or network entry
point.  It turns the frozen preregistrations into exact execution identities
and validates artifacts produced by future runners.  Keeping these rules in a
small importable module lets unit tests exercise the denominator, replacement,
ordering, and fixed-trace invariants without observing an experimental outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from proofalign.digests import digest_payload
from proofalign.integrity_models import MethodArm


CONFIRMATORY_PREREGISTRATION_SCHEMA = (
    "proofalign.saber-confirmatory-preregistration.v1"
)
FOUR_ARM_PREREGISTRATION_SCHEMA = "proofalign.four-arm-causal-preregistration.v1"
ATTACK_RECORD_BUNDLE_SCHEMA = "proofalign.saber-confirmatory-record-bundle.v1"
FIXED_TRACE_BUNDLE_SCHEMA = "proofalign.four-arm-fixed-trace-bundle.v3"
FIXED_TRACE_RESULT_SCHEMA = "proofalign.four-arm-fixed-trace-result.v3"

ARM_ORDER = (
    MethodArm.VLA_ONLY,
    MethodArm.INTENT_ONLY,
    MethodArm.EXECUTION_ONLY,
    MethodArm.DUAL,
)
CONDITION_ORDER = ("clean", "attacked")


class ConfirmatoryContractError(ValueError):
    """Raised when a frozen design or future artifact violates its contract."""


@dataclass(frozen=True)
class ConfirmatoryUnit:
    base_pair_id: str
    unit_id: str
    suite: str
    level: int
    level_task_id: int
    task_id: int
    init_state_id: int
    trusted_instruction: str
    seed_block_id: str
    env_seed: int
    policy_seed: int

    def identity_payload(self) -> dict[str, Any]:
        return {
            "base_pair_id": self.base_pair_id,
            "unit_id": self.unit_id,
            "suite": self.suite,
            "level": self.level,
            "level_task_id": self.level_task_id,
            "task_id": self.task_id,
            "init_state_id": self.init_state_id,
            "trusted_instruction": self.trusted_instruction,
            "seed_block_id": self.seed_block_id,
            "env_seed": self.env_seed,
            "policy_seed": self.policy_seed,
        }

    def frozen_projection_payload(self) -> dict[str, Any]:
        """Return the exact projection hashed by the design freezer."""

        return {
            "unit_id": self.unit_id,
            "base_pair_id": self.base_pair_id,
            "suite": self.suite,
            "level": self.level,
            "task_id": self.task_id,
            "init_state_id": self.init_state_id,
            "block_id": self.seed_block_id,
            "env_seed": self.env_seed,
            "policy_seed": self.policy_seed,
        }


@dataclass(frozen=True)
class VictimEpisodeSpec:
    sequence_index: int
    condition: str
    unit: ConfirmatoryUnit

    @property
    def episode_id(self) -> str:
        return f"{self.condition}_{self.unit.unit_id}"


@dataclass(frozen=True)
class FourArmEpisodeSpec:
    sequence_index: int
    stage: str
    condition: str
    arm: MethodArm
    unit: ConfirmatoryUnit

    @property
    def episode_id(self) -> str:
        return (
            f"{self.stage}_{self.condition}_{self.arm.value}_{self.unit.unit_id}"
        )


def load_json_object(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfirmatoryContractError(f"cannot load JSON object {target}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfirmatoryContractError(f"JSON root is not an object: {target}")
    return value


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_confirmatory_preregistration(protocol: Mapping[str, Any]) -> None:
    if protocol.get("schema") != CONFIRMATORY_PREREGISTRATION_SCHEMA:
        raise ConfirmatoryContractError("unexpected confirmatory preregistration schema")
    if protocol.get("protocol_status") != "preregistered_design_frozen_execution_not_authorized":
        raise ConfirmatoryContractError("confirmatory design is not frozen")
    if protocol.get("outcomes_observed_for_this_population") is not False:
        raise ConfirmatoryContractError("confirmatory population is not outcome-blind")
    scope = _mapping(protocol.get("scope"), "scope")
    if scope.get("gpu_execution_authorized") is not False:
        raise ConfirmatoryContractError("design artifact unexpectedly authorizes GPU execution")
    producer = _mapping(protocol.get("attack_record_producer"), "attack_record_producer")
    expected_producer = {
        "required_record_count": 60,
        "one_generation_per_base_pair": True,
        "one_record_per_base_pair_shared_only_across_its_two_seed_replicates": True,
        "best_of_n_selection_allowed": False,
        "regeneration_or_replacement_allowed": False,
        "victim_rollout_or_outcome_visible_during_generation": False,
        "p0b_records_reused": False,
    }
    _require_values(producer, expected_producer, "attack_record_producer")
    stopping = _mapping(protocol.get("invalid_missing_and_stopping"), "invalid_missing_and_stopping")
    _require_values(
        stopping,
        {
            "failed_unit_or_seed_replacement_allowed": False,
            "invalid_episode_replacement_allowed": False,
            "partial_run_resumption_allowed": False,
            "threshold_or_population_revision_in_same_protocol_allowed": False,
        },
        "invalid_missing_and_stopping",
    )

    pairs = _object_list(protocol.get("frozen_base_pairs"), "frozen_base_pairs")
    if len(pairs) != 60:
        raise ConfirmatoryContractError("confirmatory design requires exactly 60 base pairs")
    identities = {
        (row.get("suite"), row.get("task_id"), row.get("init_state_id"))
        for row in pairs
    }
    pair_ids = {row.get("base_pair_id") for row in pairs}
    if len(identities) != 60 or len(pair_ids) != 60 or None in pair_ids:
        raise ConfirmatoryContractError("confirmatory base-pair identities are not unique")
    if digest_payload(pairs) != protocol.get("base_population_sha256"):
        raise ConfirmatoryContractError("confirmatory base-population digest changed")

    seed_blocks = _object_list(
        protocol.get("replicate_seed_blocks"), "replicate_seed_blocks"
    )
    if seed_blocks != [
        {"block_id": "seed_block_a", "env_seed": 43, "policy_seed": 11},
        {"block_id": "seed_block_b", "env_seed": 59, "policy_seed": 17},
    ]:
        raise ConfirmatoryContractError("confirmatory seed blocks changed")
    units = build_units(protocol, validate=False)
    if len(units) != 120 or len({unit.unit_id for unit in units}) != 120:
        raise ConfirmatoryContractError("confirmatory unit projection is not 120 unique units")
    if digest_payload([unit.frozen_projection_payload() for unit in units]) != protocol.get(
        "unit_population_sha256"
    ):
        raise ConfirmatoryContractError("confirmatory unit-population digest changed")


def validate_four_arm_preregistration(
    protocol: Mapping[str, Any],
    *,
    confirmatory_protocol: Mapping[str, Any],
    confirmatory_sha256: str | None = None,
) -> None:
    validate_confirmatory_preregistration(confirmatory_protocol)
    if protocol.get("schema") != FOUR_ARM_PREREGISTRATION_SCHEMA:
        raise ConfirmatoryContractError("unexpected four-arm preregistration schema")
    if protocol.get("protocol_status") != "preregistered_design_frozen_execution_not_authorized":
        raise ConfirmatoryContractError("four-arm design is not frozen")
    if protocol.get("outcomes_observed_for_this_four_arm_population") is not False:
        raise ConfirmatoryContractError("four-arm design is not outcome-blind")
    if _mapping(protocol.get("scope"), "scope").get("gpu_execution_authorized") is not False:
        raise ConfirmatoryContractError("four-arm design unexpectedly authorizes GPU execution")
    expected_arms = [
        {
            "arm": arm.value,
            "intent_action_enabled": arm.intent_enabled,
            "action_execution_enabled": arm.execution_enabled,
        }
        for arm in ARM_ORDER
    ]
    legacy_arms = [
        {
            "arm": arm.value,
            "intent_plan_enabled": arm.intent_enabled,
            "plan_execution_enabled": arm.execution_enabled,
        }
        for arm in ARM_ORDER
    ]
    if protocol.get("factorial_arms") not in (expected_arms, legacy_arms):
        raise ConfirmatoryContractError("four-arm treatment switches changed")
    contract = _mapping(protocol.get("shared_runner_contract"), "shared_runner_contract")
    if contract.get("only_treatment_switches") not in (
        ["intent_action_enabled", "action_execution_enabled"],
        ["intent_plan_enabled", "plan_execution_enabled"],
    ):
        raise ConfirmatoryContractError("shared runner permits non-factorial switches")
    stopping = _mapping(
        protocol.get("invalid_missing_and_stopping"),
        "invalid_missing_and_stopping",
    )
    _require_values(
        stopping,
        {
            "replacement_allowed": False,
            "resume_partial_root_allowed": False,
            "outcome_driven_arm_or_population_changes_allowed": False,
            "threshold_tuning_within_protocol_allowed": False,
        },
        "invalid_missing_and_stopping",
    )
    dependency = _mapping(protocol.get("dependency"), "dependency")
    bound = _mapping(
        dependency.get("confirmatory_protocol"), "dependency.confirmatory_protocol"
    )
    if bound.get("protocol_id") != confirmatory_protocol.get("protocol_id"):
        raise ConfirmatoryContractError("four-arm confirmatory protocol id differs")
    if confirmatory_sha256 is not None and bound.get("sha256") != confirmatory_sha256:
        raise ConfirmatoryContractError("four-arm confirmatory protocol digest differs")


def build_units(
    confirmatory_protocol: Mapping[str, Any],
    *,
    validate: bool = True,
) -> list[ConfirmatoryUnit]:
    if validate:
        validate_confirmatory_preregistration(confirmatory_protocol)
    pairs = _object_list(
        confirmatory_protocol.get("frozen_base_pairs"), "frozen_base_pairs"
    )
    blocks = _object_list(
        confirmatory_protocol.get("replicate_seed_blocks"),
        "replicate_seed_blocks",
    )
    units: list[ConfirmatoryUnit] = []
    for pair in pairs:
        for block in blocks:
            env_seed = _integer(block.get("env_seed"), "env_seed")
            policy_seed = _integer(block.get("policy_seed"), "policy_seed")
            base_pair_id = _text(pair.get("base_pair_id"), "base_pair_id")
            units.append(
                ConfirmatoryUnit(
                    base_pair_id=base_pair_id,
                    unit_id=f"{base_pair_id}_env{env_seed}_policy{policy_seed}",
                    suite=_text(pair.get("suite"), "suite"),
                    level=_integer(pair.get("level"), "level"),
                    level_task_id=_integer(
                        pair.get("level_task_id"), "level_task_id"
                    ),
                    task_id=_integer(pair.get("task_id"), "task_id"),
                    init_state_id=_integer(
                        pair.get("init_state_id"), "init_state_id"
                    ),
                    trusted_instruction=_text(
                        pair.get("trusted_instruction"), "trusted_instruction"
                    ),
                    seed_block_id=_text(block.get("block_id"), "block_id"),
                    env_seed=env_seed,
                    policy_seed=policy_seed,
                )
            )
    return units


def hash_balanced_units(
    confirmatory_protocol: Mapping[str, Any],
) -> list[ConfirmatoryUnit]:
    """Return base-pair-major units with a frozen hash-balanced seed order."""

    units = build_units(confirmatory_protocol)
    by_pair: dict[str, list[ConfirmatoryUnit]] = {}
    for unit in units:
        by_pair.setdefault(unit.base_pair_id, []).append(unit)
    ordered: list[ConfirmatoryUnit] = []
    for pair in _object_list(
        confirmatory_protocol.get("frozen_base_pairs"), "frozen_base_pairs"
    ):
        pair_id = _text(pair.get("base_pair_id"), "base_pair_id")
        pair_units = sorted(by_pair[pair_id], key=lambda item: item.seed_block_id)
        bit = sha256(
            f"{confirmatory_protocol['protocol_id']}:{pair_id}:seed-order-v1".encode(
                "utf-8"
            )
        ).digest()[0] & 1
        ordered.extend(pair_units if bit == 0 else reversed(pair_units))
    return ordered


def victim_episode_specs(
    confirmatory_protocol: Mapping[str, Any],
) -> list[VictimEpisodeSpec]:
    specs: list[VictimEpisodeSpec] = []
    for unit in hash_balanced_units(confirmatory_protocol):
        for condition in CONDITION_ORDER:
            specs.append(
                VictimEpisodeSpec(
                    sequence_index=len(specs) + 1,
                    condition=condition,
                    unit=unit,
                )
            )
    return specs


def latin_square_arm_order(
    *,
    protocol_id: str,
    unit_id: str,
    condition: str,
) -> tuple[MethodArm, ...]:
    """Assign one of four cyclic arm orders by a deterministic hash bucket."""

    if condition not in CONDITION_ORDER:
        raise ConfirmatoryContractError(f"unsupported condition: {condition}")
    bucket = int.from_bytes(
        sha256(
            f"{protocol_id}:{unit_id}:{condition}:arm-order-v1".encode("utf-8")
        ).digest()[:8],
        "big",
    ) % len(ARM_ORDER)
    return ARM_ORDER[bucket:] + ARM_ORDER[:bucket]


def four_arm_episode_specs(
    confirmatory_protocol: Mapping[str, Any],
    four_arm_protocol: Mapping[str, Any],
    *,
    stage: str,
    condition: str,
) -> list[FourArmEpisodeSpec]:
    validate_four_arm_preregistration(
        four_arm_protocol,
        confirmatory_protocol=confirmatory_protocol,
    )
    allowed = {
        "A_fixed_trace_shadow": False,
        "B_clean_closed_loop": True,
        "C_attacked_closed_loop": True,
    }
    if stage not in allowed:
        raise ConfirmatoryContractError(f"unsupported four-arm stage: {stage}")
    if (
        stage == "B_clean_closed_loop"
        and condition != "clean"
        or stage == "C_attacked_closed_loop"
        and condition != "attacked"
    ):
        raise ConfirmatoryContractError("four-arm stage/condition mismatch")
    specs: list[FourArmEpisodeSpec] = []
    for unit in hash_balanced_units(confirmatory_protocol):
        for arm in latin_square_arm_order(
            protocol_id=_text(four_arm_protocol.get("protocol_id"), "protocol_id"),
            unit_id=unit.unit_id,
            condition=condition,
        ):
            specs.append(
                FourArmEpisodeSpec(
                    sequence_index=len(specs) + 1,
                    stage=stage,
                    condition=condition,
                    arm=arm,
                    unit=unit,
                )
            )
    return specs


def producer_pairs(
    confirmatory_protocol: Mapping[str, Any],
) -> list[dict[str, Any]]:
    validate_confirmatory_preregistration(confirmatory_protocol)
    return [
        {
            "pair_id": row["base_pair_id"],
            "suite": row["suite"],
            "level": row["level"],
            "level_task_id": row["level_task_id"],
            "task_id": row["task_id"],
            "init_state_id": row["init_state_id"],
            "trusted_instruction": row["trusted_instruction"],
        }
        for row in confirmatory_protocol["frozen_base_pairs"]
    ]


def validate_attack_record_bundle(
    bundle: Mapping[str, Any],
    *,
    confirmatory_protocol: Mapping[str, Any],
    producer_protocol_sha256: str | None = None,
) -> list[dict[str, Any]]:
    validate_confirmatory_preregistration(confirmatory_protocol)
    if bundle.get("schema") != ATTACK_RECORD_BUNDLE_SCHEMA:
        raise ConfirmatoryContractError("unexpected confirmatory record-bundle schema")
    if bundle.get("confirmatory_protocol_id") != confirmatory_protocol.get(
        "protocol_id"
    ):
        raise ConfirmatoryContractError("record bundle binds another confirmatory design")
    if (
        producer_protocol_sha256 is not None
        and bundle.get("producer_protocol_sha256") != producer_protocol_sha256
    ):
        raise ConfirmatoryContractError("record bundle producer-protocol digest differs")
    if bundle.get("victim_outcomes_observed") is not False:
        raise ConfirmatoryContractError("record bundle generation observed victim outcomes")
    if bundle.get("generation_attempt_count") != 60:
        raise ConfirmatoryContractError("record bundle must record exactly 60 attempts")
    if bundle.get("replacement_attempt_count") != 0:
        raise ConfirmatoryContractError("record bundle contains replacement attempts")
    records = _object_list(bundle.get("records"), "records")
    pairs = producer_pairs(confirmatory_protocol)
    if len(records) != len(pairs):
        raise ConfirmatoryContractError("record bundle does not contain 60 records")
    seen: set[tuple[str, int, int]] = set()
    validated: list[dict[str, Any]] = []
    for sequence_index, (pair, record) in enumerate(
        zip(pairs, records, strict=True), 1
    ):
        identity = (
            str(record.get("suite")),
            _integer(record.get("task_id"), "record.task_id"),
            _integer(record.get("init_state_id"), "record.init_state_id"),
        )
        expected_identity = (
            pair["suite"],
            pair["task_id"],
            pair["init_state_id"],
        )
        if identity != expected_identity or identity in seen:
            raise ConfirmatoryContractError(
                f"record {sequence_index} identity/order differs from frozen population"
            )
        seen.add(identity)
        expected = {
            "original_instruction": pair["trusted_instruction"],
            "objective": "constraint_violation",
            "source": "official SABER exact-task prompt-tool producer",
        }
        _require_values(record, expected, f"records[{sequence_index - 1}]")
        perturbed = _text(
            record.get("perturbed_instruction"), "perturbed_instruction"
        )
        if perturbed == pair["trusted_instruction"]:
            raise ConfirmatoryContractError(
                f"record {sequence_index} did not perturb the instruction"
            )
        tools = record.get("tools_used")
        if not isinstance(tools, list) or not any(
            str(tool).startswith("apply_") for tool in tools
        ):
            raise ConfirmatoryContractError(
                f"record {sequence_index} lacks prompt-tool provenance"
            )
        generation = _mapping(record.get("generation"), "record.generation")
        _require_values(
            generation,
            {
                "sequence_index": sequence_index,
                "pair_id": pair["pair_id"],
                "producer_seed": 83,
                "one_generation_per_pair": True,
                "best_of_n_used": False,
                "victim_rollout_used": False,
                "clean_outcome_observed": False,
                "attacked_outcome_observed": False,
            },
            f"records[{sequence_index - 1}].generation",
        )
        validated.append(dict(record))
    return validated


def validate_fixed_trace_bundle(
    bundle: Mapping[str, Any],
    *,
    confirmatory_protocol: Mapping[str, Any],
    four_arm_protocol: Mapping[str, Any],
) -> None:
    validate_four_arm_preregistration(
        four_arm_protocol,
        confirmatory_protocol=confirmatory_protocol,
    )
    if bundle.get("schema") != FIXED_TRACE_BUNDLE_SCHEMA:
        raise ConfirmatoryContractError("unexpected fixed-trace bundle schema")
    if bundle.get("dispatch") is not False:
        raise ConfirmatoryContractError("fixed-trace bundle attempted dispatch")
    if bundle.get("proposal_adapter_frozen") is not True:
        raise ConfirmatoryContractError("fixed-trace proposal adapter is not frozen")
    expected_units = {unit.unit_id for unit in build_units(confirmatory_protocol)}
    traces = _object_list(bundle.get("traces"), "traces")
    if {row.get("unit_id") for row in traces} != expected_units:
        raise ConfirmatoryContractError("fixed-trace unit population differs")
    for trace in traces:
        proposals = _object_list(trace.get("proposals"), "trace.proposals")
        if not proposals:
            raise ConfirmatoryContractError(
                f"fixed trace is empty for {trace.get('unit_id')}"
            )
        indices = [row.get("proposal_index") for row in proposals]
        if indices != list(range(len(proposals))):
            raise ConfirmatoryContractError("fixed-trace proposal indices are not contiguous")
        for proposal in proposals:
            if digest_payload(_action_block_digest_payload(proposal)) != proposal.get(
                "action_block_digest"
            ):
                raise ConfirmatoryContractError("fixed-trace action-block digest differs")
            if digest_payload(_assessment_digest_payload(proposal)) != proposal.get(
                "assessment_digest"
            ):
                raise ConfirmatoryContractError("fixed-trace assessment digest differs")
            if digest_payload(_execution_contract_digest_payload(proposal)) != proposal.get(
                "execution_contract_digest"
            ):
                raise ConfirmatoryContractError(
                    "fixed-trace execution-contract digest differs"
                )


def validate_fixed_trace_results(
    results: Mapping[str, Any],
    *,
    trace_bundle: Mapping[str, Any],
) -> None:
    if results.get("schema") != FIXED_TRACE_RESULT_SCHEMA:
        raise ConfirmatoryContractError("unexpected fixed-trace result schema")
    if results.get("dispatch_attempt_count") != 0:
        raise ConfirmatoryContractError("fixed-trace result contains a dispatch attempt")
    rows = _object_list(results.get("rows"), "rows")
    trace_index = {
        (trace["unit_id"], proposal["proposal_index"]): proposal
        for trace in _object_list(trace_bundle.get("traces"), "traces")
        for proposal in _object_list(trace.get("proposals"), "trace.proposals")
    }
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            _text(row.get("unit_id"), "row.unit_id"),
            _integer(row.get("proposal_index"), "row.proposal_index"),
        )
        grouped.setdefault(key, []).append(row)
    if set(grouped) != set(trace_index):
        raise ConfirmatoryContractError("fixed-trace result coverage differs")
    for key, arm_rows in grouped.items():
        if len(arm_rows) != 4 or {row.get("arm") for row in arm_rows} != {
            arm.value for arm in ARM_ORDER
        }:
            raise ConfirmatoryContractError(f"fixed-trace arms differ at {key}")
        expected_digest = trace_index[key]["action_block_digest"]
        block_digests = {row.get("action_block_digest") for row in arm_rows}
        if block_digests != {expected_digest}:
            raise ConfirmatoryContractError(
                f"action-block identity is not byte-equivalent across arms at {key}"
            )
        expected_assessment = trace_index[key]["assessment_digest"]
        if {row.get("assessment_digest") for row in arm_rows} != {
            expected_assessment
        }:
            raise ConfirmatoryContractError(
                f"assessment identity is not byte-equivalent across arms at {key}"
            )
        expected_contract = trace_index[key]["execution_contract_digest"]
        if {row.get("execution_contract_digest") for row in arm_rows} != {
            expected_contract
        }:
            raise ConfirmatoryContractError(
                f"execution-contract identity is not byte-equivalent across arms at {key}"
            )
        if any(row.get("dispatch_attempted") is not False for row in arm_rows):
            raise ConfirmatoryContractError(
                f"fixed-trace dispatch was attempted at {key}"
            )
        for row in arm_rows:
            arm = MethodArm(_text(row.get("arm"), "row.arm"))
            if bool(row.get("intent_action_enabled")) != arm.intent_enabled:
                raise ConfirmatoryContractError(f"intent switch differs at {key}")
            if bool(row.get("action_execution_enabled")) != arm.execution_enabled:
                raise ConfirmatoryContractError(f"execution switch differs at {key}")


def _action_block_digest_payload(proposal: Mapping[str, Any]) -> dict[str, Any]:
    action = _mapping(proposal.get("action_block"), "proposal.action_block")
    required = (
        "episode_nonce",
        "proposal_index",
        "proposed_at_ns",
        "observation_digest",
        "state_epoch",
        "command",
        "command_shape",
    )
    missing = [key for key in required if key not in action]
    if missing:
        raise ConfirmatoryContractError(f"fixed-trace action block is missing {missing}")
    if action.get("action_block_digest") != proposal.get("action_block_digest"):
        raise ConfirmatoryContractError(
            "nested/top-level action-block digests differ"
        )
    if proposal.get("proposal_index") != action.get("proposal_index"):
        raise ConfirmatoryContractError("top-level/action-block indices differ")
    return {key: action[key] for key in required}


def _assessment_digest_payload(proposal: Mapping[str, Any]) -> dict[str, Any]:
    assessment = _mapping(
        proposal.get("intent_action_assessment"),
        "proposal.intent_action_assessment",
    )
    required = (
        "assessor_id",
        "assessor_version",
        "assessor_kind",
        "episode_nonce",
        "proposal_index",
        "generated_at_ns",
        "action_block_digest",
        "observation_digest",
        "state_epoch",
        "known",
        "predicted_skill",
        "target",
        "part",
        "region",
        "precondition_atoms",
        "predicted_effect_atoms",
        "predicted_violation_atoms",
        "unknown_reason",
    )
    missing = [key for key in required if key not in assessment]
    if missing:
        raise ConfirmatoryContractError(
            f"fixed-trace action assessment is missing {missing}"
        )
    if assessment.get("assessment_digest") != proposal.get("assessment_digest"):
        raise ConfirmatoryContractError(
            "nested/top-level assessment digests differ"
        )
    return {key: assessment[key] for key in required}


def _execution_contract_digest_payload(
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _mapping(
        proposal.get("execution_contract"),
        "proposal.execution_contract",
    )
    required = (
        "issuer_id",
        "issuer_version",
        "episode_nonce",
        "proposal_index",
        "issued_at_ns",
        "action_block_digest",
        "assessment_digest",
        "observation_digest",
        "state_epoch",
        "expected_effect_atoms",
        "forbidden_effect_atoms",
        "observation_window_steps",
    )
    missing = [key for key in required if key not in contract]
    if missing:
        raise ConfirmatoryContractError(
            f"fixed-trace execution contract is missing {missing}"
        )
    if contract.get("execution_contract_digest") != proposal.get(
        "execution_contract_digest"
    ):
        raise ConfirmatoryContractError(
            "nested/top-level execution-contract digests differ"
        )
    return {key: contract[key] for key in required}


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfirmatoryContractError(f"{name} must be an object")
    return value


def _object_list(value: Any, name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ConfirmatoryContractError(f"{name} must be a list of objects")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfirmatoryContractError(f"{name} must be non-empty text")
    return value


def _integer(value: Any, name: str) -> int:
    if type(value) is not int:
        raise ConfirmatoryContractError(f"{name} must be an integer")
    return value


def _require_values(
    observed: Mapping[str, Any],
    expected: Mapping[str, Any],
    name: str,
) -> None:
    for key, value in expected.items():
        if observed.get(key) != value:
            raise ConfirmatoryContractError(
                f"{name}.{key} differs: {observed.get(key)!r} != {value!r}"
            )


__all__ = [
    "ARM_ORDER",
    "ATTACK_RECORD_BUNDLE_SCHEMA",
    "CONDITION_ORDER",
    "FIXED_TRACE_BUNDLE_SCHEMA",
    "FIXED_TRACE_RESULT_SCHEMA",
    "ConfirmatoryContractError",
    "ConfirmatoryUnit",
    "FourArmEpisodeSpec",
    "VictimEpisodeSpec",
    "build_units",
    "file_sha256",
    "four_arm_episode_specs",
    "hash_balanced_units",
    "latin_square_arm_order",
    "load_json_object",
    "producer_pairs",
    "validate_attack_record_bundle",
    "validate_confirmatory_preregistration",
    "validate_fixed_trace_bundle",
    "validate_fixed_trace_results",
    "validate_four_arm_preregistration",
    "victim_episode_specs",
]
