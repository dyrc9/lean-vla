from __future__ import annotations

import re

from proofalign.models import TaskIntent


DANGEROUS_PATTERNS = [
    "stab",
    "hurt",
    "harm",
    "attack",
    "weapon",
    "by the blade",
]

UNSAFE_CUT_TARGETS = [
    "hand",
    "human",
    "person",
    "body",
]

KNOWN_OBJECT_PHRASES = [
    "akita black bowl",
    "black akita bowl",
    "cream cheese box",
    "alphabet soup",
    "moka pot",
    "soda can",
    "white yellow mug",
    "wooden bowl",
    "dish towel",
    "wine bottle",
    "porcelain mug",
    "game console",
    "human hand",
    "knife",
    "scissors",
    "hammer",
    "fork",
    "mug",
    "bowl",
    "banana",
    "apple",
    "plate",
    "book",
    "frypan",
    "vase",
    "ketchup",
    "milk",
    "butter",
]

KNOWN_REGIONS = [
    "target region",
    "cutting board",
    "plate",
    "basket",
    "stove",
    "microwave",
    "cabinet",
    "drawer",
]


def parse_intent(instruction: str) -> TaskIntent:
    """Parse a small, explicit instruction language into a symbolic intent.

    This parser is deliberately rule based. In the prototype, LLM/VLA reasoning
    lives outside the trusted checker boundary.
    """

    text = instruction.lower().strip()
    unsafe_cut = "cut" in text and any(target in text for target in UNSAFE_CUT_TARGETS)
    if text.startswith("do not ") or unsafe_cut or any(pattern in text for pattern in DANGEROUS_PATTERNS):
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

    place_target = _parse_place_target(text)
    known_object = _known_object(text)
    known_region = _known_region(text)

    if known_object and any(word in text for word in ("bring", "deliver", "pass")):
        return TaskIntent(
            raw_instruction=instruction,
            verb="place",
            target_object=known_object,
            target_region=known_region or "target_region",
            avoid_objects=avoid_objects,
        )

    if place_target:
        target_object, target_region = place_target
        return TaskIntent(
            raw_instruction=instruction,
            verb="place",
            target_object=target_object,
            target_region=target_region,
            avoid_objects=avoid_objects,
        )

    if known_object and any(word in text for word in ("place", "put")) and known_region:
        return TaskIntent(
            raw_instruction=instruction,
            verb="place",
            target_object=known_object,
            target_region=known_region,
            avoid_objects=avoid_objects,
        )

    pick_match = re.search(r"pick up the (?P<object>[a-z0-9_-]+)(?: by the (?P<part>[a-z0-9_-]+))?", text)
    if pick_match:
        return TaskIntent(
            raw_instruction=instruction,
            verb="pick",
            target_object=pick_match.group("object"),
            target_part=pick_match.group("part"),
            avoid_objects=avoid_objects,
        )

    if known_object and any(word in text for word in ("pick", "grab", "get", "retrieve")):
        part = "handle" if known_object in {"knife", "scissors", "hammer"} else None
        return TaskIntent(
            raw_instruction=instruction,
            verb="pick",
            target_object=known_object,
            target_part=part,
            avoid_objects=avoid_objects,
        )

    grab_match = re.search(r"(?:grab|get|retrieve) the (?P<object>[a-z0-9_-]+)", text)
    if grab_match:
        part = "handle" if grab_match.group("object") in {"knife", "scissors", "hammer"} else None
        return TaskIntent(
            raw_instruction=instruction,
            verb="pick",
            target_object=grab_match.group("object"),
            target_part=part,
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


def _known_object(text: str) -> str | None:
    normalized = text.replace("_", " ")
    for phrase in KNOWN_OBJECT_PHRASES:
        if phrase in normalized:
            return phrase.replace(" ", "_")
    return None


def _known_region(text: str) -> str | None:
    normalized = text.replace("_", " ")
    for phrase in KNOWN_REGIONS:
        if phrase in normalized:
            return phrase.replace(" ", "_")
    return None


def _parse_place_target(text: str) -> tuple[str, str] | None:
    match = re.search(
        r"\b(?:place|put)\s+the\s+(?P<object>.+?)\s+(?:on|in|into)\s+the\s+(?P<region>.+?)(?:\s+while\b|\s+without\b|$)",
        text,
    )
    if not match:
        return None
    object_text = match.group("object").strip()
    region_text = match.group("region").strip()
    target_object = _known_object(object_text) or _symbolize(object_text)
    target_region = _known_region(region_text) or _symbolize(region_text)
    return target_object, target_region


def _symbolize(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.replace("-", "_")).strip("_")
