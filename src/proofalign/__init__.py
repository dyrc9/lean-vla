"""ProofAlign mission-rooted integrity research prototypes.

The minimal Python fast checker and Lean core are currently separate artifacts;
the package does not claim a machine-checked refinement between them.
"""

__all__ = [
    "ProofAlignPrototype",
    "MethodArm",
]


def __getattr__(name: str):
    if name == "ProofAlignPrototype":
        from proofalign.integrity_runtime import ProofAlignPrototype

        return ProofAlignPrototype
    if name == "MethodArm":
        from proofalign.integrity_models import MethodArm

        return MethodArm
    raise AttributeError(name)
