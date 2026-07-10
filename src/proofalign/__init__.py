"""ProofAlign: a Lean-backed dual alignment safety wrapper prototype."""

__all__ = [
    "CTDAChecker",
    "CTDARuntimeSession",
    "CTDASupervisor",
    "DualAlignmentChecker",
    "SafetyExecutor",
]


def __getattr__(name: str):
    if name == "DualAlignmentChecker":
        from proofalign.checker import DualAlignmentChecker

        return DualAlignmentChecker
    if name == "SafetyExecutor":
        from proofalign.executor import SafetyExecutor

        return SafetyExecutor
    if name in {"CTDAChecker", "CTDASupervisor"}:
        from proofalign.ctda import CTDAChecker, CTDASupervisor

        return {"CTDAChecker": CTDAChecker, "CTDASupervisor": CTDASupervisor}[name]
    if name == "CTDARuntimeSession":
        from proofalign.ctda_runtime import CTDARuntimeSession

        return CTDARuntimeSession
    raise AttributeError(name)
