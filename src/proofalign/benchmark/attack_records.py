from __future__ import annotations

import json
import warnings
from dataclasses import replace
from pathlib import Path
from typing import Any


AttackRecordIndex = dict[tuple[str, int, int], dict[str, Any]]


def load_attack_record_index(path: str | Path | None) -> AttackRecordIndex:
    if not path:
        return {}
    record_path = Path(path).expanduser()
    text = record_path.read_text(encoding="utf-8")
    records: list[dict[str, Any]]
    if record_path.suffix == ".jsonl":
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        data = json.loads(text)
        if isinstance(data, dict) and "records" in data:
            data = data["records"]
        if not isinstance(data, list):
            raise ValueError(f"Attack record must be a JSON list or JSONL file: {record_path}")
        records = list(data)

    index: AttackRecordIndex = {}
    for record in records:
        key = attack_record_key(record)
        if key in index:
            raise ValueError(f"Duplicate attack record key {key!r} in {record_path}")
        index[key] = dict(record)
    return index


def attack_record_key(record: dict[str, Any]) -> tuple[str, int, int]:
    suite = record.get("suite", record.get("benchmark_name"))
    if suite is None:
        raise ValueError(f"Attack record is missing suite/benchmark_name: {record!r}")
    try:
        return (str(suite), int(record["task_id"]), int(record["init_state_id"]))
    except KeyError as exc:
        raise ValueError(f"Attack record is missing required key {exc.args[0]!r}: {record!r}") from exc


def get_attack_record(
    records: AttackRecordIndex,
    *,
    suite: str,
    task_id: int,
    init_state_id: int,
) -> dict[str, Any] | None:
    return records.get((suite, int(task_id), int(init_state_id)))


def apply_attack_record(runtime: Any, record: dict[str, Any] | None) -> Any:
    if not record:
        return runtime
    perturbed = record.get("perturbed_instruction")
    if not isinstance(perturbed, str) or not perturbed:
        raise ValueError(f"Attack record is missing non-empty perturbed_instruction: {record!r}")

    original = str(record.get("original_instruction", ""))
    runtime_instruction = str(getattr(runtime, "instruction", ""))
    if original and original != runtime_instruction:
        warnings.warn(
            "Attack record original_instruction does not exactly match runtime instruction "
            f"for {record.get('suite', record.get('benchmark_name'))} task_id={record.get('task_id')} "
            f"init_state_id={record.get('init_state_id')}: record={original!r}, runtime={runtime_instruction!r}",
            RuntimeWarning,
            stacklevel=2,
        )

    metadata = dict(getattr(runtime, "metadata", {}) or {})
    metadata.update(attack_metadata(record, fallback_original=runtime_instruction))
    return replace(runtime, instruction=perturbed, metadata=metadata)


def attack_metadata(record: dict[str, Any], *, fallback_original: str) -> dict[str, Any]:
    return {
        # The benchmark-owned instruction remains the only trusted task root.
        # A record's copy is retained strictly as an untrusted audit field.
        "original_instruction": fallback_original,
        "attack_record_claimed_original_instruction": record.get("original_instruction"),
        "perturbed_instruction": str(record["perturbed_instruction"]),
        "attack_objective": record.get("objective"),
        "attack_tools_used": list(record.get("tools_used") or []),
        "attack_record_source": record.get("source"),
    }
