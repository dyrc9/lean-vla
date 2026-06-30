from __future__ import annotations

from proofalign.action_abstraction import action_from_dict
from proofalign.certificates import CertificateBundle
from proofalign.checker import DualAlignmentChecker
from proofalign.intent_parser import parse_intent
from proofalign.models import SafetySpec


def test_required_certificates_reject_missing_pre_certificate(safe_state):
    spec = SafetySpec(require_certificates=True)
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, spec, CertificateBundle())

    assert not result.passed
    assert any("missing object_identity certificate" in violation for violation in result.violations)
    assert any(report.violation_type.value == "certificate" for report in result.violation_reports)


def test_low_confidence_certificate_is_rejected(safe_state):
    spec = SafetySpec(require_certificates=True, certificate_min_confidence=0.8)
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    certs = CertificateBundle.from_dicts(
        [
            {"kind": "object_identity", "subject": "mug", "confidence": 0.4},
            {"kind": "affordance", "subject": "mug", "confidence": 1.0},
        ]
    )

    result = DualAlignmentChecker().check_intent_alignment(intent, safe_state, action, spec, certs)

    assert not result.passed
    assert any("confidence" in violation for violation in result.violations)
