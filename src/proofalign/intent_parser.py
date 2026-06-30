from __future__ import annotations

import re

from proofalign.models import TaskIntent


DANGEROUS_PATTERNS = [
    "stab",
    "cut",
    "hurt",
    "harm",
    "attack",
    "weapon",
    "by the blade",
]


def parse_intent(instruction: str) -> TaskIntent:
    """Parse a small, explicit instruction language into a symbolic intent.

    This parser is deliberately rule based. In the prototype, LLM/VLA reasoning
    lives outside the trusted checker boundary.
    """

    text = instruction.lower().strip()
    if text.startswith("do not ") or any(pattern in text for pattern in DANGEROUS_PATTERNS):
        return TaskIntent(
            raw_instruction=instruction,
            verb="reject",
            reject_required=True,
            unsafe_reason="instruction is negative or requests a dangerous contact",
        )

    avoid_objects = []
    for avoid_word in ["human hand", "hand", "obstacle", "knife", "blade"]:
        if f"avoiding the {avoid_word}" in text or f"without touching the {avoid_word}" in text or f"avoid {avoid_word}" in text:
            avoid_objects.append(avoid_word.replace(" ", "_"))

    pick_match = re.search(r"pick up the (?P<object>[a-z0-9_-]+)(?: by the (?P<part>[a-z0-9_-]+))?", text)
    if pick_match:
        return TaskIntent(
            raw_instruction=instruction,
            verb="pick",
            target_object=pick_match.group("object"),
            target_part=pick_match.group("part"),
            avoid_objects=avoid_objects,
        )

    place_match = re.search(r"place the (?P<object>[a-z0-9_-]+) (?:on|in|into) the (?P<region>[a-z0-9_-]+)", text)
    if place_match:
        return TaskIntent(
            raw_instruction=instruction,
            verb="place",
            target_object=place_match.group("object"),
            target_region=place_match.group("region"),
            avoid_objects=avoid_objects,
        )

    move_match = re.search(r"move the (?P<object>[a-z0-9_-]+) to the (?P<region>[a-z0-9_-]+(?: region)?)", text)
    if move_match:
        return TaskIntent(
            raw_instruction=instruction,
            verb="move",
            target_object=move_match.group("object"),
            target_region=move_match.group("region").replace(" ", "_"),
            avoid_objects=avoid_objects,
        )

    return TaskIntent(
        raw_instruction=instruction,
        verb="unknown",
        reject_required=True,
        unsafe_reason="instruction is outside the supported prototype grammar",
    )
