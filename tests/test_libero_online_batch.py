from __future__ import annotations

import pytest

from scripts.run_libero_online_batch import (
    load_episode,
    main,
    parse_args,
    parse_task_ids,
    summarize,
    validate_batch_args,
)


def test_parse_task_ids_supports_ranges_and_deduplication():
    assert parse_task_ids("0-2,2,4") == [0, 1, 2, 4]


def test_batch_args_accept_multiple_init_state_ids():
    args = parse_args(
        [
            "--task-ids",
            "0",
            "--init-state-ids",
            "0-2",
            "--max-chunk-steps",
            "5",
            "--continue-on-replan",
            "--attack-record",
            "experiments/attack.json",
        ]
    )

    assert args.task_ids == "0"
    assert parse_task_ids(args.init_state_ids) == [0, 1, 2]
    assert args.max_chunk_steps == 5
    assert args.continue_on_replan
    assert args.attack_record == "experiments/attack.json"


def test_summarize_reports_per_init_state_breakdown():
    episodes = [
        {
            "metadata": {"benchmark_name": "affordance", "init_state_id": 0},
            "decision": "allow",
            "task_success": True,
            "trace": [{"decision": "allow", "env_info": {"cost": {}}, "runtime_seconds": {}}],
        },
        {
            "metadata": {"benchmark_name": "affordance", "init_state_id": 1},
            "decision": "reject",
            "task_success": False,
            "trace": [{"decision": "reject", "env_info": {"cost": {}}, "runtime_seconds": {}}],
        },
    ]
    failures = [{"suite": "affordance", "init_state_id": 1}]

    summary = summarize(expected_total=3, episodes=episodes, failures=failures, output_files=[])

    assert summary["per_init_state_breakdown"]["0"]["completed_episodes"] == 1
    assert summary["per_init_state_breakdown"]["1"]["total_episodes"] == 2
    assert summary["per_init_state_breakdown"]["1"]["failed_episodes"] == 1


def test_summarize_does_not_count_zero_cost_dict_as_collision():
    episodes = [
        {
            "metadata": {"benchmark_name": "obstacle_avoidance", "init_state_id": 0},
            "decision": "allow",
            "task_success": False,
            "trace": [
                {
                    "decision": "allow",
                    "env_info": {"cost": {"checkrobotcontact": 0, "checkcontact": 0}},
                    "runtime_seconds": {},
                }
            ],
        }
    ]

    summary = summarize(expected_total=1, episodes=episodes, failures=[], output_files=[])

    assert summary["episodes_with_cost_or_collision"] == 0


def test_summarize_counts_collision_or_cost_from_independent_fallback_trace():
    episodes = [
        {
            "metadata": {"benchmark_name": "obstacle_avoidance", "init_state_id": 0},
            "decision": "safe_stop",
            "task_success": False,
            "trace": [
                {
                    "decision": "safe_stop",
                    "env_info": {"cost": {}},
                    "runtime_seconds": {},
                    "ctda": {
                        "fallback_trace": {
                            "kind": "ctda_fallback",
                            "env_info": {"collision": False, "cost": {"contact": 1}},
                            "receipt": {
                                "succeeded": False,
                                "postcondition": {
                                    "no_collision": True,
                                    "no_cost": False,
                                }
                            },
                        }
                    },
                }
            ],
        }
    ]

    summary = summarize(expected_total=1, episodes=episodes, failures=[], output_files=[])

    assert summary["episodes_with_cost_or_collision"] == 1
    assert summary["ctda"]["fallback_attempt_count"] == 1
    assert summary["ctda"]["fallback_success_count"] == 0
    assert summary["ctda"]["fallback_failure_count"] == 1
    assert summary["ctda"]["fallback_error_count"] == 0


def test_summarize_counts_fallback_error_even_without_a_receipt():
    episode = {
        "metadata": {"benchmark_name": "affordance", "init_state_id": 0},
        "decision": "safe_stop",
        "trace": [
            {
                "decision": "safe_stop",
                "env_info": {},
                "runtime_seconds": {},
                "ctda": {"fallback_error": "actuator unavailable"},
            }
        ],
    }

    summary = summarize(
        expected_total=1, episodes=[episode], failures=[], output_files=[]
    )

    assert summary["ctda"]["fallback_attempt_count"] == 1
    assert summary["ctda"]["fallback_failure_count"] == 1
    assert summary["ctda"]["fallback_error_count"] == 1


def test_batch_disables_skip_existing_only_for_ctda() -> None:
    with pytest.raises(ValueError, match="disabled in CTDA mode"):
        validate_batch_args(parse_args(["--skip-existing", "--ctda"]))

    validate_batch_args(parse_args(["--skip-existing"]))


def test_load_episode_rejects_non_object_json(tmp_path) -> None:
    path = tmp_path / "episode.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        load_episode(path)
