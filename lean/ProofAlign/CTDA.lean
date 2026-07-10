import ProofAlign.Core
import Std

namespace ProofAlign

/-!
# Contract-Carrying Temporal Dual Alignment

This module is the executable Lean trust boundary for CTDA.  It intentionally
separates four judgments:

1. a semantic contract refines a frozen mission and phase obligation;
2. a bounded raw-action prefix is authorized by that semantic judgment;
3. the observed execution is bound to the authorization and its evidence;
4. a persistent, three-valued temporal monitor classifies the checked prefix.

The propositions are conditional on the evidence producers named by their
digests.  A nonempty witness name is not itself a dynamics or perception proof;
it is a binding that a trusted producer/checker must validate at the boundary.
-/

abbrev SpecId := String
abbrev ContractId := String
abbrev Digest := String
abbrev PhaseId := String
abbrev EvidenceRef := String
abbrev FallbackId := String
abbrev WitnessRef := String
abbrev Counterexample := String
abbrev MissingEvidence := String
abbrev EvidenceConflict := String
abbrev Violation := String

structure Duration where
  ticks : Nat
deriving Repr, DecidableEq, BEq

structure Timestamp where
  tick : Nat
deriving Repr, DecidableEq, BEq

structure TimeBase where
  digest : Digest
  clockId : String
  nanosecondsPerTick : Nat
  controlPeriod : Duration
  maxSamplingJitter : Duration
  maxMonitorLatency : Duration
deriving Repr, DecidableEq, BEq

structure Deadline where
  expiresAt : Timestamp
deriving Repr, DecidableEq, BEq

structure AuthorityEnvelope where
  authorityId : String
  sourceDigest : Digest
  version : String
  authenticated : Bool
deriving Repr, DecidableEq, BEq

inductive Skill where
  | approach
  | pick
  | transport
  | place
  | release
  | hold
  | brake
  | retreat
  | stop
  | reject
deriving Repr, DecidableEq, BEq

inductive FallbackClass where
  | hold
  | brake
  | retreat
  | taskRecovery
  | reject
deriving Repr, DecidableEq, BEq

inductive StateAtom where
  | holding : ObjectId -> StateAtom
  | inRegion : ObjectId -> RegionId -> StateAtom
  | collisionFree
  | humanClearanceAtLeast : Nat -> StateAtom
  | obstacleClearanceAtLeast : Nat -> StateAtom
deriving Repr, DecidableEq, BEq

inductive StateFormula where
  | atom : StateAtom -> StateFormula
  | neg : StateFormula -> StateFormula
  | and : StateFormula -> StateFormula -> StateFormula
  | or : StateFormula -> StateFormula -> StateFormula
  | implies : StateFormula -> StateFormula -> StateFormula
deriving Repr, DecidableEq, BEq

def evalStateAtom (state : WorldState) : StateAtom -> Bool
  | .holding obj => held state obj
  | .inRegion obj region => objectInRegion state obj region
  | .collisionFree => !state.collision
  | .humanClearanceAtLeast margin => state.humanHandDistance >= margin
  | .obstacleClearanceAtLeast margin => state.obstacleDistance >= margin

def evalStateFormula (state : WorldState) : StateFormula -> Bool
  | .atom atom => evalStateAtom state atom
  | .neg formula => !(evalStateFormula state formula)
  | .and left right => evalStateFormula state left && evalStateFormula state right
  | .or left right => evalStateFormula state left || evalStateFormula state right
  | .implies antecedent consequent =>
      !(evalStateFormula state antecedent) || evalStateFormula state consequent

inductive TraceAtom where
  | noBadContact
  | holding : ObjectId -> TraceAtom
  | released : ObjectId -> TraceAtom
  | inRegion : ObjectId -> RegionId -> TraceAtom
  | stable : ObjectId -> TraceAtom
  | unchanged : ObjectId -> TraceAtom
  | humanClearanceAtLeast : Nat -> TraceAtom
  | obstacleClearanceAtLeast : Nat -> TraceAtom
  | goalReached
deriving Repr, DecidableEq, BEq

inductive TraceFormula where
  | atom : TraceAtom -> TraceFormula
  | neg : TraceFormula -> TraceFormula
  | and : TraceFormula -> TraceFormula -> TraceFormula
  | implies : TraceFormula -> TraceFormula -> TraceFormula
  | always : TraceFormula -> TraceFormula
  | eventuallyWithin : Duration -> TraceFormula -> TraceFormula
  | until : TraceFormula -> TraceFormula -> TraceFormula
  | sequence : List TraceAtom -> TraceFormula
  | stableFor : Duration -> TraceFormula -> TraceFormula
  | precededBy : TraceFormula -> TraceFormula -> TraceFormula
deriving Repr, DecidableEq, BEq

structure SymbolicEventFrame where
  timestamp : Timestamp
  facts : List TraceAtom
  sourcePlantSampleDigest : Digest
deriving Repr, DecidableEq, BEq

abbrev SymbolicEventTrace := List SymbolicEventFrame

structure ExactInterval where
  lower : Int
  upper : Int
deriving Repr, DecidableEq, BEq

def ExactInterval.WellFormed (interval : ExactInterval) : Prop :=
  interval.lower <= interval.upper

instance (interval : ExactInterval) : Decidable interval.WellFormed :=
  Int.decLe interval.lower interval.upper

structure PlantSample where
  timestamp : Timestamp
  sampleDigest : Digest
  stateDigest : Digest
  authorizationDigest : Digest
  executedCommandDigest : Digest
  humanClearance : ExactInterval
  obstacleClearance : ExactInterval
  force : ExactInterval
  hardInvariantsHold : Bool
  withinReachableTube : Bool
  modelAssumptionsHold : Bool
deriving Repr, DecidableEq, BEq

abbrev PlantTrace := List PlantSample

structure TaskTransition where
  source : PhaseId
  skill : Skill
  destination : PhaseId
deriving Repr, DecidableEq, BEq

structure TaskAutomaton where
  initialPhase : PhaseId
  terminalPhases : List PhaseId
  transitions : List TaskTransition
deriving Repr, DecidableEq, BEq

def TaskAutomaton.allows
    (automaton : TaskAutomaton)
    (source : PhaseId)
    (skill : Skill)
    (destination : PhaseId) : Bool :=
  automaton.transitions.any fun transition =>
    transition.source == source
      && transition.skill == skill
      && transition.destination == destination

def TaskAutomaton.nonblocking (automaton : TaskAutomaton) (phase : PhaseId) : Bool :=
  automaton.terminalPhases.contains phase
    || automaton.transitions.any (fun transition => transition.source == phase)

def TaskProgresses
    (automaton : TaskAutomaton)
    (source : PhaseId)
    (skill : Skill)
    (destination : PhaseId) : Bool :=
  source != destination && automaton.allows source skill destination

structure ObjectBinding where
  objectId : ObjectId
  ontologyClass : String
  registryDigest : Digest
  allowedParts : List PartId := []
deriving Repr, DecidableEq, BEq

structure PhaseObligation where
  phase : PhaseId
  obligations : List TraceFormula
  terminalEvent : TraceAtom
  requiredPart : Option PartId := none
deriving Repr, DecidableEq, BEq

structure MissionSpec where
  specId : SpecId
  specDigest : Digest
  authority : AuthorityEnvelope
  instructionDigest : Digest
  goal : TraceFormula
  hardInvariants : List TraceFormula
  taskAutomaton : TaskAutomaton
  phaseObligations : List PhaseObligation
  objectRoles : List ObjectBinding
  defaultMustPreserve : List ObjectId
  requiredEvidence : List String
  timeBase : TimeBase
deriving Repr, DecidableEq, BEq

structure SemanticSkillContract where
  contractId : ContractId
  contractDigest : Digest
  specId : SpecId
  specDigest : Digest
  phaseBefore : PhaseId
  expectedNextPhase : PhaseId
  skill : Skill
  target : Option ObjectId := none
  part : Option PartId := none
  region : Option RegionId := none
  issuedAt : Timestamp
  deadline : Deadline
  guards : List StateFormula := []
  guarantee : List TraceFormula
  advancesObligations : List TraceFormula
  terminalEvent : TraceAtom
  mayModify : List ObjectId := []
  mustPreserve : List ObjectId := []
  fallbackClass : FallbackClass
  fallbackId : FallbackId
  semanticPreRequirements : List String := []
  physicalPreRequirements : List String := []
  runtimeRequirements : List String := []
  postRequirements : List String := []
deriving Repr, DecidableEq, BEq

inductive StaticCheckResult where
  | proven : WitnessRef -> StaticCheckResult
  | refuted : List Counterexample -> StaticCheckResult
  | unknown : List MissingEvidence -> StaticCheckResult
  | inconsistent : List EvidenceConflict -> StaticCheckResult
deriving Repr, DecidableEq, BEq

structure ActionProposalBinding where
  contractId : ContractId
  contractDigest : Digest
  proposalIndex : Nat
  proposalDigest : Digest
  proposedHorizon : Duration
  issuedAt : Timestamp
deriving Repr, DecidableEq, BEq

structure PrefixAuthorization where
  authorizationDigest : Digest
  contractId : ContractId
  contractDigest : Digest
  semanticWitnessRef : WitnessRef
  specDigest : Digest
  stateDigest : Digest
  monitorStateDigest : Digest
  proposalIndex : Nat
  proposalDigest : Digest
  authorizedCommandDigest : Digest
  filterPolicyDigest : Digest
  dynamicsModelDigest : Digest
  timeBaseDigest : Digest
  tubeDigest : Digest
  maxAuthorizedDuration : Duration
  fallbackId : FallbackId
  fallbackWitnessRef : EvidenceRef
  issuedAt : Timestamp
  validUntil : Timestamp
deriving Repr, DecidableEq, BEq

structure TubeSlice where
  offset : Duration
  validUntil : Duration
  invariantMargin : Int
  safeThroughout : Bool
  recoverableThroughout : Bool
  safetyWitnessRef : EvidenceRef
  recoveryWitnessRef : EvidenceRef
deriving Repr, DecidableEq, BEq

structure ReachableTube where
  tubeDigest : Digest
  authorizedCommandDigest : Digest
  dynamicsModelDigest : Digest
  horizon : Duration
  fallbackId : FallbackId
  fallbackWitnessRef : EvidenceRef
  slices : List TubeSlice
deriving Repr, DecidableEq, BEq

inductive EvidenceKind where
  | proposalAdmissibility
  | filterPreservation
deriving Repr, DecidableEq, BEq

/- A typed evidence binding names the exact claim inputs checked by an external
producer.  `verified` remains an explicit trust-boundary assumption, but the
claim cannot be reused for a different contract, proposal, command, or filter. -/
structure EvidenceBinding where
  kind : EvidenceKind
  contractDigest : Digest
  proposalDigest : Digest
  authorizedCommandDigest : Digest
  policyDigest : Digest
  producerId : String
  producerVersion : String
  witnessRef : EvidenceRef
  verified : Bool
deriving Repr, DecidableEq, BEq

structure PrefixPreEvidenceBundle where
  proposalDigest : Digest
  authorizedCommandDigest : Digest
  filterPolicyDigest : Digest
  dynamicsModelDigest : Digest
  tubeDigest : Digest
  fallbackId : FallbackId
  fallbackWitnessRef : EvidenceRef
  worstCaseSwitchLatency : Duration
  maxCertifiedSwitchLatency : Duration
  proposalEvidence : EvidenceBinding
  filterEvidence : EvidenceBinding
  coveredRequirements : List String
deriving Repr, DecidableEq, BEq

structure PrefixCandidate where
  proposal : ActionProposalBinding
  authorization : PrefixAuthorization
  tube : ReachableTube
  preEvidence : PrefixPreEvidenceBundle
deriving Repr, DecidableEq, BEq

structure MonitorState where
  monitorStateDigest : Digest
  contractId : ContractId
  specDigest : Digest
  phase : PhaseId
  stateDigest : Digest
  nextProposalIndex : Nat
  pending : List TraceFormula
  hasPending : Bool
  lastEventTimestamp : Timestamp
deriving Repr, DecidableEq, BEq

inductive MonitorVerdict where
  | complete : WitnessRef -> MonitorVerdict
  | violated : List Violation -> MonitorVerdict
  | safePending : MonitorState -> MonitorVerdict
  | unknown : List MissingEvidence -> MonitorVerdict
  | inconsistent : List EvidenceConflict -> MonitorVerdict
deriving Repr, DecidableEq, BEq

structure ExecutionReceipt where
  authorizationDigest : Digest
  authorizedCommandDigest : Digest
  executedCommandDigest : Digest
  executedAt : Timestamp
  withinAuthorizedError : Bool
  actuatorEvidence : EvidenceRef
  errorBoundWitness : EvidenceRef
deriving Repr, DecidableEq, BEq

structure PrefixRuntimeEvidenceBundle where
  authorizationDigest : Digest
  executedCommandDigest : Digest
  plantTraceDigest : Digest
  tubeDigest : Digest
  monitorBeforeDigest : Digest
  allSamplesWithinTube : Bool
  allHardInvariantsHold : Bool
  allModelAssumptionsHold : Bool
  observerWitness : EvidenceRef
  timingWitness : EvidenceRef
  coveredRequirements : List String
deriving Repr, DecidableEq, BEq

structure FactAbstractionLink where
  frameIndex : Nat
  factIndex : Nat
  sampleDigest : Digest
  atom : TraceAtom
  derivationDigest : Digest
  witnessRef : EvidenceRef
  verified : Bool
deriving Repr, DecidableEq, BEq

structure TraceAbstractionEvidence where
  plantTraceDigest : Digest
  symbolicEventTraceDigest : Digest
  timeBaseDigest : Digest
  abstractorId : String
  abstractorVersion : String
  witnessRef : EvidenceRef
  verified : Bool
  links : List FactAbstractionLink
deriving Repr, DecidableEq, BEq

structure PrefixExecutionRecord where
  recordDigest : Digest
  candidate : PrefixCandidate
  receipt : ExecutionReceipt
  plantTrace : PlantTrace
  plantTraceDigest : Digest
  plantTimeBaseDigest : Digest
  eventTrace : SymbolicEventTrace
  symbolicEventTraceDigest : Digest
  runtimeEvidence : PrefixRuntimeEvidenceBundle
  abstractionEvidence : TraceAbstractionEvidence
  monitorBeforeDigest : Digest
  monitorAfterDigest : Digest
deriving Repr, DecidableEq, BEq

structure PostEvidenceBundle where
  evidenceDigest : Digest
  contractDigest : Digest
  recordDigest : Digest
  finalStateDigest : Digest
  terminalFrameSourceDigest : Digest
  terminalFrameTimestamp : Timestamp
  monitorAfterDigest : Digest
  producerId : String
  producerVersion : String
  witnessRef : EvidenceRef
  verified : Bool
  coveredRequirements : List String
deriving Repr, DecidableEq, BEq

structure ContractExecution where
  contractId : ContractId
  specDigest : Digest
  prefixes : List PrefixExecutionRecord
deriving Repr, DecidableEq, BEq

def requirementsCovered (available required : List String) : Bool :=
  required.all available.contains

def nonemptyStrings (values : List String) : Bool :=
  values.all fun value => value != ""

def objectRegistered (mission : MissionSpec) (objectId : ObjectId) : Bool :=
  mission.objectRoles.any fun binding => binding.objectId == objectId

def partAllowedForTarget
    (mission : MissionSpec) (objectId : ObjectId) (part : PartId) : Bool :=
  match mission.objectRoles.find? fun binding => binding.objectId == objectId with
  | none => false
  | some binding => part != "" && binding.allowedParts.contains part

def targetWellFormed (mission : MissionSpec) (contract : SemanticSkillContract) : Bool :=
  let registered := contract.target.all (objectRegistered mission)
  let frameObjectsRegistered :=
    (contract.mayModify ++ contract.mustPreserve).all (objectRegistered mission)
  registered && frameObjectsRegistered &&
    match contract.skill with
    | .approach | .transport => contract.target.isSome
    | .place => contract.target.isSome && contract.region.isSome
    | .release => contract.target.isSome
    | .pick =>
        match contract.target, contract.part with
        | some target, some part => partAllowedForTarget mission target part
        | _, _ => false
    | .hold | .brake | .retreat | .stop | .reject => true

def frameSetsConsistent (mission : MissionSpec) (contract : SemanticSkillContract) : Bool :=
  let disjoint := contract.mayModify.all fun objectId =>
    !(contract.mustPreserve.contains objectId)
  let preservesDefaults := mission.defaultMustPreserve.all fun objectId =>
    contract.mustPreserve.contains objectId
  let modifyingTargetDeclared :=
    match contract.skill, contract.target with
    | .pick, some target
    | .transport, some target
    | .place, some target
    | .release, some target => contract.mayModify.contains target
    | _, _ => true
  disjoint && preservesDefaults && modifyingTargetDeclared

def MissionSpec.obligationFor
    (mission : MissionSpec) (phase : PhaseId) : Option PhaseObligation :=
  mission.phaseObligations.find? fun obligation => obligation.phase == phase

def traceFormulaMentionsAtom (formula : TraceFormula) (needle : TraceAtom) : Bool :=
  match formula with
  | .atom atom => atom == needle
  | .neg inner | .always inner | .eventuallyWithin _ inner | .stableFor _ inner =>
      traceFormulaMentionsAtom inner needle
  | .and left right | .implies left right | .until left right
  | .precededBy left right =>
      traceFormulaMentionsAtom left needle || traceFormulaMentionsAtom right needle
  | .sequence atoms => atoms.contains needle

/- A semantic guarantee refines the mission only when it discharges the frozen
obligations for the declared destination phase.  A transition into a terminal
phase must additionally carry the frozen mission goal itself. -/
def GuaranteeRefinesMission
    (mission : MissionSpec) (contract : SemanticSkillContract) : Bool :=
  match mission.obligationFor contract.expectedNextPhase with
  | none => false
  | some phaseObligation =>
      !phaseObligation.obligations.isEmpty
        && contract.advancesObligations == phaseObligation.obligations
        && phaseObligation.obligations.all contract.guarantee.contains
        && contract.terminalEvent == phaseObligation.terminalEvent
        && contract.part == phaseObligation.requiredPart
        && phaseObligation.obligations.any
          (fun formula => traceFormulaMentionsAtom formula phaseObligation.terminalEvent)
        && (if mission.taskAutomaton.terminalPhases.contains contract.expectedNextPhase then
              contract.guarantee.contains mission.goal
            else
              true)

structure SemanticCheckRequest where
  mission : MissionSpec
  phase : PhaseId
  state : WorldState
  currentTime : Timestamp
  contract : SemanticSkillContract
  evidence : List String
deriving Repr, DecidableEq, BEq

def SemanticTemporalRefines (request : SemanticCheckRequest) : Prop :=
  request.mission.authority.authenticated = true
  ∧ request.mission.authority.sourceDigest ≠ ""
  ∧ request.mission.specId ≠ ""
  ∧ request.mission.specDigest ≠ ""
  ∧ request.contract.contractId ≠ ""
  ∧ request.contract.contractDigest ≠ ""
  ∧ request.contract.specId = request.mission.specId
  ∧ request.contract.specDigest = request.mission.specDigest
  ∧ request.contract.phaseBefore = request.phase
  ∧ request.contract.issuedAt.tick <= request.currentTime.tick
  ∧ request.currentTime.tick <= request.contract.deadline.expiresAt.tick
  ∧ TaskProgresses request.mission.taskAutomaton
      request.phase request.contract.skill request.contract.expectedNextPhase = true
  ∧ request.mission.taskAutomaton.nonblocking request.contract.expectedNextPhase = true
  ∧ targetWellFormed request.mission request.contract = true
  ∧ request.contract.guarantee ≠ []
  ∧ GuaranteeRefinesMission request.mission request.contract = true
  ∧ request.contract.guards.all (evalStateFormula request.state) = true
  ∧ frameSetsConsistent request.mission request.contract = true
  ∧ request.contract.fallbackId ≠ ""
  ∧ requirementsCovered
      request.evidence
      (request.mission.requiredEvidence ++ request.contract.semanticPreRequirements) = true

instance (request : SemanticCheckRequest) : Decidable (SemanticTemporalRefines request) :=
  by
    unfold SemanticTemporalRefines
    infer_instance

def semanticWitnessFor (contract : SemanticSkillContract) : WitnessRef :=
  "semantic:" ++ contract.contractDigest

def checkSemantic (request : SemanticCheckRequest) : StaticCheckResult :=
  if SemanticTemporalRefines request then
    .proven (semanticWitnessFor request.contract)
  else
    .refuted ["semantic-temporal mission refinement failed"]

theorem checkSemantic_sound
    (request : SemanticCheckRequest)
    (witness : WitnessRef)
    (result : checkSemantic request = .proven witness) :
    SemanticTemporalRefines request := by
  unfold checkSemantic at result
  split at result
  · assumption
  · simp at result

theorem checkSemantic_reflects (request : SemanticCheckRequest) :
    (∃ witness, checkSemantic request = .proven witness)
      ↔ SemanticTemporalRefines request := by
  constructor
  · rintro ⟨witness, result⟩
    exact checkSemantic_sound request witness result
  · intro valid
    refine ⟨semanticWitnessFor request.contract, ?_⟩
    simp [checkSemantic, valid]

def tubeSliceValid (horizon : Duration) (slice : TubeSlice) : Bool :=
  decide (slice.offset.ticks < slice.validUntil.ticks)
    && decide (slice.validUntil.ticks <= horizon.ticks)
    && decide (0 <= slice.invariantMargin)
    && slice.safeThroughout
    && slice.recoverableThroughout
    && slice.safetyWitnessRef != ""
    && slice.recoveryWitnessRef != ""

def tubeSliceChainFrom
    (expectedStart : Nat) (horizon : Duration) : List TubeSlice -> Bool
  | [] => true
  | slice :: rest =>
      decide (slice.offset.ticks = expectedStart)
        && tubeSliceValid horizon slice
        && tubeSliceChainFrom slice.validUntil.ticks horizon rest

def tubeCoveredUntil (tube : ReachableTube) : Nat :=
  match tube.slices.getLast? with
  | none => 0
  | some slice => slice.validUntil.ticks

def tubeSafeAndRecoverableFor
    (tube : ReachableTube)
    (authorizedDuration : Duration)
    (fallbackId : FallbackId)
    (fallbackWitnessRef : EvidenceRef) : Bool :=
  tube.tubeDigest != ""
    && tube.authorizedCommandDigest != ""
    && tube.dynamicsModelDigest != ""
    && decide (0 < tube.horizon.ticks)
    && decide (0 < authorizedDuration.ticks)
    && decide (authorizedDuration.ticks <= tube.horizon.ticks)
    && !tube.slices.isEmpty
    && tubeSliceChainFrom 0 tube.horizon tube.slices
    && decide (authorizedDuration.ticks <= tubeCoveredUntil tube)
    && tube.fallbackId == fallbackId
    && tube.fallbackWitnessRef == fallbackWitnessRef
    && fallbackId != ""
    && fallbackWitnessRef != ""

def evidenceProducerValid (evidence : EvidenceBinding) : Bool :=
  evidence.producerId != ""
    && evidence.producerVersion != ""
    && evidence.witnessRef != ""
    && evidence.verified

def proposalEvidenceValid
    (contract : SemanticSkillContract)
    (proposal : ActionProposalBinding)
    (evidence : EvidenceBinding) : Bool :=
  evidence.kind == .proposalAdmissibility
    && evidence.contractDigest == contract.contractDigest
    && evidence.proposalDigest == proposal.proposalDigest
    && evidence.authorizedCommandDigest == ""
    && evidence.policyDigest == ""
    && evidenceProducerValid evidence

def filterEvidenceValid
    (contract : SemanticSkillContract)
    (proposal : ActionProposalBinding)
    (authorization : PrefixAuthorization)
    (evidence : EvidenceBinding) : Bool :=
  evidence.kind == .filterPreservation
    && evidence.contractDigest == contract.contractDigest
    && evidence.proposalDigest == proposal.proposalDigest
    && evidence.authorizedCommandDigest == authorization.authorizedCommandDigest
    && evidence.policyDigest == authorization.filterPolicyDigest
    && evidenceProducerValid evidence

def monotonicProposal (previous : Option Nat) (next : Nat) : Bool :=
  match previous with
  | none => true
  | some index => index < next

structure PrefixPreCheckRequest where
  mission : MissionSpec
  state : WorldState
  stateDigest : Digest
  monitorState : MonitorState
  currentTime : Timestamp
  previousProposalIndex : Option Nat := none
  contract : SemanticSkillContract
  semanticRequest : SemanticCheckRequest
  semanticWitness : WitnessRef
  candidate : PrefixCandidate
deriving Repr, DecidableEq, BEq

def PrefixPreCertified (request : PrefixPreCheckRequest) : Prop :=
  request.semanticRequest.mission = request.mission
  ∧ request.semanticRequest.phase = request.monitorState.phase
  ∧ request.semanticRequest.state = request.state
  ∧ request.semanticRequest.contract = request.contract
  ∧ request.semanticRequest.currentTime.tick <= request.currentTime.tick
  ∧ checkSemantic request.semanticRequest = .proven request.semanticWitness
  ∧ request.semanticWitness = semanticWitnessFor request.contract
  ∧ request.mission.authority.authenticated = true
  ∧ request.contract.specId = request.mission.specId
  ∧ request.contract.specDigest = request.mission.specDigest
  ∧ request.monitorState.contractId = request.contract.contractId
  ∧ request.monitorState.specDigest = request.mission.specDigest
  ∧ request.monitorState.phase = request.contract.phaseBefore
  ∧ request.monitorState.monitorStateDigest ≠ ""
  ∧ request.candidate.proposal.contractId = request.contract.contractId
  ∧ request.candidate.proposal.contractDigest = request.contract.contractDigest
  ∧ request.candidate.authorization.contractId = request.contract.contractId
  ∧ request.candidate.authorization.contractDigest = request.contract.contractDigest
  ∧ request.candidate.authorization.semanticWitnessRef = request.semanticWitness
  ∧ request.candidate.authorization.authorizationDigest ≠ ""
  ∧ request.candidate.authorization.specDigest = request.mission.specDigest
  ∧ request.candidate.authorization.stateDigest = request.stateDigest
  ∧ request.candidate.authorization.monitorStateDigest = request.monitorState.monitorStateDigest
  ∧ request.candidate.authorization.proposalIndex = request.candidate.proposal.proposalIndex
  ∧ request.candidate.authorization.proposalDigest = request.candidate.proposal.proposalDigest
  ∧ request.candidate.authorization.timeBaseDigest = request.mission.timeBase.digest
  ∧ request.candidate.authorization.tubeDigest = request.candidate.tube.tubeDigest
  ∧ request.candidate.authorization.authorizedCommandDigest =
      request.candidate.tube.authorizedCommandDigest
  ∧ request.candidate.authorization.dynamicsModelDigest =
      request.candidate.tube.dynamicsModelDigest
  ∧ request.candidate.proposal.issuedAt.tick <= request.candidate.authorization.issuedAt.tick
  ∧ request.candidate.authorization.issuedAt.tick <= request.currentTime.tick
  ∧ request.currentTime.tick <= request.candidate.authorization.validUntil.tick
  ∧ request.currentTime.tick <= request.contract.deadline.expiresAt.tick
  ∧ request.candidate.authorization.validUntil.tick <=
      request.contract.deadline.expiresAt.tick
  ∧ request.candidate.authorization.issuedAt.tick +
      request.candidate.authorization.maxAuthorizedDuration.ticks <=
      request.candidate.authorization.validUntil.tick
  ∧ request.currentTime.tick +
      request.candidate.authorization.maxAuthorizedDuration.ticks <=
      request.candidate.authorization.validUntil.tick
  ∧ request.currentTime.tick +
      request.candidate.authorization.maxAuthorizedDuration.ticks <=
      request.contract.deadline.expiresAt.tick
  ∧ request.candidate.authorization.maxAuthorizedDuration.ticks <=
      request.candidate.proposal.proposedHorizon.ticks
  ∧ monotonicProposal
      request.previousProposalIndex
      request.candidate.proposal.proposalIndex = true
  ∧ request.monitorState.nextProposalIndex = request.candidate.proposal.proposalIndex
  ∧ request.contract.guards.all (evalStateFormula request.state) = true
  ∧ request.candidate.authorization.fallbackId = request.contract.fallbackId
  ∧ request.candidate.authorization.fallbackWitnessRef =
      request.candidate.preEvidence.fallbackWitnessRef
  ∧ tubeSafeAndRecoverableFor
      request.candidate.tube
      request.candidate.authorization.maxAuthorizedDuration
      request.candidate.authorization.fallbackId
      request.candidate.authorization.fallbackWitnessRef = true
  ∧ request.candidate.preEvidence.proposalDigest =
      request.candidate.proposal.proposalDigest
  ∧ request.candidate.preEvidence.authorizedCommandDigest =
      request.candidate.authorization.authorizedCommandDigest
  ∧ request.candidate.preEvidence.filterPolicyDigest =
      request.candidate.authorization.filterPolicyDigest
  ∧ request.candidate.preEvidence.dynamicsModelDigest =
      request.candidate.authorization.dynamicsModelDigest
  ∧ request.candidate.preEvidence.tubeDigest =
      request.candidate.authorization.tubeDigest
  ∧ request.candidate.preEvidence.fallbackId =
      request.candidate.authorization.fallbackId
  ∧ request.candidate.preEvidence.fallbackWitnessRef =
      request.candidate.authorization.fallbackWitnessRef
  ∧ request.candidate.preEvidence.worstCaseSwitchLatency.ticks <=
      request.candidate.preEvidence.maxCertifiedSwitchLatency.ticks
  ∧ request.candidate.preEvidence.maxCertifiedSwitchLatency.ticks <=
      request.mission.timeBase.maxMonitorLatency.ticks
  ∧ proposalEvidenceValid
      request.contract
      request.candidate.proposal
      request.candidate.preEvidence.proposalEvidence = true
  ∧ filterEvidenceValid
      request.contract
      request.candidate.proposal
      request.candidate.authorization
      request.candidate.preEvidence.filterEvidence = true
  ∧ requirementsCovered
      request.candidate.preEvidence.coveredRequirements
      request.contract.physicalPreRequirements = true

instance (request : PrefixPreCheckRequest) : Decidable (PrefixPreCertified request) :=
  by
    unfold PrefixPreCertified
    infer_instance

def prefixWitnessFor (candidate : PrefixCandidate) : WitnessRef :=
  "prefix-pre:" ++ candidate.authorization.authorizationDigest

def checkPrefixPre (request : PrefixPreCheckRequest) : StaticCheckResult :=
  if PrefixPreCertified request then
    .proven (prefixWitnessFor request.candidate)
  else
    .refuted ["semantic witness, prefix authorization, or reachable-tube evidence failed"]

theorem checkPrefixPre_sound
    (request : PrefixPreCheckRequest)
    (witness : WitnessRef)
    (result : checkPrefixPre request = .proven witness) :
    PrefixPreCertified request := by
  unfold checkPrefixPre at result
  split at result
  · assumption
  · simp at result

theorem checkPrefixPre_reflects (request : PrefixPreCheckRequest) :
    (∃ witness, checkPrefixPre request = .proven witness)
      ↔ PrefixPreCertified request := by
  constructor
  · rintro ⟨witness, result⟩
    exact checkPrefixPre_sound request witness result
  · intro valid
    refine ⟨prefixWitnessFor request.candidate, ?_⟩
    simp [checkPrefixPre, valid]

theorem PrefixPreCertified.guarantee_nonempty
    {request : PrefixPreCheckRequest}
    (certified : PrefixPreCertified request) :
    request.contract.guarantee ≠ [] := by
  rcases certified with
    ⟨_, _, _, contractBinding, _, semanticChecked, _⟩
  have semanticValid :=
    checkSemantic_sound request.semanticRequest request.semanticWitness semanticChecked
  have semanticGuarantee : request.semanticRequest.contract.guarantee ≠ [] := by
    rcases semanticValid with
      ⟨_, _, _, _, _, _, _, _, _, _, _, _, _, _, guaranteeNonempty, _⟩
    exact guaranteeNonempty
  rw [contractBinding] at semanticGuarantee
  exact semanticGuarantee

def traceTimestampsStrict {α : Type}
    (timestamp : α -> Timestamp) (trace : List α) : Bool :=
  (trace.zip trace.tail).all fun pair =>
    (timestamp pair.fst).tick < (timestamp pair.snd).tick

def plantTraceWellFormed (trace : PlantTrace) : Bool :=
  !trace.isEmpty
    && traceTimestampsStrict PlantSample.timestamp trace
    && trace.all (fun sample =>
      sample.sampleDigest != ""
        && sample.stateDigest != ""
        && sample.authorizationDigest != ""
        && sample.executedCommandDigest != ""
        && decide sample.humanClearance.WellFormed
        && decide sample.obstacleClearance.WellFormed
        && decide sample.force.WellFormed)

def eventTraceWellFormed (trace : SymbolicEventTrace) : Bool :=
  traceTimestampsStrict SymbolicEventFrame.timestamp trace
    && trace.all (fun frame => frame.sourcePlantSampleDigest != "")

def eventFrameHasPlantProvenance
    (plantTrace : PlantTrace) (frame : SymbolicEventFrame) : Bool :=
  plantTrace.any fun sample =>
    sample.sampleDigest == frame.sourcePlantSampleDigest
      && sample.timestamp == frame.timestamp

def eventTraceHasPlantProvenance
    (plantTrace : PlantTrace) (eventTrace : SymbolicEventTrace) : Bool :=
  eventTrace.all (eventFrameHasPlantProvenance plantTrace)

def factLinkMatches
    (plantTrace : PlantTrace)
    (eventTrace : SymbolicEventTrace)
    (link : FactAbstractionLink) : Bool :=
  match eventTrace[link.frameIndex]? with
  | none => false
  | some frame =>
      match frame.facts[link.factIndex]? with
      | none => false
      | some atom =>
          atom == link.atom
            && frame.sourcePlantSampleDigest == link.sampleDigest
            && link.derivationDigest != ""
            && link.witnessRef != ""
            && link.verified
            && plantTrace.any (fun sample =>
              sample.sampleDigest == link.sampleDigest
                && sample.timestamp == frame.timestamp)

def factLinkCount
    (links : List FactAbstractionLink) (frameIndex factIndex : Nat) : Nat :=
  (links.filter fun link =>
    link.frameIndex == frameIndex && link.factIndex == factIndex).length

def totalFactCount (eventTrace : SymbolicEventTrace) : Nat :=
  eventTrace.foldl (fun total frame => total + frame.facts.length) 0

def allFactsExactlyLinked
    (eventTrace : SymbolicEventTrace) (links : List FactAbstractionLink) : Bool :=
  (List.range eventTrace.length).all fun frameIndex =>
    match eventTrace[frameIndex]? with
    | none => false
    | some frame =>
        (List.range frame.facts.length).all fun factIndex =>
          factLinkCount links frameIndex factIndex == 1

def abstractionLinksValid
    (plantTrace : PlantTrace)
    (eventTrace : SymbolicEventTrace)
    (evidence : TraceAbstractionEvidence) : Bool :=
  evidence.verified
    && evidence.links.all (factLinkMatches plantTrace eventTrace)
    && allFactsExactlyLinked eventTrace evidence.links
    && evidence.links.length == totalFactCount eventTrace

def commandConformsToAuthorization
    (receipt : ExecutionReceipt) : Bool :=
  receipt.executedCommandDigest == receipt.authorizedCommandDigest
    || (receipt.withinAuthorizedError && receipt.errorBoundWitness != "")

def sampleInsideAuthorization
    (authorization : PrefixAuthorization)
    (receipt : ExecutionReceipt)
    (sample : PlantSample) : Bool :=
  decide (receipt.executedAt.tick <= sample.timestamp.tick)
    && decide (sample.timestamp.tick <=
      receipt.executedAt.tick + authorization.maxAuthorizedDuration.ticks)
    && decide (sample.timestamp.tick <= authorization.validUntil.tick)

structure ObservedEvidenceCheckRequest where
  prefixRequest : PrefixPreCheckRequest
  prefixWitness : WitnessRef
  record : PrefixExecutionRecord
deriving Repr, DecidableEq, BEq

def ObservedPrefixEvidenceValid (request : ObservedEvidenceCheckRequest) : Prop :=
  checkPrefixPre request.prefixRequest = .proven request.prefixWitness
  ∧ request.prefixWitness = prefixWitnessFor request.prefixRequest.candidate
  ∧ request.record.recordDigest ≠ ""
  ∧ request.record.candidate = request.prefixRequest.candidate
  ∧ request.record.candidate.authorization.contractId =
      request.prefixRequest.contract.contractId
  ∧ request.record.candidate.authorization.contractDigest =
      request.prefixRequest.contract.contractDigest
  ∧ request.record.candidate.authorization.specDigest =
      request.prefixRequest.mission.specDigest
  ∧ request.record.receipt.authorizationDigest =
      request.record.candidate.authorization.authorizationDigest
  ∧ request.record.receipt.authorizedCommandDigest =
      request.record.candidate.authorization.authorizedCommandDigest
  ∧ request.record.receipt.executedCommandDigest ≠ ""
  ∧ request.record.receipt.actuatorEvidence ≠ ""
  ∧ commandConformsToAuthorization request.record.receipt = true
  ∧ request.record.candidate.authorization.issuedAt.tick <=
      request.record.receipt.executedAt.tick
  ∧ request.record.receipt.executedAt.tick <=
      request.record.candidate.authorization.validUntil.tick
  ∧ request.record.receipt.executedAt.tick +
      request.record.candidate.authorization.maxAuthorizedDuration.ticks <=
      request.record.candidate.authorization.validUntil.tick
  ∧ request.record.receipt.executedAt.tick +
      request.record.candidate.authorization.maxAuthorizedDuration.ticks <=
      request.prefixRequest.contract.deadline.expiresAt.tick
  ∧ request.record.monitorBeforeDigest =
      request.prefixRequest.monitorState.monitorStateDigest
  ∧ request.record.monitorBeforeDigest =
      request.record.candidate.authorization.monitorStateDigest
  ∧ request.record.monitorAfterDigest ≠ ""
  ∧ request.record.monitorAfterDigest ≠ request.record.monitorBeforeDigest
  ∧ request.record.plantTraceDigest ≠ ""
  ∧ request.record.symbolicEventTraceDigest ≠ ""
  ∧ request.record.plantTimeBaseDigest = request.prefixRequest.mission.timeBase.digest
  ∧ plantTraceWellFormed request.record.plantTrace = true
  ∧ request.record.plantTrace.all (fun sample =>
      sample.authorizationDigest == request.record.receipt.authorizationDigest
        && sample.executedCommandDigest == request.record.receipt.executedCommandDigest
        && sample.hardInvariantsHold
        && sample.withinReachableTube
        && sample.modelAssumptionsHold
        && sampleInsideAuthorization
          request.record.candidate.authorization request.record.receipt sample) = true
  ∧ eventTraceWellFormed request.record.eventTrace = true
  ∧ eventTraceHasPlantProvenance
      request.record.plantTrace request.record.eventTrace = true
  ∧ abstractionLinksValid
      request.record.plantTrace
      request.record.eventTrace
      request.record.abstractionEvidence = true
  ∧ request.record.runtimeEvidence.authorizationDigest =
      request.record.receipt.authorizationDigest
  ∧ request.record.runtimeEvidence.executedCommandDigest =
      request.record.receipt.executedCommandDigest
  ∧ request.record.runtimeEvidence.plantTraceDigest = request.record.plantTraceDigest
  ∧ request.record.runtimeEvidence.tubeDigest =
      request.record.candidate.tube.tubeDigest
  ∧ request.record.runtimeEvidence.monitorBeforeDigest = request.record.monitorBeforeDigest
  ∧ request.record.runtimeEvidence.allSamplesWithinTube = true
  ∧ request.record.runtimeEvidence.allHardInvariantsHold = true
  ∧ request.record.runtimeEvidence.allModelAssumptionsHold = true
  ∧ request.record.runtimeEvidence.observerWitness ≠ ""
  ∧ request.record.runtimeEvidence.timingWitness ≠ ""
  ∧ requirementsCovered
      request.record.runtimeEvidence.coveredRequirements
      request.prefixRequest.contract.runtimeRequirements = true
  ∧ request.record.abstractionEvidence.plantTraceDigest = request.record.plantTraceDigest
  ∧ request.record.abstractionEvidence.symbolicEventTraceDigest =
      request.record.symbolicEventTraceDigest
  ∧ request.record.abstractionEvidence.timeBaseDigest =
      request.prefixRequest.mission.timeBase.digest
  ∧ request.record.abstractionEvidence.abstractorId ≠ ""
  ∧ request.record.abstractionEvidence.abstractorVersion ≠ ""
  ∧ request.record.abstractionEvidence.witnessRef ≠ ""

instance (request : ObservedEvidenceCheckRequest) :
    Decidable (ObservedPrefixEvidenceValid request) :=
  by
    unfold ObservedPrefixEvidenceValid
    infer_instance

def observedWitnessFor (record : PrefixExecutionRecord) : WitnessRef :=
  "observed:" ++ record.recordDigest

def checkObservedEvidence (request : ObservedEvidenceCheckRequest) : StaticCheckResult :=
  if ObservedPrefixEvidenceValid request then
    .proven (observedWitnessFor request.record)
  else
    .refuted ["execution receipt, authorization, tube, monitor, or trace provenance failed"]

theorem checkObservedEvidence_sound
    (request : ObservedEvidenceCheckRequest)
    (witness : WitnessRef)
    (result : checkObservedEvidence request = .proven witness) :
    ObservedPrefixEvidenceValid request := by
  unfold checkObservedEvidence at result
  split at result
  · assumption
  · simp at result

theorem checkObservedEvidence_reflects (request : ObservedEvidenceCheckRequest) :
    (∃ witness, checkObservedEvidence request = .proven witness)
      ↔ ObservedPrefixEvidenceValid request := by
  constructor
  · rintro ⟨witness, result⟩
    exact checkObservedEvidence_sound request witness result
  · intro valid
    refine ⟨observedWitnessFor request.record, ?_⟩
    simp [checkObservedEvidence, valid]

/-! ## Three-valued partial-trace semantics -/

inductive PartialVerdict where
  | satisfied
  | violated
  | pending
deriving Repr, DecidableEq, BEq

def partialNot : PartialVerdict -> PartialVerdict
  | .satisfied => .violated
  | .violated => .satisfied
  | .pending => .pending

def partialAnd (left right : PartialVerdict) : PartialVerdict :=
  match left, right with
  | .violated, _ | _, .violated => .violated
  | .satisfied, .satisfied => .satisfied
  | _, _ => .pending

def partialOr (left right : PartialVerdict) : PartialVerdict :=
  match left, right with
  | .satisfied, _ | _, .satisfied => .satisfied
  | .violated, .violated => .violated
  | _, _ => .pending

def partialAll (verdicts : List PartialVerdict) (closed : Bool) : PartialVerdict :=
  if verdicts.any (· == .violated) then
    .violated
  else if verdicts.all (· == .satisfied) then
    if closed then .satisfied else .pending
  else if closed then
    .violated
  else
    .pending

def partialExists (verdicts : List PartialVerdict) (closed : Bool) : PartialVerdict :=
  if verdicts.any (· == .satisfied) then
    .satisfied
  else if closed then
    .violated
  else
    .pending

def indicesFrom (start length : Nat) : List Nat :=
  (List.range (length - start)).map (start + ·)

def frameHasAtom (trace : SymbolicEventTrace) (index : Nat) (atom : TraceAtom) : Bool :=
  match trace[index]? with
  | none => false
  | some frame => frame.facts.contains atom

def withinWindow
    (trace : SymbolicEventTrace)
    (start index : Nat)
    (duration : Duration) : Bool :=
  match trace[start]?, trace[index]? with
  | some first, some current => current.timestamp.tick <= first.timestamp.tick + duration.ticks
  | _, _ => false

def windowExpired
    (trace : SymbolicEventTrace)
    (start : Nat)
    (duration : Duration) : Bool :=
  match trace[start]?, trace.getLast? with
  | some first, some latest => first.timestamp.tick + duration.ticks <= latest.timestamp.tick
  | _, _ => false

def windowEndpointCovered
    (trace : SymbolicEventTrace)
    (start : Nat)
    (duration : Duration) : Bool :=
  match trace[start]? with
  | none => false
  | some first => trace.any fun frame =>
      frame.timestamp.tick == first.timestamp.tick + duration.ticks

def traceIndicesGapBounded
    (trace : SymbolicEventTrace)
    (indices : List Nat)
    (maxSampleGap : Duration) : Bool :=
  (indices.zip indices.tail).all fun pair =>
    match trace[pair.fst]?, trace[pair.snd]? with
    | some first, some next =>
        next.timestamp.tick <= first.timestamp.tick + maxSampleGap.ticks
    | _, _ => false

def evalSequence
    (trace : SymbolicEventTrace)
    (index : Nat)
    (closed : Bool) : List TraceAtom -> PartialVerdict
  | [] => .violated
  | atom :: rest =>
      match trace[index]? with
      | none => if closed then .violated else .pending
      | some frame =>
          if !frame.facts.contains atom then
            .violated
          else if rest.isEmpty then
            .satisfied
          else
            evalSequence trace (index + 1) closed rest

termination_by atoms => atoms.length

def evalTraceFormulaPartial
    (maxSampleGap : Duration)
    (trace : SymbolicEventTrace)
    (index : Nat)
    (closed : Bool) : TraceFormula -> PartialVerdict
  | .atom atom =>
      match trace[index]? with
      | none => if closed then .violated else .pending
      | some frame => if frame.facts.contains atom then .satisfied else .violated
  | .neg inner => partialNot (evalTraceFormulaPartial maxSampleGap trace index closed inner)
  | .and left right =>
      partialAnd
        (evalTraceFormulaPartial maxSampleGap trace index closed left)
        (evalTraceFormulaPartial maxSampleGap trace index closed right)
  | .implies antecedent consequent =>
      partialOr
        (partialNot (evalTraceFormulaPartial maxSampleGap trace index closed antecedent))
        (evalTraceFormulaPartial maxSampleGap trace index closed consequent)
  | .always inner =>
      let verdicts := (indicesFrom index trace.length).map fun current =>
        evalTraceFormulaPartial maxSampleGap trace current closed inner
      partialAll verdicts closed
  | .eventuallyWithin duration inner =>
      let verdicts := ((indicesFrom index trace.length).filter fun current =>
        withinWindow trace index current duration).map fun current =>
          evalTraceFormulaPartial maxSampleGap trace current closed inner
      partialExists verdicts (closed || windowExpired trace index duration)
  | .until left right =>
      let candidates := (indicesFrom index trace.length).map fun stop =>
        let prior := (List.range (stop - index)).map fun offset =>
          evalTraceFormulaPartial maxSampleGap trace (index + offset) closed left
        partialAnd (partialAll prior true)
          (evalTraceFormulaPartial maxSampleGap trace stop closed right)
      if candidates.any (· == .satisfied) then
        .satisfied
      else
        let leftSoFar := (indicesFrom index trace.length).map fun current =>
          evalTraceFormulaPartial maxSampleGap trace current closed left
        if leftSoFar.any (· == .violated) then
          .violated
        else if closed then .violated else .pending
  | .sequence atoms => evalSequence trace index closed atoms
  | .stableFor duration inner =>
      let inWindow := (indicesFrom index trace.length).filter fun current =>
        withinWindow trace index current duration
      let verdicts := inWindow.map fun current =>
        evalTraceFormulaPartial maxSampleGap trace current closed inner
      if verdicts.any (· == .violated) then
        .violated
      else if windowEndpointCovered trace index duration
        && traceIndicesGapBounded trace inWindow maxSampleGap
        && verdicts.all (· == .satisfied) then
        .satisfied
      else
        .pending
  | .precededBy earlier later =>
      let laterIndices := indicesFrom index trace.length
      let validPair := laterIndices.any fun laterIndex =>
        evalTraceFormulaPartial maxSampleGap trace laterIndex closed later == .satisfied
          && (List.range (laterIndex - index)).any (fun offset =>
            evalTraceFormulaPartial maxSampleGap trace (index + offset) closed earlier == .satisfied)
      if validPair then
        .satisfied
      else
        let laterSeen := laterIndices.any fun laterIndex =>
          evalTraceFormulaPartial maxSampleGap trace laterIndex closed later == .satisfied
        if laterSeen || closed then .violated else .pending

def formulasPartialVerdict
    (maxSampleGap : Duration)
    (trace : SymbolicEventTrace)
    (closed : Bool)
    (formulas : List TraceFormula) : PartialVerdict :=
  formulas.foldl
    (fun accumulated formula =>
      partialAnd accumulated
        (evalTraceFormulaPartial maxSampleGap trace 0 closed formula))
    .satisfied

def terminalEventAtEnd
    (trace : SymbolicEventTrace) (contract : SemanticSkillContract) : Bool :=
  match trace.getLast? with
  | none => false
  | some frame => frame.facts.contains contract.terminalEvent

def allowedSampleGap (mission : MissionSpec) : Duration :=
  ⟨mission.timeBase.controlPeriod.ticks + mission.timeBase.maxSamplingJitter.ticks⟩

def hardInvariantVerdict
    (mission : MissionSpec)
    (contract : SemanticSkillContract)
    (trace : SymbolicEventTrace) : PartialVerdict :=
  formulasPartialVerdict (allowedSampleGap mission) trace
    (terminalEventAtEnd trace contract) mission.hardInvariants

def contractGuaranteeVerdict
    (mission : MissionSpec)
    (contract : SemanticSkillContract)
    (trace : SymbolicEventTrace) : PartialVerdict :=
  formulasPartialVerdict (allowedSampleGap mission) trace
    (terminalEventAtEnd trace contract) contract.guarantee

def finalPlantStateDigest (trace : PlantTrace) : Option Digest :=
  trace.getLast?.map PlantSample.stateDigest

def postEvidenceBundleValid
    (contract : SemanticSkillContract)
    (record : PrefixExecutionRecord)
    (currentStateDigest : Digest)
    (evidence : PostEvidenceBundle) : Bool :=
  evidence.evidenceDigest != ""
    && evidence.contractDigest == contract.contractDigest
    && evidence.recordDigest == record.recordDigest
    && evidence.finalStateDigest == currentStateDigest
    && evidence.monitorAfterDigest == record.monitorAfterDigest
    && evidence.producerId != ""
    && evidence.producerVersion != ""
    && evidence.witnessRef != ""
    && evidence.verified
    && requirementsCovered evidence.coveredRequirements contract.postRequirements
    && match record.eventTrace.getLast? with
       | none => false
       | some frame =>
           frame.facts.contains contract.terminalEvent
             && evidence.terminalFrameSourceDigest == frame.sourcePlantSampleDigest
             && evidence.terminalFrameTimestamp == frame.timestamp

structure MonitorCheckRequest where
  observed : ObservedEvidenceCheckRequest
  observedWitness : WitnessRef
  priorState : MonitorState
  currentStateDigest : Digest
  nextProposalIndex : Nat
  currentTime : Timestamp
  postEvidence : PostEvidenceBundle
deriving Repr, DecidableEq, BEq

def monitorBindingsValid (request : MonitorCheckRequest) : Bool :=
  let precheck := request.observed.prefixRequest
  let record := request.observed.record
  request.priorState == precheck.monitorState
    && request.priorState.monitorStateDigest == record.monitorBeforeDigest
    && request.priorState.contractId == precheck.contract.contractId
    && request.priorState.specDigest == precheck.mission.specDigest
    && request.priorState.phase == precheck.contract.phaseBefore
    && request.priorState.nextProposalIndex == record.candidate.proposal.proposalIndex
    && request.nextProposalIndex == record.candidate.proposal.proposalIndex + 1
    && record.monitorAfterDigest != ""
    && finalPlantStateDigest record.plantTrace == some request.currentStateDigest
    && match record.plantTrace.getLast? with
       | none => false
       | some sample => sample.timestamp.tick <= request.currentTime.tick

def pendingMonitorState (request : MonitorCheckRequest) : MonitorState :=
  let precheck := request.observed.prefixRequest
  let record := request.observed.record
  { monitorStateDigest := record.monitorAfterDigest
    contractId := precheck.contract.contractId
    specDigest := precheck.mission.specDigest
    phase := precheck.contract.phaseBefore
    stateDigest := request.currentStateDigest
    nextProposalIndex := request.nextProposalIndex
    pending := precheck.contract.guarantee
    hasPending := true
    lastEventTimestamp :=
      match record.eventTrace.getLast? with
      | none => request.priorState.lastEventTimestamp
      | some frame => frame.timestamp }

def completeWitnessFor (request : MonitorCheckRequest) : WitnessRef :=
  let precheck := request.observed.prefixRequest
  let record := request.observed.record
  "complete:" ++ precheck.contract.contractDigest
    ++ ":" ++ record.recordDigest
    ++ ":" ++ request.postEvidence.evidenceDigest
    ++ ":" ++ record.monitorAfterDigest

def monitorStep (request : MonitorCheckRequest) : MonitorVerdict :=
  let precheck := request.observed.prefixRequest
  let record := request.observed.record
  match checkObservedEvidence request.observed with
  | .inconsistent conflicts => .inconsistent conflicts
  | .unknown missing => .unknown missing
  | .refuted counterexamples => .violated counterexamples
  | .proven actualWitness =>
      if actualWitness != request.observedWitness then
        .inconsistent ["observed witness is not bound to the checked record"]
      else if !monitorBindingsValid request then
        .inconsistent ["record does not continue the supplied persistent monitor state"]
      else if precheck.contract.deadline.expiresAt.tick < request.currentTime.tick then
        .violated ["contract deadline expired before completion was accepted"]
      else
        let terminalSeen := terminalEventAtEnd record.eventTrace precheck.contract
        let invariantVerdict :=
          hardInvariantVerdict precheck.mission precheck.contract record.eventTrace
        let guaranteeVerdict :=
          contractGuaranteeVerdict precheck.mission precheck.contract record.eventTrace
        if invariantVerdict = .violated then
          .violated ["a frozen mission invariant is violated on the checked prefix"]
        else if guaranteeVerdict = .violated then
          .violated ["the semantic contract is refuted by the checked trace"]
        else if terminalSeen = true
          ∧ invariantVerdict = .satisfied
          ∧ guaranteeVerdict = .satisfied then
          if postEvidenceBundleValid
              precheck.contract record request.currentStateDigest request.postEvidence then
            .complete (completeWitnessFor request)
          else
            .unknown ["required post-condition evidence is missing"]
        else if terminalSeen = true then
          .unknown ["terminal event is present but temporal obligations remain undecidable"]
        else
          .safePending (pendingMonitorState request)

def CurrentPrefixSafeUnderCheckedEvidence (request : MonitorCheckRequest) : Prop :=
  checkObservedEvidence request.observed = .proven request.observedWitness
  ∧ monitorBindingsValid request = true
  ∧ request.currentTime.tick <=
      request.observed.prefixRequest.contract.deadline.expiresAt.tick
  ∧ hardInvariantVerdict
      request.observed.prefixRequest.mission
      request.observed.prefixRequest.contract
      request.observed.record.eventTrace ≠ .violated
  ∧ contractGuaranteeVerdict
      request.observed.prefixRequest.mission
      request.observed.prefixRequest.contract
      request.observed.record.eventTrace ≠ .violated

def PendingObligations (state : MonitorState) : Prop :=
  state.hasPending = true ∧ state.pending ≠ []

def CompletedTraceConforms (request : MonitorCheckRequest) : Prop :=
  checkObservedEvidence request.observed = .proven request.observedWitness
  ∧ monitorBindingsValid request = true
  ∧ request.currentTime.tick <=
      request.observed.prefixRequest.contract.deadline.expiresAt.tick
  ∧ terminalEventAtEnd
      request.observed.record.eventTrace
      request.observed.prefixRequest.contract = true
  ∧ hardInvariantVerdict
      request.observed.prefixRequest.mission
      request.observed.prefixRequest.contract
      request.observed.record.eventTrace = .satisfied
  ∧ contractGuaranteeVerdict
      request.observed.prefixRequest.mission
      request.observed.prefixRequest.contract
      request.observed.record.eventTrace = .satisfied
  ∧ postEvidenceBundleValid
      request.observed.prefixRequest.contract
      request.observed.record
      request.currentStateDigest
      request.postEvidence = true

instance (request : MonitorCheckRequest) : Decidable (CurrentPrefixSafeUnderCheckedEvidence request) :=
  by unfold CurrentPrefixSafeUnderCheckedEvidence; infer_instance

instance (request : MonitorCheckRequest) : Decidable (CompletedTraceConforms request) :=
  by unfold CompletedTraceConforms; infer_instance

set_option linter.unusedSimpArgs false in
theorem monitor_pending_sound
    (request : MonitorCheckRequest)
    (state : MonitorState)
    (result : monitorStep request = .safePending state) :
    CurrentPrefixSafeUnderCheckedEvidence request ∧ PendingObligations state := by
  unfold monitorStep at result
  repeat' (split at result <;> simp_all [CurrentPrefixSafeUnderCheckedEvidence,
    PendingObligations, pendingMonitorState])
  repeat' (split at result <;> simp_all [CurrentPrefixSafeUnderCheckedEvidence,
    PendingObligations, pendingMonitorState])
  have observedValid : ObservedPrefixEvidenceValid request.observed := by
    apply checkObservedEvidence_sound request.observed request.observedWitness
    assumption
  have prefixValid : PrefixPreCertified request.observed.prefixRequest :=
    checkPrefixPre_sound _ request.observed.prefixWitness observedValid.1
  have guaranteeNonempty := prefixValid.guarantee_nonempty
  subst state
  simp_all [CurrentPrefixSafeUnderCheckedEvidence, PendingObligations,
    pendingMonitorState]

set_option linter.unusedSimpArgs false in
theorem monitor_complete_sound
    (request : MonitorCheckRequest)
    (witness : WitnessRef)
    (result : monitorStep request = .complete witness) :
    CompletedTraceConforms request := by
  unfold monitorStep at result
  repeat' (split at result <;> simp_all [CompletedTraceConforms])
  repeat' (split at result <;> simp_all [CompletedTraceConforms])
  repeat' (split at result <;> simp_all [CompletedTraceConforms])
  split at result <;> try simp_all [CompletedTraceConforms]
  split at result <;> try simp_all [CompletedTraceConforms]
  split at result <;> try simp_all [CompletedTraceConforms]
  split at result <;> try simp_all [CompletedTraceConforms]
  split at result <;> simp_all [CompletedTraceConforms]

end ProofAlign
