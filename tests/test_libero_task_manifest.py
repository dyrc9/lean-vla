from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from proofalign.benchmark.libero_online_wrapper import (
    LiberoStateObserver,
    _merge_effect_results,
)
from proofalign.benchmark.libero_online_runner import (
    LiberoOnlineIntegrationError,
    LiberoTaskRuntime,
    _load_ctda_task_manifest,
)
from proofalign.benchmark.libero_task_manifest import (
    CONTACT_PART_BINDING,
    LiberoTaskManifestError,
    compile_libero_task_manifest,
    load_libero_task_manifest,
)
from proofalign.ctda import (
    AuthorityEnvelope,
    MonitorVerdict,
    PlantSample,
    TimeBase,
    contract_from_mission_phase,
    digest_text,
)
from proofalign.ctda_runtime import (
    CTDARuntimeSession,
    ExactAllowlistEvidenceIssuer,
    _derive_events,
)
from proofalign.models import (
    GripperContactPartObservation,
    GripperContactPartQuery,
    Object,
    Pose,
    CheckResult,
    Decision,
    SafetySpec,
    WorldState,
)
from proofalign.violations import ViolationReport, ViolationType


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = REPO_ROOT / "external" / "LIBERO-Safety"
REGISTRY_PATH = REPO_ROOT / "experiments" / "libero_affordance_grasp_manifests.json"


def _authority() -> AuthorityEnvelope:
    return AuthorityEnvelope("libero:affordance", "fixture", "task-1", "unsigned")


def _time_base() -> TimeBase:
    return TimeBase("test-clock", 20_000_000, 1_000_000, 1_000_000, 2_000_000)


def _load(task_id: int = 1):
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    item = next(entry for entry in registry["manifests"] if entry["task_id"] == task_id)
    return load_libero_task_manifest(
        REGISTRY_PATH,
        suite="affordance",
        task_id=task_id,
        bddl_path=BENCHMARK_ROOT / item["bddl_file"],
    )


def _state(manifest, *, left: bool, right: bool) -> WorldState:
    return WorldState(
        objects={
            manifest.target_object: Object(
                manifest.target_object,
                manifest.target_object.removesuffix("_1"),
                Pose(0.1, 0.0, 0.0),
            )
        },
        gripper_contact_parts=[
            GripperContactPartObservation(
                manifest.target_object,
                manifest.geom_ids,
                left,
                right,
                ("left-match",) if left else (),
                ("right-match",) if right else (),
            )
        ],
    )


def test_registry_source_binds_all_fifteen_affordance_goals() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    manifests = []

    for item in registry["manifests"]:
        manifests.append(
            load_libero_task_manifest(
                REGISTRY_PATH,
                suite=item["suite"],
                task_id=item["task_id"],
                bddl_path=BENCHMARK_ROOT / item["bddl_file"],
            )
        )

    assert len(manifests) == 15
    assert {manifest.task_id for manifest in manifests} == set(range(15))
    assert all(manifest.goal_predicate == "CheckGripperContactPart" for manifest in manifests)
    assert all(manifest.goal_atom.startswith("gripper_contact_part:") for manifest in manifests)


def test_manifest_loader_rejects_changed_bddl(tmp_path: Path) -> None:
    manifest = _load()
    changed = tmp_path / "changed.bddl"
    source = BENCHMARK_ROOT / manifest.bddl_file
    changed.write_bytes(source.read_bytes() + b"\n; changed\n")

    with pytest.raises(LiberoTaskManifestError, match="digest mismatch"):
        load_libero_task_manifest(
            REGISTRY_PATH,
            suite=manifest.suite,
            task_id=manifest.task_id,
            bddl_path=changed,
        )


def test_runner_requires_explicit_manifest_registry_trust_anchor() -> None:
    manifest = _load()
    runtime = LiberoTaskRuntime(
        benchmark=None,
        task=None,
        task_id=manifest.task_id,
        task_name=manifest.task_name,
        instruction=manifest.instruction,
        bddl_file=BENCHMARK_ROOT / manifest.bddl_file,
        init_state=None,
        init_state_id=0,
    )
    digest = sha256(REGISTRY_PATH.read_bytes()).hexdigest()
    args = SimpleNamespace(
        ctda=True,
        benchmark="affordance",
        ctda_task_manifest_registry=str(REGISTRY_PATH),
        ctda_task_manifest_registry_sha256=digest,
    )

    loaded = _load_ctda_task_manifest(runtime, args)

    assert loaded is not None
    assert loaded.manifest_digest == manifest.manifest_digest
    args.ctda_task_manifest_registry_sha256 = "0" * 64
    with pytest.raises(LiberoOnlineIntegrationError, match="trust anchor"):
        _load_ctda_task_manifest(runtime, args)


def test_manifest_compiler_uses_exact_contact_goal_not_holding_or_language_tail() -> None:
    manifest = _load(task_id=2)
    state = _state(manifest, left=False, right=False)

    mission = compile_libero_task_manifest(
        manifest,
        state,
        SafetySpec.from_dict({}),
        _authority(),
        _time_base(),
        spec_id="affordance:2:0",
        episode_nonce="manifest-test-episode",
    )

    assert mission.goal_atoms == (manifest.goal_atom,)
    assert not any(atom.startswith(("holding:", "released:", "in_region:")) for atom in mission.goal_atoms)
    assert mission.phases == ("approach", "contact")
    assert mission.goal_phases == ("contact",)
    assert mission.phase_obligations[0].part == CONTACT_PART_BINDING
    assert mission.phase_obligations[0].guarantees == (manifest.goal_atom,)
    assert mission.safe_parts == ((manifest.target_object, CONTACT_PART_BINDING),)


def test_contact_witness_completes_manifest_contract_and_round_trips() -> None:
    manifest = _load()
    before = _state(manifest, left=False, right=False)
    after = _state(manifest, left=True, right=True)
    after = WorldState.from_dict(after.to_dict())
    mission = compile_libero_task_manifest(
        manifest,
        before,
        SafetySpec.from_dict({}),
        _authority(),
        _time_base(),
        spec_id="affordance:1:0",
        episode_nonce="manifest-completion-episode",
    )
    contract = contract_from_mission_phase(
        mission,
        current_phase="approach",
        issued_at_ns=0,
        deadline_ns=100,
    )

    events = _derive_events(
        contract,
        before,
        (after,),
        (
            PlantSample(
                10,
                digest_text("state"),
                digest_text("command"),
                True,
                True,
                True,
            ),
        ),
    )

    assert [event.atom for event, _ in events] == [manifest.goal_atom, "phase:contact"]
    session = CTDARuntimeSession.from_unsigned_mission(
        mission,
        evidence_issuer=ExactAllowlistEvidenceIssuer(
            producer_id=mission.authority.authority_id,
            producer_version=mission.authority.version,
        ),
        now_ns=0,
    )
    assert session.supervisor.mission.authority.authenticated is True


def test_exact_contact_completion_supersedes_only_legacy_pick_postcondition() -> None:
    legacy = CheckResult(
        passed=False,
        layer="chunk_effect",
        violations=["legacy holding postcondition did not hold"],
        explanation="legacy mismatch",
        suggested_decision=Decision.REPLAN,
        violation_reports=[
            ViolationReport(
                ViolationType.POSTCONDITION,
                "chunk_effect",
                "legacy holding postcondition did not hold",
            )
        ],
    )
    ctda = CheckResult(
        passed=True,
        layer="ctda_monitor",
        explanation="exact contact-part mission completed",
        suggested_decision=Decision.ALLOW,
    )

    assert _merge_effect_results(legacy, ctda, MonitorVerdict.COMPLETE) is ctda
    hazardous = CheckResult(
        passed=False,
        layer="chunk_effect",
        violations=["collision"],
        explanation="collision",
        suggested_decision=Decision.SAFE_STOP,
        violation_reports=[
            ViolationReport(ViolationType.COLLISION, "chunk_effect", "collision")
        ],
    )
    assert _merge_effect_results(hazardous, ctda, MonitorVerdict.COMPLETE) is hazardous


@dataclass
class _Contact:
    geom1: int
    geom2: int


class _SimModel:
    def __init__(self) -> None:
        self.names = {0: "left_pad", 1: "right_pad", 2: "hammer_collision_21"}

    def geom_id2name(self, geom_id: int) -> str:
        return self.names[geom_id]


class _SimData:
    def __init__(self, *, right: bool) -> None:
        self.contact = [_Contact(0, 2)] + ([_Contact(1, 2)] if right else [])
        self.ncon = len(self.contact)


class _Gripper:
    _important_geoms = {
        "left_fingerpad": ["left_pad"],
        "right_fingerpad": ["right_pad"],
    }


class _Robot:
    gripper = _Gripper()


class _ObjectModel:
    category_name = "hammer"
    contact_geoms = ["hammer_collision_20", "hammer_collision_21"]


class _ContactEnv:
    def __init__(self, *, right: bool) -> None:
        self.sim = type("Sim", (), {"model": _SimModel(), "data": _SimData(right=right)})()
        self.objects_dict = {"hammer_1": _ObjectModel()}
        self.fixtures_dict = {}
        self.object_sites_dict = {}
        self.robots = [_Robot()]
        self.collision = False
        self.cost = {}
        self.min_distance_to_human_hand = 1.0
        self.min_distance_to_obstacle = 1.0


@pytest.mark.parametrize(("right", "satisfied"), [(False, False), (True, True)])
def test_state_observer_recomputes_two_finger_contact_part_witness(
    right: bool,
    satisfied: bool,
) -> None:
    query = GripperContactPartQuery("hammer_1", ("21",))

    state = LiberoStateObserver(contact_part_queries=(query,)).observe(
        _ContactEnv(right=right)
    )

    assert len(state.gripper_contact_parts) == 1
    witness = state.gripper_contact_parts[0]
    assert witness.atom == query.atom
    assert witness.left_contact is True
    assert witness.right_contact is right
    assert witness.satisfied is satisfied
    assert f"ctda_unknown_observation:{query.atom}" not in state.notes


def test_state_observer_marks_unavailable_contact_query_unknown() -> None:
    query = GripperContactPartQuery("hammer_1", ("21",))
    env = _ContactEnv(right=True)
    del env.robots

    state = LiberoStateObserver(contact_part_queries=(query,)).observe(env)

    assert state.gripper_contact_parts == []
    assert f"ctda_unknown_observation:{query.atom}" in state.notes
