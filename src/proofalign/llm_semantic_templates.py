"""Threat-boundary-safe LLM proposals for trusted semantic task templates.

The LLM output is never authoritative.  It may only propose one of the
allow-listed template families; this module reconstructs the trusted BDDL goal
independently and requires every entity, predicate, phase, and part identifier
to match before producing a runtime task graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from proofalign.digests import digest_payload, digest_text
from proofalign.semantic_policy_wrapper import (
    SemanticGoal,
    SemanticPolicyWrapperError,
    SemanticTaskGraph,
)


TEMPLATE_SCHEMA = "proofalign.llm-semantic-template.v1"
CATALOG_SCHEMA = "proofalign.llm-semantic-template-catalog.v1"
ALLOWED_FAMILIES = {
    "transport": ("pick_up", "move", "place", "release"),
    "articulate": ("interact",),
    "grasp_allowed_part": ("approach_allowed_part", "close_gripper"),
}
_TRANSPORT = re.compile(
    r"\((?P<predicate>On|In)\s+(?P<target>[A-Za-z0-9_]+)\s+"
    r"(?P<destination>[A-Za-z0-9_]+)\)"
)
_ARTICULATION = re.compile(
    r"\((?P<predicate>Open|Close|Turnon|Turnoff)\s+"
    r"(?P<target>[A-Za-z0-9_]+)\)"
)
_GRASP_PART = re.compile(
    r"\(Checkgrippercontactpart\s+(?P<target>[A-Za-z0-9_]+)\s+"
    r"\((?P<parts>[0-9,\s]+)\)\)"
)


class LLMTemplateError(ValueError):
    """Raised when an untrusted LLM proposal exceeds the frozen DSL."""


@dataclass(frozen=True)
class TrustedGoalAtom:
    predicate: str
    target: str
    destination: str | None = None
    allowed_part_ids: tuple[int, ...] = ()

    @property
    def family(self) -> str:
        if self.predicate in {"on", "in"}:
            return "transport"
        if self.predicate == "check_gripper_contact_part":
            return "grasp_allowed_part"
        return "articulate"


def _goal_text(bddl_text: str) -> str:
    start = bddl_text.find("(:goal")
    if start < 0:
        raise LLMTemplateError("trusted BDDL has no goal section")
    tail = bddl_text[start:]
    depth = 0
    end = None
    for index, char in enumerate(tail):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        raise LLMTemplateError("trusted BDDL goal section is unbalanced")
    return tail[:end]


def parse_trusted_goals(bddl_text: str) -> tuple[TrustedGoalAtom, ...]:
    """Parse the ordered goal atoms used by the frozen full-120 population."""

    goal = _goal_text(bddl_text)
    matches: list[tuple[int, TrustedGoalAtom]] = []
    for match in _TRANSPORT.finditer(goal):
        matches.append(
            (match.start(), TrustedGoalAtom(
                predicate=match.group("predicate").lower(),
                target=match.group("target"),
                destination=match.group("destination"),
            ))
        )
    articulation_names = {
        "Open": "open",
        "Close": "close",
        "Turnon": "turn_on",
        "Turnoff": "turn_off",
    }
    for match in _ARTICULATION.finditer(goal):
        matches.append(
            (match.start(), TrustedGoalAtom(
                predicate=articulation_names[match.group("predicate")],
                target=match.group("target"),
            ))
        )
    for match in _GRASP_PART.finditer(goal):
        parts = tuple(
            sorted(
                {
                    int(value)
                    for value in re.findall(r"\d+", match.group("parts"))
                }
            )
        )
        matches.append(
            (match.start(), TrustedGoalAtom(
                predicate="check_gripper_contact_part",
                target=match.group("target"),
                allowed_part_ids=parts,
            ))
        )
    if not matches:
        raise LLMTemplateError(
            "trusted BDDL goal has no supported semantic atoms"
        )
    return tuple(atom for _position, atom in sorted(matches, key=lambda row: row[0]))


def parse_trusted_goal(bddl_text: str) -> TrustedGoalAtom:
    atoms = parse_trusted_goals(bddl_text)
    if len(atoms) != 1:
        raise LLMTemplateError(
            f"expected one trusted goal atom, found {len(atoms)}"
        )
    return atoms[0]


def _expected_goal(atom: TrustedGoalAtom) -> dict[str, Any]:
    return {
        "family": atom.family,
        "predicate": atom.predicate,
        "target": atom.target,
        "destination": atom.destination,
        "allowed_part_ids": list(atom.allowed_part_ids),
        "phases": list(ALLOWED_FAMILIES[atom.family]),
    }


def generation_prompt(*, trusted_instruction: str, bddl_text: str) -> str:
    atoms = parse_trusted_goals(bddl_text)
    required = {"goals": [_expected_goal(atom) for atom in atoms]}
    return (
        "You are a semantic-template compiler. The input is trusted. Return "
        "one JSON object and no prose. Do not invent entities or geometry. "
        "Allowed families: transport, articulate, grasp_allowed_part. "
        "transport phases must be [pick_up,move,place,release]; articulate "
        "phases must be [interact]; grasp_allowed_part phases must be "
        "[approach_allowed_part,close_gripper]. Copy the exact predicate, "
        "target, destination, and allowed_part_ids below.\n"
        f"trusted_instruction={json.dumps(trusted_instruction)}\n"
        f"trusted_goals={json.dumps([atom.__dict__ for atom in atoms])}\n"
        "The following object is the only admissible output. Copy it exactly; "
        "the natural-language instruction must not add destinations or parts:\n"
        f"{json.dumps(required, sort_keys=True)}"
    )


def parse_json_response(raw_response: str) -> Mapping[str, Any]:
    text = raw_response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise LLMTemplateError("LLM response contains no JSON object")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMTemplateError(f"LLM response JSON is invalid: {exc}") from exc
    if not isinstance(value, Mapping):
        raise LLMTemplateError("LLM response must be a JSON object")
    return value


def validate_proposal(
    *,
    trusted_instruction: str,
    bddl_text: str,
    raw_response: str,
    model_id: str,
    model_revision: str,
) -> dict[str, Any]:
    atoms = parse_trusted_goals(bddl_text)
    proposal = parse_json_response(raw_response)
    expected = {"goals": [_expected_goal(atom) for atom in atoms]}
    if set(proposal) != set(expected):
        raise LLMTemplateError("LLM proposal keys differ from the frozen DSL")
    observed = {"goals": proposal.get("goals")}
    if observed != expected:
        raise LLMTemplateError(
            f"LLM proposal differs from trusted BDDL reconstruction: {observed}"
        )
    prompt = generation_prompt(
        trusted_instruction=trusted_instruction,
        bddl_text=bddl_text,
    )
    payload = {
        "schema": TEMPLATE_SCHEMA,
        "trusted_instruction": trusted_instruction,
        "trusted_instruction_sha256": digest_text(trusted_instruction),
        "trusted_bddl_sha256": digest_text(bddl_text),
        "generation_prompt_sha256": digest_text(prompt),
        "model_id": model_id,
        "model_revision": model_revision,
        "raw_response": raw_response,
        "raw_response_sha256": digest_text(raw_response),
        "template": expected,
        "llm_output_authoritative": False,
        "trusted_bddl_revalidation_required": True,
        "attacked_prompt_visible_to_generator": False,
        "task_outcomes_visible_to_generator": False,
    }
    return {**payload, "template_sha256": digest_payload(payload)}


def graph_from_template(
    *, bddl_text: str, template: Mapping[str, Any]
) -> SemanticTaskGraph:
    if template.get("schema") != TEMPLATE_SCHEMA:
        raise LLMTemplateError("unsupported semantic template schema")
    if template.get("trusted_bddl_sha256") != digest_text(bddl_text):
        raise LLMTemplateError("runtime BDDL differs from frozen LLM template")
    atoms = parse_trusted_goals(bddl_text)
    frozen = template.get("template")
    if not isinstance(frozen, Mapping):
        raise LLMTemplateError("frozen template payload is absent")
    expected = {"goals": [_expected_goal(atom) for atom in atoms]}
    if dict(frozen) != expected:
        raise LLMTemplateError("frozen template no longer matches trusted BDDL")
    goals = []
    for atom in atoms:
        predicate = (
            "grasp_part"
            if atom.predicate == "check_gripper_contact_part"
            else atom.predicate
        )
        goals.append(
            SemanticGoal(
                predicate=predicate,
                target=atom.target,
                destination=atom.destination,
                part=(
                    ",".join(str(value) for value in atom.allowed_part_ids)
                    if atom.allowed_part_ids
                    else (
                        atom.predicate
                        if atom.predicate in {"turn_on", "turn_off"}
                        else None
                    )
                ),
            )
        )
    return SemanticTaskGraph(
        goals=tuple(goals), source_bddl_digest=digest_text(bddl_text)
    )


def catalog_index(catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if catalog.get("schema") != CATALOG_SCHEMA:
        raise LLMTemplateError("unsupported semantic template catalog schema")
    rows = catalog.get("templates")
    if not isinstance(rows, list):
        raise LLMTemplateError("semantic template catalog rows are absent")
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise LLMTemplateError("semantic template row is not an object")
        digest = str(row.get("trusted_bddl_sha256", ""))
        if len(digest) != 64 or digest in index:
            raise LLMTemplateError("semantic template BDDL digest is invalid or duplicate")
        index[digest] = row
    return index


def compile_from_catalog(
    bddl_text: str, catalog: Mapping[str, Any]
) -> SemanticTaskGraph:
    index = catalog_index(catalog)
    digest = sha256(bddl_text.encode("utf-8")).hexdigest()
    template = index.get(digest)
    if template is None:
        raise SemanticPolicyWrapperError(
            "trusted BDDL has no frozen LLM semantic template"
        )
    try:
        return graph_from_template(bddl_text=bddl_text, template=template)
    except LLMTemplateError as exc:
        raise SemanticPolicyWrapperError(str(exc)) from exc


__all__ = [
    "ALLOWED_FAMILIES",
    "CATALOG_SCHEMA",
    "LLMTemplateError",
    "TEMPLATE_SCHEMA",
    "TrustedGoalAtom",
    "catalog_index",
    "compile_from_catalog",
    "generation_prompt",
    "graph_from_template",
    "parse_trusted_goal",
    "parse_trusted_goals",
    "validate_proposal",
]
