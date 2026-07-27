"""ProofAlign mission-rooted integrity research prototypes.

The minimal Python fast checker and Lean core are currently separate artifacts;
the package does not claim a machine-checked refinement between them.
"""

__all__ = [
    "ProofAlignPrototype",
    "MethodArm",
    "ActionAssessmentKind",
    "ActionBlockAssessment",
    "BlockExecutionContract",
]


def __getattr__(name: str):
    if name == "ProofAlignPrototype":
        from proofalign.integrity_runtime import ProofAlignPrototype

        return ProofAlignPrototype
    if name in {
        "MethodArm",
        "ActionAssessmentKind",
        "ActionBlockAssessment",
        "BlockExecutionContract",
    }:
        from proofalign import integrity_models

        return getattr(integrity_models, name)
    raise AttributeError(name)
