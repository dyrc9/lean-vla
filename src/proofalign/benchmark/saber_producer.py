"""Small adapters for running the official SABER agent without a victim rollout.

The ART LangGraph integration stores its OpenAI-compatible endpoint in a
``ContextVar``.  That context is installed by ``wrap_rollout`` and therefore
``init_chat_model`` must be called from inside the wrapped coroutine.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any


async def run_text_agent_in_art_context(
    *,
    model: Any,
    wrap_rollout: Callable[[Any, Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]],
    init_chat_model: Callable[[], Any],
    official_text_agent: Callable[..., Awaitable[Any]],
    cap_chat_model_tokens: Callable[[Any], Any],
    attack_tools: Sequence[Any],
    messages: Sequence[Any],
    instruction: str,
    max_turns: int,
    logger: Any = None,
) -> Any:
    """Invoke SABER's official text-tool loop with ART's context installed.

    ``model`` must already be registered with its ART backend.  Keeping the
    chat-model construction in ``rollout`` is the important invariant: moving
    it above ``wrap_rollout`` reproduces the historical ``CURRENT_CONFIG``
    startup failure.
    """

    async def rollout(_registered_model: Any) -> Any:
        chat_model = cap_chat_model_tokens(init_chat_model())
        return await official_text_agent(
            chat_model,
            attack_tools,
            list(messages),
            instruction=instruction,
            max_turns=max_turns,
            _logger=logger,
        )

    wrapped = wrap_rollout(model, rollout)
    return await wrapped(model)
