#!/usr/bin/env python3
"""Audit current semantic no-outcome readiness after E5 qualification."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from run_semantic_effect_observer_qualification_e5 import (  # noqa: E402
    CHECKSUMS_PATH as E5_CHECKSUMS_PATH,
    PROTOCOL_PATH as E5_PROTOCOL_PATH,
    RESULT_PATH as E5_RESULT_PATH,
    file_sha256,
    validate_protocol as validate_e5_protocol,
    validate_result as validate_e5_result,
)
from run_semantic_no_dispatch_four_arm_e4 import (  # noqa: E402
    PROTOCOL_PATH as E4_PROTOCOL_PATH,
    RESULT_PATH as E4_RESULT_PATH,
    validate_result as validate_e4_result,
)
from prepare_semantic_resource_smoke_e6 import (  # noqa: E402
    OUTPUT_ROOT as E6_OUTPUT_ROOT,
    PROTOCOL_PATH as E6_PROTOCOL_PATH,
    build_protocol as build_e6_protocol,
    canonical_text as e6_canonical_text,
    validate_protocol as validate_e6_protocol,
)
from run_semantic_resource_smoke_e6 import (  # noqa: E402
    AUTHORIZED_PROTOCOL_PATH as E6_AUTHORIZED_PROTOCOL_PATH,
    CHECKSUMS_PATH as E6_AUTHORIZED_CHECKSUMS_PATH,
    OUTPUT_ROOT as E6_AUTHORIZED_OUTPUT_ROOT,
    RESULT_PATH as E6_AUTHORIZED_RESULT_PATH,
    validate_authorized_protocol as validate_e6_authorized_protocol,
    validate_result as validate_e6_result,
)
from run_deployment_perception_preflight_e7 import (  # noqa: E402
    EVIDENCE_PATH as E7_EVIDENCE_PATH,
    PROTOCOL_PATH as E7_PROTOCOL_PATH,
    build_evidence as build_e7_evidence,
    canonical_text as e7_canonical_text,
    validate_protocol as validate_e7_protocol,
)
from prepare_deployment_perception_dataset_e7 import (  # noqa: E402
    SCHEMA_PATH as E7_SUPERVISION_SCHEMA_PATH,
    build_schema as build_e7_supervision_schema,
    canonical_text as e7_supervision_canonical_text,
    validate_schema as validate_e7_supervision_schema,
)
from generate_semantic_source_binding_e8 import (  # noqa: E402
    DEFAULT_PACKET as E8_PACKET_PATH,
    build_report as build_e8_report,
    canonical_text as e8_canonical_text,
)


DEFAULT_PACKET = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_post_e5_readiness_packet_v1.json"
)
SOURCE_PATHS = (
    "src/proofalign/semantic_effect_observer.py",
    "scripts/run_liberosafety_pi05_openpi_eval.py",
    "scripts/run_semantic_effect_observer_qualification_e5.py",
    "scripts/validate_semantic_post_e5_readiness.py",
    "tests/test_semantic_effect_observer.py",
    "tests/test_semantic_effect_observer_qualification_e5.py",
    "tests/test_semantic_online_runner.py",
    "scripts/prepare_semantic_resource_smoke_e6.py",
    "scripts/run_semantic_resource_smoke_e6.py",
    "scripts/run_deployment_perception_preflight_e7.py",
    "scripts/prepare_deployment_perception_dataset_e7.py",
    "scripts/run_deployment_perception_dataset_qualification_e7.py",
    "scripts/generate_semantic_source_binding_e8.py",
    "tests/test_semantic_resource_smoke_e6.py",
    "tests/test_deployment_perception_preflight_e7.py",
    "tests/test_deployment_perception_dataset_qualification_e7.py",
    "tests/test_semantic_source_binding_e8.py",
    "Makefile",
    "scripts/check_all.sh",
)
ONLINE_REQUIRED_FRAGMENTS = (
    "SemanticPrefixEffectObserver",
    "initial_local_observation",
    "latest_local_observation",
    "effects_known=effects_known",
    "observer_id=EFFECT_OBSERVER_ID",
)
MAKEFILE_REQUIRED_FRAGMENTS = (
    "e4-no-dispatch-check:",
    "e5-effect-observer-check:",
    "e6-resource-smoke-preflight-check:",
    "e7-perception-preflight-check:",
    "e8-source-binding-check:",
    "semantic-post-e5-readiness-check:",
)
CHECK_ALL_REQUIRED_FRAGMENTS = (
    "scripts/run_semantic_no_dispatch_four_arm_e4.py --check",
    "scripts/run_semantic_effect_observer_qualification_e5.py --check",
    "scripts/prepare_semantic_resource_smoke_e6.py --check",
    "scripts/run_semantic_resource_smoke_e6.py --check-state",
    "scripts/run_deployment_perception_preflight_e7.py --check",
    "scripts/prepare_deployment_perception_dataset_e7.py --check-schema",
    (
        "scripts/run_deployment_perception_dataset_qualification_e7.py "
        "--check-contract"
    ),
    "scripts/generate_semantic_source_binding_e8.py --check",
    "scripts/validate_semantic_post_e5_readiness.py --check",
)


class PostE5ReadinessError(RuntimeError):
    """Raised when the post-E5 readiness packet is stale or invalid."""


def _sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PostE5ReadinessError(
            f"expected JSON object: {path}"
        )
    return value


def _fragment_report(
    text: str,
    fragments: tuple[str, ...],
) -> dict[str, bool]:
    return {fragment: fragment in text for fragment in fragments}


def build_report() -> dict[str, Any]:
    e4_protocol = _read_json(E4_PROTOCOL_PATH)
    e4_result = _read_json(E4_RESULT_PATH)
    validate_e4_result(e4_protocol, e4_result)

    e5_protocol = _read_json(E5_PROTOCOL_PATH)
    e5_result = _read_json(E5_RESULT_PATH)
    validate_e5_protocol(e5_protocol)
    validate_e5_result(e5_protocol, e5_result)
    expected_checksum = (
        f"{file_sha256(E5_RESULT_PATH)}  {E5_RESULT_PATH.name}\n"
    )
    if E5_CHECKSUMS_PATH.read_text(
        encoding="utf-8"
    ) != expected_checksum:
        raise PostE5ReadinessError("E5 checksum manifest is stale")

    e6_protocol = _read_json(E6_PROTOCOL_PATH)
    validate_e6_protocol(e6_protocol)
    if E6_PROTOCOL_PATH.read_text(
        encoding="utf-8"
    ) != e6_canonical_text(build_e6_protocol()):
        raise PostE5ReadinessError("E6 protocol is stale")
    if E6_OUTPUT_ROOT.exists():
        raise PostE5ReadinessError(
            "superseded E6 preregistration output root is occupied"
        )
    e6_authorized = E6_AUTHORIZED_PROTOCOL_PATH.exists()
    e6_measurement_complete = False
    e6_measurement_qualified = False
    e6_classification = None
    e6_result_sha256 = None
    if e6_authorized:
        e6_authorized_protocol = _read_json(
            E6_AUTHORIZED_PROTOCOL_PATH
        )
        validate_e6_authorized_protocol(e6_authorized_protocol)
        if (
            E6_AUTHORIZED_RESULT_PATH.exists()
            != E6_AUTHORIZED_CHECKSUMS_PATH.exists()
        ):
            raise PostE5ReadinessError(
                "E6 result/checksum presence is inconsistent"
            )
        if E6_AUTHORIZED_RESULT_PATH.exists():
            e6_result = _read_json(E6_AUTHORIZED_RESULT_PATH)
            validate_e6_result(
                e6_authorized_protocol,
                e6_result,
            )
            expected_e6_checksum = (
                f"{_sha256(E6_AUTHORIZED_RESULT_PATH)}  "
                f"{E6_AUTHORIZED_RESULT_PATH.name}\n"
            )
            if E6_AUTHORIZED_CHECKSUMS_PATH.read_text(
                encoding="utf-8"
            ) != expected_e6_checksum:
                raise PostE5ReadinessError(
                    "E6 checksum manifest is stale"
                )
            e6_measurement_complete = True
            e6_measurement_qualified = e6_result["summary"][
                "qualified"
            ]
            e6_classification = e6_result["classification"]
            e6_result_sha256 = _sha256(
                E6_AUTHORIZED_RESULT_PATH
            )
    elif E6_AUTHORIZED_OUTPUT_ROOT.exists():
        raise PostE5ReadinessError(
            "authorized E6 output exists without a protocol"
        )

    e7_protocol = _read_json(E7_PROTOCOL_PATH)
    validate_e7_protocol(e7_protocol)
    e7_evidence = build_e7_evidence(e7_protocol)
    if E7_EVIDENCE_PATH.read_text(
        encoding="utf-8"
    ) != e7_canonical_text(e7_evidence):
        raise PostE5ReadinessError("E7 evidence is stale")
    e7_supervision_schema = _read_json(
        E7_SUPERVISION_SCHEMA_PATH
    )
    validate_e7_supervision_schema(e7_supervision_schema)
    if E7_SUPERVISION_SCHEMA_PATH.read_text(
        encoding="utf-8"
    ) != e7_supervision_canonical_text(
        build_e7_supervision_schema()
    ):
        raise PostE5ReadinessError(
            "E7 supervision contract is stale"
        )
    e8_report = build_e8_report()
    if E8_PACKET_PATH.read_text(
        encoding="utf-8"
    ) != e8_canonical_text(e8_report):
        raise PostE5ReadinessError(
            "E8 source-binding audit is stale"
        )

    online_text = (
        REPO_ROOT
        / "scripts"
        / "run_liberosafety_pi05_openpi_eval.py"
    ).read_text(encoding="utf-8")
    makefile_text = (REPO_ROOT / "Makefile").read_text(
        encoding="utf-8"
    )
    check_all_text = (
        REPO_ROOT / "scripts" / "check_all.sh"
    ).read_text(encoding="utf-8")
    online_fragments = _fragment_report(
        online_text,
        ONLINE_REQUIRED_FRAGMENTS,
    )
    makefile_fragments = _fragment_report(
        makefile_text,
        MAKEFILE_REQUIRED_FRAGMENTS,
    )
    check_all_fragments = _fragment_report(
        check_all_text,
        CHECK_ALL_REQUIRED_FRAGMENTS,
    )
    wiring_complete = (
        all(online_fragments.values())
        and all(makefile_fragments.values())
        and all(check_all_fragments.values())
    )
    components = {
        "e4_no_dispatch_gate": {
            "complete": e4_result["e4_complete"] is True,
            "path": str(E4_RESULT_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(E4_RESULT_PATH),
            "classification": e4_result["classification"],
            "outcome_rollout_authorized": e4_result[
                "outcome_rollout_authorized"
            ],
        },
        "e5_effect_observer_qualification": {
            "complete": e5_result["summary"]["qualified"] is True,
            "path": str(E5_RESULT_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(E5_RESULT_PATH),
            "classification": e5_result["classification"],
            "case_count": e5_result["summary"]["case_count"],
            "clean_retention": e5_result["summary"][
                "clean_retention"
            ],
            "attack_false_allow_count": e5_result["summary"][
                "attack_false_allow_count"
            ],
            "ood_abstention_rate": e5_result["summary"][
                "ood_abstention_rate"
            ],
            "p99_latency_ns": e5_result["summary"]["latency_ns"][
                "p99"
            ],
        },
        "qualified_observer_online_wiring": {
            "complete": all(online_fragments.values()),
            "fragments": online_fragments,
        },
        "top_level_check_wiring": {
            "complete": (
                all(makefile_fragments.values())
                and all(check_all_fragments.values())
            ),
            "makefile_fragments": makefile_fragments,
            "check_all_fragments": check_all_fragments,
        },
        "e6_resource_smoke_preregistration": {
            "complete": (
                (
                    not e6_authorized
                    and not E6_AUTHORIZED_OUTPUT_ROOT.exists()
                )
                or (
                    e6_measurement_complete
                    and e6_measurement_qualified
                )
            ),
            "path": str(E6_PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(E6_PROTOCOL_PATH),
            "execution_authorized": e6_authorized,
            "measurement_complete": e6_measurement_complete,
            "measurement_qualified": e6_measurement_qualified,
            "classification": e6_classification,
            "result_path": (
                str(
                    E6_AUTHORIZED_RESULT_PATH.relative_to(
                        REPO_ROOT
                    )
                )
                if e6_measurement_complete
                else None
            ),
            "result_sha256": e6_result_sha256,
            "fresh_output_root_absent": not E6_OUTPUT_ROOT.exists(),
            "executor_ready": True,
            "authorized_successor_protocol_absent": (
                not e6_authorized
            ),
            "authorized_successor_output_root_absent": (
                not E6_AUTHORIZED_OUTPUT_ROOT.exists()
            ),
        },
        "e7_deployment_perception_data_audit": {
            "complete": True,
            "path": str(E7_EVIDENCE_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(E7_EVIDENCE_PATH),
            "classification": e7_evidence["classification"],
            "qualification_ready": e7_evidence[
                "qualification_ready"
            ],
            "missing_requirement_ids": e7_evidence[
                "missing_requirement_ids"
            ],
            "supervision_contract_path": str(
                E7_SUPERVISION_SCHEMA_PATH.relative_to(REPO_ROOT)
            ),
            "supervision_contract_sha256": _sha256(
                E7_SUPERVISION_SCHEMA_PATH
            ),
            "supervision_contract_current": True,
            "dataset_qualification_runner_ready": True,
        },
        "e8_source_binding_audit": {
            "complete": True,
            "path": str(E8_PACKET_PATH.relative_to(REPO_ROOT)),
            "sha256": _sha256(E8_PACKET_PATH),
            "classification": e8_report["classification"],
            "repository_head_commit": e8_report[
                "repository_head_commit"
            ],
            "commit_scope_complete": e8_report[
                "commit_scope_complete"
            ],
            "evidence_inventory_complete": e8_report[
                "evidence_inventory_complete"
            ],
            "openpi_head_commit": e8_report["openpi_binding"][
                "head_commit"
            ],
            "openpi_tracked_worktree_clean": e8_report[
                "openpi_binding"
            ]["tracked_worktree_clean"],
            "clean_commit_bound": e8_report[
                "clean_commit_bound"
            ],
            "not_bound_path_count": e8_report[
                "not_bound_path_count"
            ],
        },
    }
    no_outcome_stack_complete = (
        all(component["complete"] for component in components.values())
        and wiring_complete
    )
    blockers = []
    if e7_evidence["missing_requirement_ids"]:
        blockers.append(
            "deployment perception cannot be qualified from the current "
            "RLDS schema; missing: "
            + ",".join(e7_evidence["missing_requirement_ids"])
        )
    if not e8_report["clean_commit_bound"]:
        blockers.append(
            "semantic source scope is not bound to a clean commit; "
            f"E8 reports {e8_report['not_bound_path_count']} "
            "unbound paths"
        )
    if not e6_measurement_complete:
        blockers.insert(
            1,
            (
                "E6 resource smoke is preregistered but its authorized "
                "measurement is incomplete"
                if e6_authorized
                else (
                    "E6 resource smoke is preregistered but explicit "
                    "model-load/GPU authorization and measurement are "
                    "absent"
                )
            ),
        )
    elif not e6_measurement_qualified:
        blockers.insert(
            1,
            "E6 resource smoke completed but did not qualify",
        )
    blockers.append(
        "an outcome-bearing M2/four-arm protocol has not yet been frozen"
    )
    return {
        "schema": "proofalign.semantic-post-e5-readiness.v1",
        "packet_id": (
            "proofalign-semantic-post-e5-readiness-20260725-v1"
        ),
        "outcomes_observed_or_generated": False,
        "policy_loaded_during_readiness_audit": False,
        "simulator_created_during_readiness_audit": False,
        "actions_executed_during_readiness_audit": False,
        "reward_success_read_during_readiness_audit": False,
        "no_outcome_stack_complete": no_outcome_stack_complete,
        "benchmark_privileged_geometry_stack_qualified": (
            no_outcome_stack_complete
        ),
        "deployment_stack_qualified": False,
        "outcome_rollout_ready": False,
        "outcome_rollout_authorized": False,
        "components": components,
        "current_blockers": blockers,
        "source_bindings": {
            relative: _sha256(REPO_ROOT / relative)
            for relative in SOURCE_PATHS
        },
        "claim_boundary": (
            "This packet closes only the no-outcome benchmark "
            "privileged-geometry stack and the current E6 resource state. "
            "It contains no online "
            "rollout, task outcome, deployment-perception qualification, "
            "efficacy, or physical-safety evidence and authorizes no "
            "execution."
        ),
    }


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report()
        text = canonical_text(report)
        if args.check:
            if args.packet.read_text(encoding="utf-8") != text:
                raise PostE5ReadinessError(
                    f"post-E5 readiness packet is stale: {args.packet}"
                )
            print(
                f"post-E5 readiness packet is current: {args.packet}"
            )
        else:
            args.packet.parent.mkdir(parents=True, exist_ok=True)
            args.packet.write_text(text, encoding="utf-8")
            print(args.packet)
        return 0
    except (
        KeyError,
        OSError,
        PostE5ReadinessError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
