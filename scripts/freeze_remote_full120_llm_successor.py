#!/usr/bin/env python3
"""Freeze the post-failure, outcome-blind LLM-template full-120 successor."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import ARM_ORDER, canonical_text  # noqa: E402
from scripts.run_joint_limit_containment_v11_attacked_scale45 import derive_attack_transplants  # noqa: E402


OLD_UMBRELLA = REPO_ROOT / "experiments/proofalign_remote_full120_successor_protocol_20260818.json"
OLD_CLEAN = REPO_ROOT / "experiments/proofalign_remote_full120_clean_protocol_20260818.json"
OLD_ATTACKED = REPO_ROOT / "experiments/proofalign_remote_full120_attacked_protocol_20260818.json"
ATTACK_SOURCE = REPO_ROOT / "results/saber_confirmatory_producer_m2_20260727_fresh1/attack_records.json"
CATALOG = REPO_ROOT / "experiments/proofalign_llm_semantic_template_catalog_20260818.json"
QUAL_PROTOCOL = REPO_ROOT / "experiments/proofalign_llm_semantic_template_qualification_v2_20260818.json"
QUAL_ROOT = REPO_ROOT / "results/proofalign_llm_semantic_template_qualification_20260818_fresh2"
UMBRELLA = REPO_ROOT / "experiments/proofalign_remote_full120_llm_successor_protocol_20260818.json"
CLEAN = REPO_ROOT / "experiments/proofalign_remote_full120_llm_clean_protocol_20260818.json"
ATTACKED = REPO_ROOT / "experiments/proofalign_remote_full120_llm_attacked_protocol_20260818.json"
DRY_RUN = REPO_ROOT / "experiments/proofalign_remote_full120_llm_orchestration_dry_run_20260818.json"
CLEAN_ROOT = "results/proofalign_remote_full120_llm_clean_20260818_fresh1"
ATTACKED_ROOT = "results/proofalign_remote_full120_llm_attacked_20260818_fresh1"
EXTRA_SOURCE_PATHS = (
    "src/proofalign/llm_semantic_templates.py",
    "src/proofalign/semantic_local_checker.py",
    "src/proofalign/semantic_policy_wrapper.py",
    "scripts/run_llm_template_semantic_v1.py",
    "scripts/run_remote_full120_llm_experiment.py",
    "scripts/freeze_remote_full120_llm_successor.py",
    "scripts/analyze_remote_full120_experiment.py",
    "scripts/analyze_remote_full120_llm_experiment.py",
)


class FreezeError(RuntimeError):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=REPO_ROOT, text=True, capture_output=True)
    if result.returncode:
        raise FreezeError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def _write(path: Path, payload: Any) -> None:
    path.write_text(canonical_text(payload), encoding="utf-8")


def _binding(path: Path, *, classification: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }
    if classification is not None:
        value["classification"] = classification
    return value


def _source(old_clean: dict[str, Any]) -> dict[str, Any]:
    paths = tuple(dict.fromkeys((*old_clean["source"]["sha256"], *EXTRA_SOURCE_PATHS)))
    commit = _git("rev-parse", "HEAD")
    return {
        "repository_commit": commit,
        "repository_tree": _git("rev-parse", "HEAD^{tree}"),
        "sha256": {path: file_sha256(REPO_ROOT / path) for path in paths},
        "freezer": Path(__file__).relative_to(REPO_ROOT).as_posix(),
        "freezer_sha256": file_sha256(Path(__file__)),
    }


def _balance(schedule: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(row["arm"]) for row in schedule)
    unit_ids = {str(row["unit_id"]) for row in schedule}
    return {
        "episode_count": len(schedule),
        "unit_count": len(unit_ids),
        "arm_counts": {arm: counts[arm] for arm in ARM_ORDER},
        "sequence_contiguous": [row["sequence_index"] for row in schedule]
        == list(range(len(schedule))),
    }


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    old_umbrella = load_json_object(OLD_UMBRELLA)
    old_clean = load_json_object(OLD_CLEAN)
    old_attacked = load_json_object(OLD_ATTACKED)
    qualification = load_json_object(QUAL_ROOT / "summary.json")
    if qualification.get("classification") != "llm_semantic_template_qualification_pass":
        raise FreezeError("passing outcome-blind qualification is absent")
    if any(
        qualification.get(key) != 0
        for key in (
            "policy_load_count",
            "policy_inference_count",
            "env_step_count",
            "task_outcome_read_count",
            "attacked_prompt_read_count",
        )
    ):
        raise FreezeError("qualification crossed the threat boundary")
    source = _source(old_clean)
    bindings = [
        _binding(CATALOG),
        _binding(QUAL_PROTOCOL),
        _binding(
            QUAL_ROOT / "summary.json",
            classification="llm_semantic_template_qualification_pass",
        ),
        _binding(QUAL_ROOT / "qualification_ledger.jsonl"),
        _binding(QUAL_ROOT / "checksums.sha256"),
    ]

    umbrella = deepcopy(old_umbrella)
    umbrella.update(
        {
            "protocol_id": "proofalign-remote-full120-llm-template-successor-20260818",
            "protocol_status": "post_failure_exploratory_full120_execution_authorized",
            "source": source,
            "fresh_roots": {"stage_b": CLEAN_ROOT, "stage_c": ATTACKED_ROOT},
            "post_failure_exploratory_method_extension": True,
            "llm_template_catalog": _binding(CATALOG),
            "outcome_blind_qualification": _binding(
                QUAL_ROOT / "summary.json",
                classification="llm_semantic_template_qualification_pass",
            ),
            "outcomes_used_for_llm_template_generation": False,
            "attacked_prompt_visible_to_template_generator": False,
            "runtime_llm_call_count": 0,
            "historical_remote_full120_failure_preserved": _binding(
                REPO_ROOT / "docs/paper/remote_full120_result_handoff.md"
            ),
            "attacked_launch_gate": (
                "all 480 clean artifacts present, valid, and checksum-verified; "
                "clean utility result does not select or block attacked pairs"
            ),
        }
    )
    umbrella["reuse_decision"] = {
        "reused_episode_count": 0,
        "new_episode_count": 960,
        "reason": "historical VLA-only identity/config/raw/checksum audit did not pass",
        "audit_path": "experiments/proofalign_remote_full120_baseline_reuse_audit_20260818.json",
    }
    umbrella["risk_transition_contract"] = deepcopy(old_umbrella["risk_transition_contract"])
    umbrella["method_extension"] = {
        "generator": "local Qwen2.5-3B-Instruct at pre-freeze compile time",
        "generator_inputs": ["trusted task instruction", "trusted BDDL goal"],
        "untrusted_output_rule": "exact reconstruction by independent allow-listed validator",
        "runtime_geometry": "exact MuJoCo site/body/contact geom for frozen entity/part IDs",
        "online_attack_visibility": False,
        "online_outcome_visibility": False,
        "runtime_generation": False,
    }

    clean = deepcopy(old_clean)
    clean.update(
        {
            "protocol_id": "proofalign-remote-full120-llm-clean-20260818",
            "fresh_output_root": CLEAN_ROOT,
            "source": source,
            "post_failure_exploratory_method_extension": True,
            "llm_template_catalog": _binding(CATALOG),
            "outcome_blind_qualification": _binding(QUAL_ROOT / "summary.json"),
            "outcomes_used_for_llm_template_generation": False,
        }
    )
    clean["design"].update(
        {
            "study_role": "full120 clean data collection for threat-bounded LLM semantic templates",
            "task_runtime_method_version": "v15.14+llm-template-v1",
            "all_60_base_pairs_retained": True,
            "thresholds_changed_after_task_outcomes": False,
        }
    )
    clean["required_bindings"] = [*clean["required_bindings"], *bindings]

    attacked = deepcopy(old_attacked)
    attacked.update(
        {
            "protocol_id": "proofalign-remote-full120-llm-attacked-20260818",
            "fresh_output_root": ATTACKED_ROOT,
            "source": source,
            "post_failure_exploratory_method_extension": True,
            "llm_template_catalog": _binding(CATALOG),
            "outcomes_used_for_llm_template_generation": False,
        }
    )
    attacked["design"].update(
        {
            "study_role": "paired full120 SABER-attacked data collection for threat-bounded LLM semantic templates",
            "task_runtime_method_version": "v15.14+llm-template-v1",
            "all_60_clean_base_pairs_retained_regardless_of_clean_utility": True,
            "thresholds_changed_after_task_outcomes": False,
        }
    )
    attacked["required_bindings"] = [*attacked["required_bindings"], *bindings]
    attacked["paired_clean_binding"].update(
        {
            "protocol_path": CLEAN.relative_to(REPO_ROOT).as_posix(),
            "protocol_sha256": None,
            "evidence_path": f"{CLEAN_ROOT}/pilot_evidence.json",
            "evidence_sha256": None,
            "runtime_gate": "clean integrity completeness only; utility outcome does not filter or block",
        }
    )
    attacked["attack_records"] = derive_attack_transplants(
        clean, load_json_object(ATTACK_SOURCE)
    )

    dry_run = {
        "schema": "proofalign.remote-full120-llm-template-orchestration-dry-run.v1",
        "protocol_id": umbrella["protocol_id"],
        "outcomes_observed": False,
        "policy_loaded": False,
        "actions_dispatched": False,
        "clean": {**_balance(clean["schedule"]), "root": CLEAN_ROOT},
        "attacked": {**_balance(attacked["schedule"]), "root": ATTACKED_ROOT},
        "total_new_episode_count": 960,
        "same_120_units_and_four_arms": sorted(
            [
            (row["unit_id"], row["arm"], row["suite"], row["task_id"], row["init_state_id"])
            for row in clean["schedule"]
            ]
        )
        == sorted(
            [
            (row["unit_id"], row["arm"], row["suite"], row["task_id"], row["init_state_id"])
            for row in attacked["schedule"]
            ]
        ),
        "complete": True,
    }
    return umbrella, clean, attacked, dry_run


def main() -> int:
    umbrella, clean, attacked, dry_run = build()
    _write(UMBRELLA, umbrella)
    _write(CLEAN, clean)
    attacked["paired_clean_binding"]["protocol_sha256"] = file_sha256(CLEAN)
    _write(ATTACKED, attacked)
    _write(DRY_RUN, dry_run)
    print(
        canonical_text(
            {
                "umbrella": _binding(UMBRELLA),
                "clean": _binding(CLEAN),
                "attacked": _binding(ATTACKED),
                "dry_run": _binding(DRY_RUN),
                "new_episode_count": 960,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
