#!/usr/bin/env python3
"""Generate and validate per-task semantic templates with a local LLM."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from proofalign.llm_semantic_templates import (  # noqa: E402
    CATALOG_SCHEMA,
    generation_prompt,
    graph_from_template,
    validate_proposal,
)


DEFAULT_POPULATION = REPO_ROOT / "experiments/proofalign_remote_full120_clean_protocol_20260818.json"
DEFAULT_OUTPUT = REPO_ROOT / "experiments/proofalign_llm_semantic_template_catalog_20260818.json"
MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
MODEL_REVISION = "aa8e72537993ba99e69dfaafa59ed015b17504d1"
MODEL_PATH = Path(
    "/data0/ldx/saber-cache/huggingface/models--Qwen--Qwen2.5-3B-Instruct/"
    "snapshots/aa8e72537993ba99e69dfaafa59ed015b17504d1"
)


class CatalogGenerationError(RuntimeError):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=REPO_ROOT, text=True, capture_output=True)
    if result.returncode:
        raise CatalogGenerationError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def _load_model() -> tuple[Any, Any]:
    if not MODEL_PATH.is_dir():
        raise CatalogGenerationError(f"local LLM snapshot is absent: {MODEL_PATH}")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_PATH, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
        device_map="cuda",
    )
    model.eval()
    return tokenizer, model


def _generate(tokenizer: Any, model: Any, prompt: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Compile trusted robot task goals into the exact JSON DSL. "
                "Never add entities, predicates, parts, or phases."
            ),
        },
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    output = model.generate(
        **inputs,
        max_new_tokens=256,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
    return tokenizer.decode(
        output[0, inputs.input_ids.shape[1] :], skip_special_tokens=True
    ).strip()


def build_catalog(population_path: Path) -> dict[str, Any]:
    population = load_json_object(population_path)
    tokenizer, model = _load_model()
    templates = []
    seen: set[str] = set()
    for workload in population["workloads"]:
        bddl_path = REPO_ROOT / str(workload["bddl_path"])
        bddl_text = bddl_path.read_text(encoding="utf-8")
        prompt = generation_prompt(
            trusted_instruction=str(workload["trusted_instruction"]),
            bddl_text=bddl_text,
        )
        raw = _generate(tokenizer, model, prompt)
        try:
            row = validate_proposal(
                trusted_instruction=str(workload["trusted_instruction"]),
                bddl_text=bddl_text,
                raw_response=raw,
                model_id=MODEL_ID,
                model_revision=MODEL_REVISION,
            )
        except ValueError as exc:
            raise CatalogGenerationError(
                f"LLM template rejected for {workload['base_pair_id']}: {exc}; raw={raw!r}"
            ) from exc
        graph_from_template(bddl_text=bddl_text, template=row)
        digest = str(row["trusted_bddl_sha256"])
        if digest in seen:
            raise CatalogGenerationError(
                f"duplicate trusted BDDL digest: {workload['base_pair_id']}"
            )
        seen.add(digest)
        templates.append(
            {
                **row,
                "base_pair_id": workload["base_pair_id"],
                "suite": workload["suite"],
                "task_id": workload["task_id"],
                "init_state_id": workload["init_state_id"],
                "bddl_path": workload["bddl_path"],
                "bddl_file_sha256": file_sha256(bddl_path),
            }
        )
        print(f"validated {len(templates):02d}/60 {workload['base_pair_id']}", file=sys.stderr)
    return {
        "schema": CATALOG_SCHEMA,
        "catalog_id": "proofalign-full120-qwen25-trusted-template-catalog-20260818",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "population_path": population_path.relative_to(REPO_ROOT).as_posix(),
        "population_sha256": file_sha256(population_path),
        "model": {
            "id": MODEL_ID,
            "revision": MODEL_REVISION,
            "local_snapshot": str(MODEL_PATH),
            "generation": {
                "do_sample": False,
                "temperature": None,
                "max_new_tokens": 256,
            },
        },
        "threat_boundary": {
            "generator_inputs": ["trusted_instruction", "trusted_bddl_goal"],
            "attacked_prompt_visible": False,
            "policy_observation_visible": False,
            "task_outcome_visible": False,
            "llm_output_authoritative": False,
            "runtime_llm_calls": 0,
            "validation": "exact BDDL reconstruction plus allow-listed DSL",
        },
        "template_count": len(templates),
        "templates": templates,
        "source": {
            "repository_commit": _git("rev-parse", "HEAD"),
            "repository_tree": _git("rev-parse", "HEAD^{tree}"),
            "generator": Path(__file__).resolve().relative_to(REPO_ROOT).as_posix(),
            "generator_sha256": file_sha256(Path(__file__).resolve()),
        },
    }


def validate_catalog(path: Path) -> dict[str, Any]:
    catalog = load_json_object(path)
    if catalog.get("schema") != CATALOG_SCHEMA or catalog.get("template_count") != 60:
        raise CatalogGenerationError("catalog schema or population count differs")
    observed = set()
    for row in catalog["templates"]:
        bddl_path = REPO_ROOT / str(row["bddl_path"])
        bddl_text = bddl_path.read_text(encoding="utf-8")
        if file_sha256(bddl_path) != row["bddl_file_sha256"]:
            raise CatalogGenerationError(f"BDDL checksum differs: {bddl_path}")
        graph_from_template(bddl_text=bddl_text, template=row)
        observed.add(str(row["base_pair_id"]))
    if len(observed) != 60:
        raise CatalogGenerationError("catalog base-pair coverage differs")
    return {
        "valid": True,
        "template_count": 60,
        "catalog_sha256": file_sha256(path),
        "attacked_prompt_visible": False,
        "runtime_llm_calls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generate", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--population", type=Path, default=DEFAULT_POPULATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.generate:
        catalog = build_catalog(args.population.resolve())
        args.output.write_text(canonical_text(catalog), encoding="utf-8")
        print(args.output)
    else:
        print(canonical_text(validate_catalog(args.output.resolve())), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
