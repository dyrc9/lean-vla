import Std

namespace ProofAlign.IntegrityCore

/-!
# Action-block integrity core

The policy-facing object is an `ActionBlock`; no explicit high-level policy
plan is assumed.  Intent–Action assessment remains an external semantic
verdict.  Lean specifies the second boundary: an authorized block, its exact
dispatch receipt, and its observed effects must form one bound transaction
before an execution-enabled arm may advance the task phase.

This model deliberately omits signatures, learned-assessor correctness,
perception correctness, floating point, and continuous dynamics.  A Python/
Lean equivalence artifact is still required for every online claim.
-/

inductive MethodArm where
  | vlaOnly
  | intentOnly
  | executionOnly
  | dual
deriving Repr, DecidableEq

inductive LayerVerdict where
  | disabled
  | proven
  | refuted
  | unknown
deriving Repr, DecidableEq

inductive CoreVerdict where
  | allow
  | pending
  | complete
  | reject
  | unknown
deriving Repr, DecidableEq

def intentEnabled : MethodArm → Bool
  | .intentOnly | .dual => true
  | .vlaOnly | .executionOnly => false

def executionEnabled : MethodArm → Bool
  | .executionOnly | .dual => true
  | .vlaOnly | .intentOnly => false

def intentSatisfied (arm : MethodArm) (verdict : LayerVerdict) : Prop :=
  match arm with
  | .intentOnly | .dual => verdict = .proven
  | .vlaOnly | .executionOnly => verdict = .disabled

def executionSatisfied (arm : MethodArm) (verdict : LayerVerdict) : Prop :=
  match arm with
  | .executionOnly | .dual => verdict = .proven
  | .vlaOnly | .intentOnly => verdict = .disabled

theorem intent_switch_truth_table
    (arm : MethodArm)
    (verdict : LayerVerdict) :
    intentSatisfied arm verdict ↔
      if intentEnabled arm then verdict = .proven else verdict = .disabled := by
  cases arm <;> simp [intentSatisfied, intentEnabled]

theorem execution_switch_truth_table
    (arm : MethodArm)
    (verdict : LayerVerdict) :
    executionSatisfied arm verdict ↔
      if executionEnabled arm then verdict = .proven else verdict = .disabled := by
  cases arm <;> simp [executionSatisfied, executionEnabled]

structure ActiveContract where
  missionRootDigest : String
  contractDigest : String
  episodeNonce : String
  phaseBefore : String
  expectedNextPhase : String
  completionAtoms : List String
deriving Repr, DecidableEq

structure ActionBlock where
  actionBlockDigest : String
  episodeNonce : String
  proposalIndex : Nat
  observationDigest : String
  stateEpoch : Nat
  commandDigest : String
deriving Repr, DecidableEq

structure ActionAssessment where
  assessmentDigest : String
  actionBlockDigest : String
  episodeNonce : String
  proposalIndex : Nat
  observationDigest : String
  stateEpoch : Nat
deriving Repr, DecidableEq

structure BlockExecutionContract where
  executionContractDigest : String
  actionBlockDigest : String
  assessmentDigest : String
  episodeNonce : String
  proposalIndex : Nat
  observationDigest : String
  stateEpoch : Nat
  expectedEffectAtoms : List String
  forbiddenEffectAtoms : List String
deriving Repr, DecidableEq

def assessmentBound
    (block : ActionBlock)
    (assessment : ActionAssessment) : Prop :=
  assessment.actionBlockDigest = block.actionBlockDigest
    ∧ assessment.episodeNonce = block.episodeNonce
    ∧ assessment.proposalIndex = block.proposalIndex
    ∧ assessment.observationDigest = block.observationDigest
    ∧ assessment.stateEpoch = block.stateEpoch

def executionContractBound
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract) : Prop :=
  assessmentBound block assessment
    ∧ contract.actionBlockDigest = block.actionBlockDigest
    ∧ contract.assessmentDigest = assessment.assessmentDigest
    ∧ contract.episodeNonce = block.episodeNonce
    ∧ contract.proposalIndex = block.proposalIndex
    ∧ contract.observationDigest = block.observationDigest
    ∧ contract.stateEpoch = block.stateEpoch

structure PrefixAuthorization where
  arm : MethodArm
  verdict : CoreVerdict
  authorizationDigest : String
  missionRootDigest : String
  contractDigest : String
  episodeNonce : String
  stateDigest : String
  monitorDigest : String
  proposalIndex : Nat
  actionBlockDigest : String
  assessmentDigest : String
  executionContractDigest : String
  finalCommandDigest : Option String
  intentVerdict : LayerVerdict
  executionVerdict : LayerVerdict
  issuedAtNs : Nat
  validUntilNs : Nat
deriving Repr, DecidableEq

def dispatchAuthorized
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat) : Prop :=
  authorization.verdict = .allow
    ∧ authorization.missionRootDigest = task.missionRootDigest
    ∧ authorization.contractDigest = task.contractDigest
    ∧ authorization.episodeNonce = task.episodeNonce
    ∧ intentSatisfied authorization.arm authorization.intentVerdict
    ∧ executionSatisfied authorization.arm authorization.executionVerdict
    ∧ (intentEnabled authorization.arm = true →
        assessmentBound block assessment
          ∧ authorization.actionBlockDigest = block.actionBlockDigest
          ∧ authorization.assessmentDigest = assessment.assessmentDigest)
    ∧ (executionEnabled authorization.arm = true →
        executionContractBound block assessment executionContract
          ∧ authorization.actionBlockDigest = block.actionBlockDigest
          ∧ authorization.assessmentDigest = assessment.assessmentDigest
          ∧ authorization.executionContractDigest =
              executionContract.executionContractDigest)
    ∧ authorization.issuedAtNs ≤ nowNs
    ∧ nowNs ≤ authorization.validUntilNs
    ∧ authorization.finalCommandDigest.isSome
    ∧ (executionEnabled authorization.arm = true →
        authorization.finalCommandDigest = some appliedCommandDigest)

theorem dual_dispatch_requires_intent_authorization
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat)
    (arm : authorization.arm = .dual)
    (dispatch :
      dispatchAuthorized task block assessment executionContract
        authorization appliedCommandDigest nowNs) :
    authorization.intentVerdict = .proven := by
  rcases dispatch with ⟨_, _, _, _, intent, _⟩
  simpa [intentSatisfied, arm] using intent

theorem dual_dispatch_requires_execution_authorization
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat)
    (arm : authorization.arm = .dual)
    (dispatch :
      dispatchAuthorized task block assessment executionContract
        authorization appliedCommandDigest nowNs) :
    authorization.executionVerdict = .proven := by
  rcases dispatch with ⟨_, _, _, _, _, execution, _⟩
  simpa [executionSatisfied, arm] using execution

theorem execution_arm_dispatches_exact_command
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat)
    (enabled : executionEnabled authorization.arm = true)
    (dispatch :
      dispatchAuthorized task block assessment executionContract
        authorization appliedCommandDigest nowNs) :
    authorization.finalCommandDigest = some appliedCommandDigest := by
  rcases dispatch with ⟨_, _, _, _, _, _, _, _, _, _, _, exact⟩
  exact exact enabled

structure DispatchReceipt where
  receiptDigest : String
  authorizationDigest : String
  actionBlockDigest : String
  executionContractDigest : String
  episodeNonce : String
  proposalIndex : Nat
  appliedCommandDigest : String
deriving Repr, DecidableEq

structure ExecutionEvidence where
  authorizationDigest : String
  receiptDigest : String
  actionBlockDigest : String
  executionContractDigest : String
  episodeNonce : String
  proposalIndex : Nat
  observedCommandDigest : Option String
  observedAtoms : List String
  known : Bool
  observationWindowComplete : Bool
  violation : Bool
deriving Repr, DecidableEq

def executionEffectBound
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : DispatchReceipt)
    (evidence : ExecutionEvidence) : Prop :=
  executionContractBound block assessment executionContract
    ∧ authorization.actionBlockDigest = block.actionBlockDigest
    ∧ authorization.assessmentDigest = assessment.assessmentDigest
    ∧ authorization.executionContractDigest =
        executionContract.executionContractDigest
    ∧ receipt.authorizationDigest = authorization.authorizationDigest
    ∧ receipt.actionBlockDigest = block.actionBlockDigest
    ∧ receipt.executionContractDigest =
        executionContract.executionContractDigest
    ∧ evidence.authorizationDigest = authorization.authorizationDigest
    ∧ evidence.receiptDigest = receipt.receiptDigest
    ∧ evidence.actionBlockDigest = block.actionBlockDigest
    ∧ evidence.executionContractDigest =
        executionContract.executionContractDigest
    ∧ receipt.episodeNonce = block.episodeNonce
    ∧ evidence.episodeNonce = block.episodeNonce
    ∧ receipt.proposalIndex = block.proposalIndex
    ∧ evidence.proposalIndex = block.proposalIndex
    ∧ evidence.observedCommandDigest = some receipt.appliedCommandDigest

def expectedEffectsSatisfied
    (executionContract : BlockExecutionContract)
    (evidence : ExecutionEvidence) : Prop :=
  ∀ atom ∈ executionContract.expectedEffectAtoms, atom ∈ evidence.observedAtoms

def forbiddenEffectsAbsent
    (executionContract : BlockExecutionContract)
    (evidence : ExecutionEvidence) : Prop :=
  ∀ atom ∈ executionContract.forbiddenEffectAtoms, atom ∉ evidence.observedAtoms

def blockExecutionAligned
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : DispatchReceipt)
    (evidence : ExecutionEvidence) : Prop :=
  evidence.known = true
    ∧ evidence.observationWindowComplete = true
    ∧ evidence.violation = false
    ∧ executionEffectBound block assessment executionContract
        authorization receipt evidence
    ∧ expectedEffectsSatisfied executionContract evidence
    ∧ forbiddenEffectsAbsent executionContract evidence

def contractCompletionObserved
    (task : ActiveContract)
    (evidence : ExecutionEvidence) : Prop :=
  ∀ atom ∈ task.completionAtoms, atom ∈ evidence.observedAtoms

def checkedCompletion
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : DispatchReceipt)
    (evidence : ExecutionEvidence) : Prop :=
  contractCompletionObserved task evidence
    ∧ (executionEnabled authorization.arm = true →
        blockExecutionAligned block assessment executionContract
          authorization receipt evidence)

def phaseAdvanceAllowed
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : DispatchReceipt)
    (evidence : ExecutionEvidence)
    (nextPhase : String) : Prop :=
  nextPhase = task.expectedNextPhase
    ∧ checkedCompletion task block assessment executionContract
        authorization receipt evidence

theorem no_phase_advance_without_checked_completion
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : DispatchReceipt)
    (evidence : ExecutionEvidence)
    (nextPhase : String)
    (advance :
      phaseAdvanceAllowed task block assessment executionContract
        authorization receipt evidence nextPhase) :
    checkedCompletion task block assessment executionContract
      authorization receipt evidence :=
  advance.2

theorem execution_enabled_phase_advance_requires_alignment
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : DispatchReceipt)
    (evidence : ExecutionEvidence)
    (nextPhase : String)
    (enabled : executionEnabled authorization.arm = true)
    (advance :
      phaseAdvanceAllowed task block assessment executionContract
        authorization receipt evidence nextPhase) :
    blockExecutionAligned block assessment executionContract
      authorization receipt evidence :=
  advance.2.2 enabled

theorem phase_advance_requires_contract_completion
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (executionContract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : DispatchReceipt)
    (evidence : ExecutionEvidence)
    (nextPhase : String)
    (advance :
      phaseAdvanceAllowed task block assessment executionContract
        authorization receipt evidence nextPhase) :
    contractCompletionObserved task evidence :=
  advance.2.1

theorem intent_only_does_not_satisfy_execution_layer
    (verdict : LayerVerdict)
    (satisfied : executionSatisfied .intentOnly verdict) :
    verdict = .disabled := by
  simpa [executionSatisfied] using satisfied

theorem execution_only_does_not_satisfy_intent_layer
    (verdict : LayerVerdict)
    (satisfied : intentSatisfied .executionOnly verdict) :
    verdict = .disabled := by
  simpa [intentSatisfied] using satisfied

end ProofAlign.IntegrityCore
