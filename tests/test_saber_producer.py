from __future__ import annotations

import asyncio
import contextvars

import pytest

from proofalign.benchmark.saber_producer import run_text_agent_in_art_context


def test_chat_model_is_created_inside_art_rollout_context() -> None:
    async def exercise() -> None:
        current_config: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
            "CURRENT_CONFIG"
        )
        registered_model = object()
        observed: dict[str, object] = {}

        def init_chat_model() -> dict[str, str]:
            return {"endpoint": current_config.get()["endpoint"]}

        def wrap_rollout(model: object, fn):
            assert model is registered_model

            async def wrapped(call_model: object):
                assert call_model is registered_model
                token = current_config.set({"endpoint": "http://127.0.0.1:9000/v1"})
                try:
                    return await fn(call_model)
                finally:
                    current_config.reset(token)

            return wrapped

        async def official_text_agent(chat_model, tools, messages, **kwargs):
            observed.update(
                chat_model=chat_model,
                tools=tools,
                messages=messages,
                kwargs=kwargs,
            )
            return {"messages": ["ok"]}

        result = await run_text_agent_in_art_context(
            model=registered_model,
            wrap_rollout=wrap_rollout,
            init_chat_model=init_chat_model,
            official_text_agent=official_text_agent,
            cap_chat_model_tokens=lambda model: model,
            attack_tools=["prompt-tool"],
            messages=["system", "user"],
            instruction="move the bowl",
            max_turns=8,
            logger="logger",
        )

        assert result == {"messages": ["ok"]}
        assert observed["chat_model"] == {"endpoint": "http://127.0.0.1:9000/v1"}
        assert observed["tools"] == ["prompt-tool"]
        assert observed["messages"] == ["system", "user"]
        assert observed["kwargs"] == {
            "instruction": "move the bowl",
            "max_turns": 8,
            "_logger": "logger",
        }

    asyncio.run(exercise())


def test_direct_chat_model_initialization_reproduces_missing_context() -> None:
    current_config: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
        "CURRENT_CONFIG"
    )

    with pytest.raises(LookupError):
        current_config.get()
