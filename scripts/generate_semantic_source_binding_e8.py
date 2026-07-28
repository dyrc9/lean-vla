#!/usr/bin/env python3
"""Audit whether the semantic stack is bound to a clean Git commit."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_source_binding_e8_audit.json"
)
OPENPI_ROOT = REPO_ROOT / "external" / "openpi"

COMMIT_SCOPE_PATHS = (
    "Makefile",
    "README.md",
    "docs/action_block_assessment.md",
    "docs/experiments.md",
    "docs/implementation_and_experiment_readiness.md",
    "docs/l2_and_cross_layer_experiments.md",
    "docs/method.md",
    "docs/paper/paper_story.md",
    "docs/progress_and_plan.md",
    "docs/remote_execution.md",
    "docs/semantic_subtask_hierarchy.md",
    "docs/semantic_subtask_pilot.md",
    "docs/trusted_semantic_boundary.md",
    "lean/ProofAlign.lean",
    "lean/ProofAlign/SemanticIntegrityCore.lean",
    "scripts/check_all.sh",
    "scripts/freeze_four_arm_v4_l1_repair_qualification.py",
    "scripts/freeze_four_arm_v4_l1_repair_qualification_fresh2.py",
    "scripts/freeze_four_arm_v4_l1_repair_qualification_fresh3.py",
    (
        "scripts/"
        "freeze_four_arm_v4_l1_repair_qualification_terminal.py"
    ),
    "scripts/freeze_four_arm_v4_l1_block10_qualification.py",
    "scripts/freeze_four_arm_v4_l1_block10_terminal.py",
    "scripts/freeze_four_arm_v4_l1_block10_k4_qualification.py",
    "scripts/freeze_four_arm_v4_l1_block10_k4_terminal.py",
    (
        "scripts/"
        "freeze_four_arm_v4_l1_progress_projection_qualification.py"
    ),
    (
        "scripts/"
        "freeze_four_arm_v4_l1_progress_projection_terminal.py"
    ),
    (
        "scripts/"
        "freeze_four_arm_v4_l1_progress_projection_smoke.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_pick_up_phase_transition_smoke.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_pick_up_"
        "phase_transition_smoke_terminal.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_pick_up_regression_smoke.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_pick_up_"
        "regression_smoke_terminal.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_pick_up_fresh_dual_pilot.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_pick_up_"
        "fresh_dual_pilot_terminal.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_h4_regression_smoke.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_h4_"
        "regression_smoke_terminal.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_h4_"
        "regression_smoke_v2.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_prefix_"
        "regression_smoke.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_prefix_"
        "regression_smoke_terminal.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_qualification.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_qualification_terminal.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_qualification_v2.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_regression_smoke.py"
    ),
    (
        "scripts/"
        "freeze_horizon_consistent_release_"
        "regression_smoke_terminal.py"
    ),
    "scripts/generate_semantic_source_binding_e8.py",
    "scripts/generate_semantic_v4_equivalence_evidence.py",
    "scripts/prepare_deployment_perception_dataset_e7.py",
    "scripts/prepare_semantic_resource_smoke_e6.py",
    "scripts/run_deployment_perception_dataset_qualification_e7.py",
    "scripts/run_deployment_perception_preflight_e7.py",
    "scripts/run_deterministic_selector_qualification_e1f.py",
    "scripts/run_liberosafety_pi05_openpi_eval.py",
    "scripts/run_l2_execution_attack_eval.py",
    "scripts/run_l2_execution_attack_eval_v2.py",
    "scripts/run_l2_execution_attack_eval_v3.py",
    "scripts/run_l2_execution_attack_eval_v4.py",
    "scripts/run_l2_execution_attack_eval_v5.py",
    "scripts/run_l2_execution_attack_eval_v6.py",
    "scripts/run_l2_execution_attack_eval_v7.py",
    (
        "scripts/"
        "run_horizon_consistent_pick_up_fresh_dual_pilot.py"
    ),
    (
        "scripts/"
        "run_horizon_consistent_pick_up_phase_transition_smoke.py"
    ),
    (
        "scripts/"
        "run_horizon_consistent_pick_up_regression_smoke.py"
    ),
    (
        "scripts/"
        "run_horizon_consistent_release_h4_regression_smoke.py"
    ),
    (
        "scripts/"
        "run_horizon_consistent_release_prefix_regression_smoke.py"
    ),
    (
        "scripts/"
        "run_horizon_consistent_release_qualification.py"
    ),
    (
        "scripts/"
        "run_horizon_consistent_release_regression_smoke.py"
    ),
    "scripts/run_pick_up_prefix_progress_replay_qualification.py",
    "scripts/run_four_arm_v4_l1_repair_qualification.py",
    "scripts/run_four_arm_v4_l1_repair_qualification_v2.py",
    "scripts/run_four_arm_v4_l1_block10_qualification.py",
    "scripts/run_four_arm_v4_l1_block10_k4_qualification.py",
    (
        "scripts/"
        "run_four_arm_v4_l1_progress_projection_qualification.py"
    ),
    (
        "scripts/"
        "run_four_arm_v4_l1_progress_projection_smoke.py"
    ),
    "scripts/run_local_checker_qualification_e3.py",
    "scripts/run_pi05_action_conditioning_e2.py",
    "scripts/run_pi05_selector_qualification_e1.py",
    "scripts/run_semantic_effect_observer_qualification_e5.py",
    "scripts/run_semantic_closed_loop_smoke_e9.py",
    "scripts/run_semantic_no_dispatch_four_arm_e4.py",
    "scripts/run_semantic_resource_smoke_e6.py",
    "scripts/run_semantic_v4_fixed_trace_gate.py",
    "scripts/validate_deterministic_selector_e1f.py",
    "scripts/validate_local_checker_qualification_e3.py",
    "scripts/validate_pi05_selector_qualification_e1.py",
    "scripts/validate_semantic_post_e5_readiness.py",
    "scripts/validate_semantic_v4_c5_readiness.py",
    "src/proofalign/benchmark/semantic_four_arm_runner.py",
    "src/proofalign/integrity_v4_models.py",
    "src/proofalign/integrity_v4_runtime.py",
    "src/proofalign/horizon_consistent_pick_up.py",
    "src/proofalign/horizon_consistent_release.py",
    "src/proofalign/horizon_consistent_release_h4.py",
    "src/proofalign/horizon_consistent_release_prefix.py",
    "src/proofalign/semantic_action_selection.py",
    "src/proofalign/semantic_effect_observer.py",
    "src/proofalign/semantic_local_checker.py",
    "src/proofalign/semantic_policy_wrapper.py",
    "src/proofalign/semantic_progress_projection.py",
    "src/proofalign/semantic_trust.py",
    "tests/test_deployment_perception_dataset_qualification_e7.py",
    "tests/test_deployment_perception_preflight_e7.py",
    "tests/test_deterministic_selector_qualification.py",
    "tests/test_integrity_v4_models.py",
    "tests/test_integrity_v4_runtime.py",
    "tests/test_horizon_consistent_pick_up.py",
    (
        "tests/"
        "test_horizon_consistent_pick_up_fresh_dual_pilot.py"
    ),
    "tests/test_horizon_consistent_pick_up_smoke.py",
    "tests/test_horizon_consistent_release.py",
    "tests/test_horizon_consistent_release_h4.py",
    "tests/test_horizon_consistent_release_prefix.py",
    "tests/test_local_checker_qualification_e3.py",
    "tests/test_l1_repair_qualification.py",
    "tests/test_l1_repair_qualification_v2.py",
    "tests/test_l1_block10_qualification.py",
    "tests/test_l1_block10_k4_qualification.py",
    "tests/test_l1_progress_projection_qualification.py",
    "tests/test_l1_progress_projection_smoke.py",
    "tests/test_pi05_action_conditioning_e2.py",
    "tests/test_pi05_selector_qualification.py",
    "tests/test_pick_up_prefix_progress_replay.py",
    "tests/test_semantic_effect_observer.py",
    "tests/test_semantic_effect_observer_qualification_e5.py",
    "tests/test_semantic_local_checker.py",
    "tests/test_semantic_no_dispatch_four_arm_e4.py",
    "tests/test_semantic_online_runner.py",
    "tests/test_semantic_online_runner_v2.py",
    "tests/test_semantic_online_runner_v3.py",
    "tests/test_semantic_policy_wrapper.py",
    "tests/test_semantic_post_e5_readiness.py",
    "tests/test_semantic_progress_projection.py",
    "tests/test_semantic_resource_smoke_e6.py",
    "tests/test_semantic_source_binding_e8.py",
    "tests/test_semantic_v4_c5.py",
    "experiments/proofalign_deployment_perception_e7_preflight.json",
    "experiments/proofalign_deployment_perception_e7_protocol.json",
    (
        "experiments/"
        "proofalign_deployment_perception_supervision_schema_e7.json"
    ),
    "experiments/proofalign_deterministic_selector_e1f.json",
    "experiments/proofalign_deterministic_selector_e1f_protocol.json",
    "experiments/proofalign_local_checker_e3_protocol.json",
    "experiments/proofalign_local_checker_e3_v2_protocol.json",
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_repair_qualification_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_repair_qualification_fresh2_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_repair_qualification_fresh3_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_repair_qualification_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_block10_qualification_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_block10_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_block10_k4_qualification_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_progress_projection_"
        "qualification_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_progress_projection_"
        "terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_four_arm_v4_l1_progress_projection_"
        "smoke_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_pick_up_"
        "phase_transition_smoke_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_pick_up_"
        "phase_transition_smoke_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_pick_up_"
        "regression_smoke_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_pick_up_"
        "regression_smoke_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_pick_up_"
        "fresh_dual_pilot_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_pick_up_"
        "fresh_dual_pilot_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_h4_"
        "regression_smoke_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_h4_"
        "regression_smoke_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_h4_"
        "regression_smoke_v2_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_prefix_"
        "regression_smoke_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_prefix_"
        "regression_smoke_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_"
        "qualification_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_"
        "qualification_terminal_summary.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_"
        "qualification_v2_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_"
        "regression_smoke_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_horizon_consistent_release_"
        "regression_smoke_terminal_summary.json"
    ),
    "experiments/proofalign_pi05_action_conditioning_e2_protocol.json",
    "experiments/proofalign_pi05_selector_e1_protocol.json",
    (
        "experiments/"
        "proofalign_pick_up_prefix_progress_replay_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_pick_up_prefix_progress_replay_v2_protocol.json"
    ),
    (
        "experiments/"
        "proofalign_pick_up_prefix_progress_replay_v3_protocol.json"
    ),
    "experiments/proofalign_semantic_effect_observer_e5_protocol.json",
    "experiments/proofalign_semantic_effect_observer_e5_v2_protocol.json",
    "experiments/proofalign_semantic_four_arm_e4_protocol.json",
    (
        "experiments/"
        "proofalign_semantic_resource_smoke_e6_v2_authorized_protocol.json"
    ),
    "experiments/proofalign_semantic_resource_smoke_e6_v2_protocol.json",
    "experiments/proofalign_semantic_v4_c5_protocol.json",
    (
        "experiments/"
        "proofalign_semantic_v4_c5_readiness_packet_v1.json"
    ),
    "experiments/proofalign_semantic_v4_fixed_trace_c5.json",
    "experiments/proofalign_semantic_v4_lean_equivalence_c5.json",
)

EVIDENCE_PATHS = (
    (
        "results/proofalign_semantic_selector_e1_20260725_fresh1/"
        "qualification.json"
    ),
    (
        "results/proofalign_semantic_selector_e1_20260725_fresh1/"
        "SHA256SUMS"
    ),
    (
        "results/proofalign_action_conditioning_e2_20260725_fresh1/"
        "qualification.json"
    ),
    (
        "results/proofalign_action_conditioning_e2_20260725_fresh1/"
        "SHA256SUMS"
    ),
    (
        "results/proofalign_local_checker_e3_v2_20260727_fresh1/"
        "qualification.json"
    ),
    (
        "results/proofalign_local_checker_e3_v2_20260727_fresh1/"
        "SHA256SUMS"
    ),
    "results/proofalign_semantic_four_arm_e4_20260725_fresh1.json",
    (
        "results/proofalign_semantic_effect_observer_e5_v2_"
        "20260727_fresh1/qualification.json"
    ),
    (
        "results/proofalign_semantic_effect_observer_e5_v2_"
        "20260727_fresh1/SHA256SUMS"
    ),
    (
        "results/proofalign_semantic_resource_smoke_e6_v2_"
        "20260727_fresh2/measurement.json"
    ),
    (
        "results/proofalign_semantic_resource_smoke_e6_v2_"
        "20260727_fresh2/SHA256SUMS"
    ),
    (
        "results/proofalign_four_arm_v4_l1_progress_projection_"
        "qualification_20260728_fresh1/summary.json"
    ),
    (
        "results/proofalign_four_arm_v4_l1_progress_projection_"
        "qualification_20260728_fresh1/SHA256SUMS"
    ),
)


class SourceBindingError(RuntimeError):
    """Raised when an E8 source-binding audit is invalid."""


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


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


def _git(
    *args: str,
    cwd: Path = REPO_ROOT,
) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _status_map(paths: tuple[str, ...]) -> dict[str, str]:
    output = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *paths,
    )
    result: dict[str, str] = {}
    for line in output.splitlines():
        if len(line) < 4:
            raise SourceBindingError(
                f"unexpected git status row: {line}"
            )
        status = line[:2]
        path_text = line[3:]
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        result[path_text] = status
    return result


def _tracked_paths(paths: tuple[str, ...]) -> set[str]:
    output = _git("ls-files", "--", *paths)
    return set(output.splitlines()) if output else set()


def _repository_state(path: Path) -> dict[str, Any]:
    status = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
        cwd=path,
    )
    return {
        "path": str(path.resolve()),
        "head_commit": _git("rev-parse", "HEAD", cwd=path),
        "tracked_worktree_clean": not bool(status),
        "tracked_status_rows": status.splitlines(),
    }


def build_report() -> dict[str, Any]:
    scope_commit = _git(
        "log",
        "-1",
        "--format=%H",
        "--",
        *COMMIT_SCOPE_PATHS,
    )
    if not scope_commit:
        raise SourceBindingError(
            "semantic commit scope has no binding commit"
        )
    statuses = _status_map(COMMIT_SCOPE_PATHS)
    tracked = _tracked_paths(COMMIT_SCOPE_PATHS)
    source_rows = []
    for relative in COMMIT_SCOPE_PATHS:
        path = REPO_ROOT / relative
        exists = path.is_file()
        status = statuses.get(relative)
        is_tracked = relative in tracked
        source_rows.append(
            {
                "path": relative,
                "exists": exists,
                "sha256": file_sha256(path) if exists else None,
                "tracked": is_tracked,
                "git_status": status or "clean",
                "bound_to_head": (
                    exists and is_tracked and status is None
                ),
            }
        )
    evidence_rows = []
    for relative in EVIDENCE_PATHS:
        path = REPO_ROOT / relative
        evidence_rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "sha256": (
                    file_sha256(path) if path.is_file() else None
                ),
                "ignored_by_git": bool(
                    subprocess.run(
                        ("git", "check-ignore", "-q", "--", relative),
                        cwd=REPO_ROOT,
                        check=False,
                    ).returncode
                    == 0
                ),
            }
        )
    tracked_status = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
    )
    scope_complete = all(row["exists"] for row in source_rows)
    scope_bound = scope_complete and all(
        row["bound_to_head"] for row in source_rows
    )
    evidence_complete = all(
        row["exists"] for row in evidence_rows
    )
    openpi = _repository_state(OPENPI_ROOT)
    clean_commit_bound = (
        scope_bound
        and evidence_complete
        and openpi["tracked_worktree_clean"]
    )
    not_bound = [
        row["path"]
        for row in source_rows
        if not row["bound_to_head"]
    ]
    return {
        "schema": "proofalign.semantic-source-binding-e8-audit.v1",
        "audit_id": (
            "proofalign-semantic-source-binding-e8-20260725"
        ),
        "classification": (
            "semantic_source_binding_clean"
            if clean_commit_bound
            else "semantic_source_binding_not_clean"
        ),
        "repository_head_commit": scope_commit,
        "repository_head_tree": _git(
            "rev-parse", f"{scope_commit}^{{tree}}"
        ),
        "repository_binding_semantics": (
            "latest commit that changed the frozen semantic commit scope; "
            "later commits may contain only out-of-scope protocols or "
            "audit packets"
        ),
        "repository_fully_clean": not bool(tracked_status),
        "repository_status_row_count": len(
            tracked_status.splitlines()
        ),
        "commit_scope_complete": scope_complete,
        "commit_scope_bound_to_head": scope_bound,
        "evidence_inventory_complete": evidence_complete,
        "openpi_binding": openpi,
        "clean_commit_bound": clean_commit_bound,
        "not_bound_path_count": len(not_bound),
        "not_bound_paths": not_bound,
        "commit_scope": source_rows,
        "evidence_inventory": evidence_rows,
        "audit_source": {
            "path": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
            "sha256": file_sha256(Path(__file__).resolve()),
        },
        "outcomes_observed_or_generated": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "claim_boundary": (
            "This read-only audit binds the current semantic source scope, "
            "local evidence inventory, latest source-scope commit, and "
            "OpenPI checkout. "
            "A not-clean classification does not modify or commit the "
            "worktree. A clean classification would establish provenance "
            "only, not perception quality, efficacy, outcome, or safety."
        ),
    }


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
                raise SourceBindingError(
                    f"E8 source-binding audit is stale: {args.packet}"
                )
            print(f"E8 source-binding audit is current: {args.packet}")
        else:
            args.packet.parent.mkdir(parents=True, exist_ok=True)
            args.packet.write_text(text, encoding="utf-8")
            print(args.packet)
        return 0
    except (
        KeyError,
        OSError,
        SourceBindingError,
        subprocess.CalledProcessError,
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
