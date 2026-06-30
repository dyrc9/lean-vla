"""ProofAlign: a Lean-backed dual alignment safety wrapper prototype."""

__all__ = ["DualAlignmentChecker", "SafetyExecutor"]


def __getattr__(name: str):
    if name == "DualAlignmentChecker":
        from proofalign.checker import DualAlignmentChecker

        return DualAlignmentChecker
    if name == "SafetyExecutor":
        from proofalign.executor import SafetyExecutor

        return SafetyExecutor
    raise AttributeError(name)
