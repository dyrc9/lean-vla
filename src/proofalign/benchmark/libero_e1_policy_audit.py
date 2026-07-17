"""E1-v3 policy-output audit boundary.

The frozen E0-v2 online wrapper remains byte-identical to its protocol.  E1-v3
installs this compatible superset only inside its own process so OpenPI's
JSON-like audit metadata can be retained without changing E0 evidence.
"""

from __future__ import annotations

from math import isfinite
from typing import Any

from proofalign.benchmark.libero_online_wrapper import LiberoOnlineIntegrationError


def frozen_policy_value_copy(value: Any) -> Any:
    """Deep-copy one JSON-like policy value and fail closed on unsafe values."""

    return _copy(value, active=set(), depth=0)


def _copy(value: Any, *, active: set[int], depth: int) -> Any:
    if depth > 64:
        raise LiberoOnlineIntegrationError(
            "authorized action contains an excessively nested value"
        )
    if hasattr(value, "tolist"):
        return _copy(value.tolist(), active=active, depth=depth + 1)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise LiberoOnlineIntegrationError(
                "authorized action contains a non-finite number"
            )
        return value
    if isinstance(value, dict):
        marker = id(value)
        if marker in active:
            raise LiberoOnlineIntegrationError(
                "authorized action contains a cyclic dictionary"
            )
        active.add(marker)
        try:
            frozen: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise LiberoOnlineIntegrationError(
                        "authorized action metadata contains a non-string key"
                    )
                frozen[key] = _copy(item, active=active, depth=depth + 1)
            return frozen
        finally:
            active.remove(marker)
    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in active:
            raise LiberoOnlineIntegrationError(
                "authorized action contains a cyclic sequence"
            )
        active.add(marker)
        try:
            return tuple(
                _copy(item, active=active, depth=depth + 1) for item in value
            )
        finally:
            active.remove(marker)
    raise LiberoOnlineIntegrationError(
        f"authorized action contains unsupported value: {type(value).__name__}"
    )


def install_e1_policy_audit() -> None:
    """Install the E1-v3 audit copier into the frozen wrapper module."""

    from proofalign.benchmark import libero_online_wrapper

    libero_online_wrapper._frozen_action_copy = frozen_policy_value_copy
