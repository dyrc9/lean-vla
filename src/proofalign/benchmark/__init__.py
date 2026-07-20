"""Benchmark adapters for external VLA safety suites."""

from proofalign.benchmark.aegis_runtime import (
    RuntimePreflightError,
    build_runtime_preflight,
)
from proofalign.benchmark.aegis_cbf_filter import (
    AegisCBFConstraintV2,
    AegisCBFFilterResultV2,
    AegisCBFNoActionFilterV2,
    AegisCBFSourceIdentityV2,
    SignedAegisCBFFilterEvidenceV2,
    SignedAegisPostFilterNoDispatchAdapterV2,
    audit_aegis_cbf_source,
)
from proofalign.benchmark.aegis_cbf_geometry import (
    AegisCBFCoefficientProducerV2,
    AegisGeometryObservationV2,
    SignedAegisGeometryObservationV2,
    sign_aegis_geometry_observation,
)
from proofalign.benchmark.libero_online_wrapper import (
    DefaultLiberoActionAbstractor,
    LiberoStateObserver,
    ProofAlignLiberoWrapper,
    make_libero_offscreen_env,
)
from proofalign.benchmark.libero_task_manifest import (
    LiberoTaskManifest,
    compile_libero_task_manifest,
    load_libero_task_manifest,
)
from proofalign.benchmark.safelibero_foundation import (
    EpisodeSafetyStatus,
    SafeLiberoCollisionTracker,
    SafetyChannelObservation,
    SafetyObservationStatus,
    SafetyTaskQuadrant,
    aggregate_safelibero_metrics,
    build_readiness_report,
    build_safelibero_inventory,
    classify_safety_episode,
)
from proofalign.benchmark.safelibero_ctda_support import (
    SafeLiberoCTDAV2StateAdapter,
    SafeLiberoGoalManifest,
    SafeLiberoMissionTemplateV2,
    audit_safelibero_support,
    build_ctda_v2_support_audit,
    compile_safelibero_mission_template,
    parse_safelibero_goal_manifest,
)
from proofalign.benchmark.safelibero_open_region import (
    SafeLiberoOpenRegionBindingV2,
    SafeLiberoOpenRegionRuntimeV2,
    audit_official_open_region_source,
    compile_official_open_region_binding,
)

__all__ = [
    "AegisCBFCoefficientProducerV2",
    "AegisCBFConstraintV2",
    "AegisCBFFilterResultV2",
    "AegisCBFNoActionFilterV2",
    "AegisCBFSourceIdentityV2",
    "AegisGeometryObservationV2",
    "DefaultLiberoActionAbstractor",
    "EpisodeSafetyStatus",
    "LiberoStateObserver",
    "LiberoTaskManifest",
    "ProofAlignLiberoWrapper",
    "RuntimePreflightError",
    "SafeLiberoCollisionTracker",
    "SafeLiberoCTDAV2StateAdapter",
    "SafeLiberoGoalManifest",
    "SafeLiberoMissionTemplateV2",
    "SafeLiberoOpenRegionBindingV2",
    "SafeLiberoOpenRegionRuntimeV2",
    "SafetyChannelObservation",
    "SafetyObservationStatus",
    "SafetyTaskQuadrant",
    "SignedAegisCBFFilterEvidenceV2",
    "SignedAegisGeometryObservationV2",
    "SignedAegisPostFilterNoDispatchAdapterV2",
    "aggregate_safelibero_metrics",
    "audit_safelibero_support",
    "audit_official_open_region_source",
    "audit_aegis_cbf_source",
    "build_ctda_v2_support_audit",
    "build_readiness_report",
    "build_runtime_preflight",
    "build_safelibero_inventory",
    "classify_safety_episode",
    "compile_libero_task_manifest",
    "compile_safelibero_mission_template",
    "compile_official_open_region_binding",
    "load_libero_task_manifest",
    "make_libero_offscreen_env",
    "parse_safelibero_goal_manifest",
    "sign_aegis_geometry_observation",
]
