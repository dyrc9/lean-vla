from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts.run_phantom_menace_r0b import (
    DEFAULT_PROTOCOL,
    EpisodeSpec,
    ProtocolError,
    attack_specs,
    client_command,
    load_protocol,
    print_dry_run,
    qualifying_pairs,
    validate_episode_artifacts,
    validate_protocol,
)


def test_protocol_freezes_candidate_and_full_attack_order() -> None:
    protocol = load_protocol(DEFAULT_PROTOCOL)

    candidates = [
        (item["task_id"], item["init_state_id"])
        for item in protocol["clean_screening"]["candidate_order"]
    ]
    assert candidates == [
        (task_id, init_id)
        for init_id in (0, 1)
        for task_id in (3, 4, 5, 6, 7, 8, 9, 0, 1)
    ]
    specs = attack_specs(protocol, ((3, 0), (4, 0), (5, 0)))
    assert len(specs) == 27
    assert [
        (item.attack_type, item.attack_strength, item.task_id, item.init_state_id)
        for item in specs[:6]
    ] == [
        ("laser_blinding", "weak", 3, 0),
        ("laser_blinding", "weak", 4, 0),
        ("laser_blinding", "weak", 5, 0),
        ("laser_blinding", "medium", 3, 0),
        ("laser_blinding", "medium", 4, 0),
        ("laser_blinding", "medium", 5, 0),
    ]
    assert (specs[-1].attack_type, specs[-1].attack_strength) == (
        "ultrasound_blur",
        "strong",
    )


def test_protocol_rejects_task2_and_attack_reordering() -> None:
    protocol = load_protocol(DEFAULT_PROTOCOL)
    with_task2 = deepcopy(protocol)
    with_task2["clean_screening"]["candidate_order"][0]["task_id"] = 2
    with pytest.raises(ProtocolError, match="candidate order"):
        validate_protocol(with_task2)

    reordered = deepcopy(protocol)
    reordered["attack_grid"]["ordered_cells"].reverse()
    with pytest.raises(ProtocolError, match="ordered attack cells"):
        validate_protocol(reordered)


def test_dry_run_displays_all_27_attacks(capsys: pytest.CaptureFixture[str]) -> None:
    protocol = load_protocol(DEFAULT_PROTOCOL)

    print_dry_run(protocol, [])

    output = capsys.readouterr().out.splitlines()
    assert sum(line.startswith("CLEAN ") for line in output) == 18
    assert sum(line.startswith("ATTACK ") for line in output) == 27
    assert output[-1] == "TOTAL attack episodes=27"


def test_qualifying_pairs_use_first_three_valid_clean_successes() -> None:
    protocol = load_protocol(DEFAULT_PROTOCOL)
    ledger = [
        {"episode_id": "clean_task3_init0", "valid": True, "success": False},
        {"episode_id": "clean_task4_init0", "valid": False, "success": True},
        {"episode_id": "clean_task5_init0", "valid": True, "success": True},
        {"episode_id": "clean_task6_init0", "valid": True, "success": True},
        {"episode_id": "clean_task7_init0", "valid": True, "success": True},
        {"episode_id": "clean_task8_init0", "valid": True, "success": True},
    ]

    assert qualifying_pairs(protocol, ledger) == [(5, 0), (6, 0), (7, 0)]


def _write_episode(
    protocol: dict,
    spec: EpisodeSpec,
    episode_dir: Path,
    *,
    changed: bool,
    initial_sha: str = "initial",
    first_frame_sha: str = "frame",
) -> dict:
    (episode_dir / "server" / "policy_records").mkdir(parents=True)
    (episode_dir / "server" / "policy_records" / "step_0.npy").write_bytes(b"record")
    (episode_dir / "videos").mkdir()
    video_path = episode_dir / "videos" / "rollout.mp4"
    video_path.write_bytes(b"video")
    frame = {
        "policy_call_index": 0,
        "attack_changed_agentview": changed,
        "clean_agentview": {"sha256": first_frame_sha},
        "attacked_agentview": {"sha256": "attacked" if changed else first_frame_sha},
    }
    config = protocol["episode_config"]
    record = {
        "schema": "phantom_menace.openpi_episode.v1",
        "task_suite": config["suite"],
        "task_id": spec.task_id,
        "init_state_id": spec.init_state_id,
        "seed": config["env_seed"],
        "max_steps": config["horizon"],
        "replan_steps": config["replan_steps"],
        "attack_type": spec.attack_type,
        "attack_strength": spec.attack_strength,
        "attack_parameters": {},
        "fail_on_attack_error": True,
        "error": None,
        "video_error": None,
        "outcome": "failure",
        "success": False,
        "policy_calls": 1,
        "executed_actions": 220,
        "initial_state": {"sha256": initial_sha},
        "frame_digests": [frame],
        "frame_digest_manifest_sha256": "manifest",
        "video": str(video_path),
        "video_sha256": sha256(b"video").hexdigest(),
    }
    (episode_dir / "episodes.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    return record


def test_artifact_validation_accepts_paired_attack_and_rejects_fallback(
    tmp_path: Path,
) -> None:
    protocol = load_protocol(DEFAULT_PROTOCOL)
    clean_spec = EpisodeSpec("clean", 3, 0, "none", "weak", 1)
    clean_dir = tmp_path / "clean_task3_init0"
    clean_record = _write_episode(protocol, clean_spec, clean_dir, changed=False)
    record, issues, details = validate_episode_artifacts(
        protocol,
        clean_spec,
        clean_dir,
        clean_record=None,
        client_returncode=0,
    )
    assert record is not None
    assert issues == []
    assert details["policy_record_count"] == 1

    attack_spec = EpisodeSpec("attack", 3, 0, "laser_blinding", "weak", 1)
    attack_dir = tmp_path / "attack_task3_init0_laser_blinding_weak"
    _write_episode(protocol, attack_spec, attack_dir, changed=True)
    _, issues, details = validate_episode_artifacts(
        protocol,
        attack_spec,
        attack_dir,
        clean_record=clean_record,
        client_returncode=0,
    )
    assert issues == []
    assert details["changed_frame_count"] == 1

    attack_record = json.loads((attack_dir / "episodes.jsonl").read_text())
    attack_record["frame_digests"][0]["attack_changed_agentview"] = False
    (attack_dir / "episodes.jsonl").write_text(
        json.dumps(attack_record) + "\n", encoding="utf-8"
    )
    _, issues, _ = validate_episode_artifacts(
        protocol,
        attack_spec,
        attack_dir,
        clean_record=clean_record,
        client_returncode=0,
    )
    assert "not every attacked policy frame changed" in issues


def test_client_command_has_no_dynamic_attack_selection(tmp_path: Path) -> None:
    protocol = load_protocol(DEFAULT_PROTOCOL)
    spec = EpisodeSpec("attack", 3, 0, "em_truncation", "strong", 9)

    command = client_command(protocol, spec, tmp_path)

    assert command[command.index("--args.attack-type") + 1] == "em_truncation"
    assert command[command.index("--args.attack-strength") + 1] == "strong"
    assert command[command.index("--args.max-steps-override") + 1] == "220"
    assert "--args.fail-on-attack-error" in command
    assert "--args.no-use-wandb" in command
