from __future__ import annotations

from scripts.run_pi05_action_conditioning_e2 import (
    STAGE_SUBTASKS,
    compile_prompt,
)


def test_e2_uses_exact_runtime_prompt_and_stage_conflicts() -> None:
    prompt = compile_prompt(
        "Task: {task}\nCurrent semantic subtask: {subtask}",
        "put bowl on plate",
        "release(bowl_1)",
    )

    assert prompt == (
        "Task: put bowl on plate\n"
        "Current semantic subtask: release(bowl_1)"
    )
    assert STAGE_SUBTASKS["initial"]["expected"].startswith("pick_up")
    assert STAGE_SUBTASKS["release_command"]["expected"].startswith(
        "release"
    )
    assert STAGE_SUBTASKS["release_command"]["conflict"].startswith(
        "pick_up"
    )
