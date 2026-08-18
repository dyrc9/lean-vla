import Std

namespace ProofAlign.SemanticIntegrityCore

/-!
# Semantic-bound integrity v4 core

This is the successor of the frozen v3 `IntegrityCore`; it does not replace or
reinterpret that source.  It adds the semantic context/subtask/prompt identity
and models an `(H,D)` prefix as one authorization with an ordered receipt
window.  Learned semantic correctness, perception, floating point, and Python
serialization remain outside the theorem scope.
-/

inductive MethodArm where
  | vlaOnly
  | semanticOnly
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
  | reject
  | unknown
deriving Repr, DecidableEq

def semanticEnabled : MethodArm → Bool
  | .semanticOnly | .dual => true
  | .vlaOnly | .executionOnly => false

def executionEnabled : MethodArm → Bool
  | .executionOnly | .dual => true
  | .vlaOnly | .semanticOnly => false

def layerSatisfied (enabled : Bool) (verdict : LayerVerdict) : Prop :=
  if enabled then verdict = .proven else verdict = .disabled

def coreDecision
    (arm : MethodArm)
    (semanticVerdict executionVerdict : LayerVerdict) : CoreVerdict :=
  let enabledVerdicts :=
    (if semanticEnabled arm then [semanticVerdict] else [])
      ++ (if executionEnabled arm then [executionVerdict] else [])
  if .refuted ∈ enabledVerdicts then .reject
  else if .unknown ∈ enabledVerdicts then .unknown
  else .allow

theorem semantic_switch_truth_table
    (arm : MethodArm)
    (verdict : LayerVerdict) :
    layerSatisfied (semanticEnabled arm) verdict ↔
      if semanticEnabled arm then verdict = .proven
      else verdict = .disabled := by
  simp [layerSatisfied]

theorem execution_switch_truth_table
    (arm : MethodArm)
    (verdict : LayerVerdict) :
    layerSatisfied (executionEnabled arm) verdict ↔
      if executionEnabled arm then verdict = .proven
      else verdict = .disabled := by
  simp [layerSatisfied]

theorem four_arm_nominal_truth_table :
    coreDecision .vlaOnly .disabled .disabled = .allow
      ∧ coreDecision .semanticOnly .proven .disabled = .allow
      ∧ coreDecision .executionOnly .disabled .proven = .allow
      ∧ coreDecision .dual .proven .proven = .allow := by
  decide

theorem semantic_refutation_truth_table :
    coreDecision .vlaOnly .refuted .proven = .allow
      ∧ coreDecision .semanticOnly .refuted .proven = .reject
      ∧ coreDecision .executionOnly .refuted .proven = .allow
      ∧ coreDecision .dual .refuted .proven = .reject := by
  decide

theorem execution_unknown_truth_table :
    coreDecision .vlaOnly .proven .unknown = .allow
      ∧ coreDecision .semanticOnly .proven .unknown = .allow
      ∧ coreDecision .executionOnly .proven .unknown = .unknown
      ∧ coreDecision .dual .proven .unknown = .unknown := by
  decide

structure ActionBlock where
  actionBlockDigest : String
  episodeNonce : String
  proposalIndex : Nat
  candidateIndex : Nat
  stateEpoch : Nat
  semanticContextDigest : String
  semanticSubtaskDigest : String
  exactPolicyPromptDigest : String
  trustedObservationDigest : String
  commandDigest : String
  orderedActionDigests : List String
  actionCount : Nat
deriving Repr, DecidableEq

structure ActionAssessment where
  assessmentDigest : String
  actionBlockDigest : String
  episodeNonce : String
  proposalIndex : Nat
  candidateIndex : Nat
  stateEpoch : Nat
  semanticSubtaskDigest : String
  trustedObservationDigest : String
  known : Bool
deriving Repr, DecidableEq

structure BlockExecutionContract where
  executionContractDigest : String
  actionBlockDigest : String
  assessmentDigest : String
  episodeNonce : String
  proposalIndex : Nat
  candidateIndex : Nat
  stateEpoch : Nat
  semanticSubtaskDigest : String
  exactPolicyPromptDigest : String
  expectedEffectAtoms : List String
  forbiddenEffectAtoms : List String
deriving Repr, DecidableEq

def assessmentBound
    (block : ActionBlock)
    (assessment : ActionAssessment) : Prop :=
  assessment.actionBlockDigest = block.actionBlockDigest
    ∧ assessment.episodeNonce = block.episodeNonce
    ∧ assessment.proposalIndex = block.proposalIndex
    ∧ assessment.candidateIndex = block.candidateIndex
    ∧ assessment.stateEpoch = block.stateEpoch
    ∧ assessment.semanticSubtaskDigest = block.semanticSubtaskDigest
    ∧ assessment.trustedObservationDigest =
        block.trustedObservationDigest

def executionContractBound
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract) : Prop :=
  assessmentBound block assessment
    ∧ contract.actionBlockDigest = block.actionBlockDigest
    ∧ contract.assessmentDigest = assessment.assessmentDigest
    ∧ contract.episodeNonce = block.episodeNonce
    ∧ contract.proposalIndex = block.proposalIndex
    ∧ contract.candidateIndex = block.candidateIndex
    ∧ contract.stateEpoch = block.stateEpoch
    ∧ contract.semanticSubtaskDigest = block.semanticSubtaskDigest
    ∧ contract.exactPolicyPromptDigest =
        block.exactPolicyPromptDigest

structure PrefixAuthorization where
  authorizationDigest : String
  episodeNonce : String
  proposalIndex : Nat
  candidateIndex : Nat
  stateEpoch : Nat
  semanticContextDigest : String
  semanticSubtaskDigest : String
  exactPolicyPromptDigest : String
  trustedObservationDigest : String
  actionBlockDigest : String
  assessmentDigest : String
  executionContractDigest : String
  finalCommandDigest : String
  orderedActionDigests : List String
  actionCount : Nat
  issuedAtNs : Nat
  validUntilNs : Nat
deriving Repr, DecidableEq

def authorizationBound
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (nowNs : Nat) : Prop :=
  executionContractBound block assessment contract
    ∧ assessment.known = true
    ∧ authorization.episodeNonce = block.episodeNonce
    ∧ authorization.proposalIndex = block.proposalIndex
    ∧ authorization.candidateIndex = block.candidateIndex
    ∧ authorization.stateEpoch = block.stateEpoch
    ∧ authorization.semanticContextDigest =
        block.semanticContextDigest
    ∧ authorization.semanticSubtaskDigest =
        block.semanticSubtaskDigest
    ∧ authorization.exactPolicyPromptDigest =
        block.exactPolicyPromptDigest
    ∧ authorization.trustedObservationDigest =
        block.trustedObservationDigest
    ∧ authorization.actionBlockDigest = block.actionBlockDigest
    ∧ authorization.assessmentDigest = assessment.assessmentDigest
    ∧ authorization.executionContractDigest =
        contract.executionContractDigest
    ∧ authorization.finalCommandDigest = block.commandDigest
    ∧ block.orderedActionDigests.length = block.actionCount
    ∧ authorization.orderedActionDigests = block.orderedActionDigests
    ∧ authorization.actionCount = block.actionCount
    ∧ authorization.issuedAtNs ≤ nowNs
    ∧ nowNs ≤ authorization.validUntilNs

theorem authorization_binds_semantic_identity
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (nowNs : Nat)
    (bound :
      authorizationBound block assessment contract authorization nowNs) :
    authorization.semanticContextDigest = block.semanticContextDigest
      ∧ authorization.semanticSubtaskDigest =
          block.semanticSubtaskDigest
      ∧ authorization.exactPolicyPromptDigest =
          block.exactPolicyPromptDigest := by
  rcases bound with
    ⟨_, _, _, _, _, _, semanticContext, semanticSubtask,
      exactPrompt, _⟩
  exact ⟨semanticContext, semanticSubtask, exactPrompt⟩

theorem authorization_binds_exact_final_command
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (nowNs : Nat)
    (bound :
      authorizationBound block assessment contract authorization nowNs) :
    authorization.finalCommandDigest = block.commandDigest := by
  rcases bound with
    ⟨_, _, _, _, _, _, _, _, _, _, _, _, _, exactCommand, _⟩
  exact exactCommand

theorem authorization_binds_ordered_actions
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (nowNs : Nat)
    (bound :
      authorizationBound block assessment contract authorization nowNs) :
    authorization.orderedActionDigests = block.orderedActionDigests
      ∧ authorization.orderedActionDigests.length =
          authorization.actionCount := by
  rcases bound with
    ⟨_, _, _, _, _, _, _, _, _, _, _, _, _, _, blockLength,
      orderedActions, actionCount, _⟩
  constructor
  · exact orderedActions
  · calc
      authorization.orderedActionDigests.length =
          block.orderedActionDigests.length :=
        congrArg List.length orderedActions
      _ = block.actionCount := blockLength
      _ = authorization.actionCount := actionCount.symm

structure DispatchLedger where
  consumedAuthorizationDigests : List String
deriving Repr, DecidableEq

def authorizationAvailable
    (ledger : DispatchLedger)
    (authorization : PrefixAuthorization) : Prop :=
  authorization.authorizationDigest ∉
    ledger.consumedAuthorizationDigests

theorem consumed_authorization_not_available
    (ledger : DispatchLedger)
    (authorization : PrefixAuthorization)
    (consumed :
      authorization.authorizationDigest ∈
        ledger.consumedAuthorizationDigests) :
    ¬ authorizationAvailable ledger authorization := by
  simpa [authorizationAvailable]

structure StepDispatchReceipt where
  receiptDigest : String
  authorizationDigest : String
  actionBlockDigest : String
  assessmentDigest : String
  executionContractDigest : String
  episodeNonce : String
  proposalIndex : Nat
  stepIndex : Nat
  actionCount : Nat
  authorizedActionDigest : String
  appliedActionDigest : String
deriving Repr, DecidableEq

def stepReceiptBound
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipt : StepDispatchReceipt) : Prop :=
  receipt.authorizationDigest = authorization.authorizationDigest
    ∧ receipt.actionBlockDigest = block.actionBlockDigest
    ∧ receipt.assessmentDigest = assessment.assessmentDigest
    ∧ receipt.executionContractDigest =
        contract.executionContractDigest
    ∧ receipt.episodeNonce = block.episodeNonce
    ∧ receipt.proposalIndex = block.proposalIndex
    ∧ receipt.actionCount = authorization.actionCount
    ∧ receipt.stepIndex < receipt.actionCount
    ∧ authorization.orderedActionDigests[receipt.stepIndex]? =
        some receipt.authorizedActionDigest
    ∧ receipt.appliedActionDigest = receipt.authorizedActionDigest

structure PrefixExecutionEvidence where
  evidenceDigest : String
  authorizationDigest : String
  actionBlockDigest : String
  assessmentDigest : String
  executionContractDigest : String
  episodeNonce : String
  proposalIndex : Nat
  stepReceiptDigests : List String
  observedActionDigests : List String
  observationDigests : List String
  observedEffectAtoms : List String
  observedViolationAtoms : List String
  prefixComplete : Bool
  observationWindowComplete : Bool
  effectsKnown : Bool
deriving Repr, DecidableEq

def receiptWindowBound
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence) : Prop :=
  (∀ receipt ∈ receipts,
      stepReceiptBound block assessment contract authorization receipt)
    ∧ evidence.authorizationDigest = authorization.authorizationDigest
    ∧ evidence.actionBlockDigest = block.actionBlockDigest
    ∧ evidence.assessmentDigest = assessment.assessmentDigest
    ∧ evidence.executionContractDigest =
        contract.executionContractDigest
    ∧ evidence.episodeNonce = block.episodeNonce
    ∧ evidence.proposalIndex = block.proposalIndex
    ∧ evidence.stepReceiptDigests = receipts.map (·.receiptDigest)
    ∧ evidence.observedActionDigests =
        receipts.map (·.appliedActionDigest)
    ∧ evidence.observationDigests.length = receipts.length
    ∧ (evidence.prefixComplete = true →
        receipts.length = authorization.actionCount)

def expectedEffectsSatisfied
    (contract : BlockExecutionContract)
    (evidence : PrefixExecutionEvidence) : Prop :=
  ∀ atom ∈ contract.expectedEffectAtoms,
    atom ∈ evidence.observedEffectAtoms

def forbiddenEffectsAbsent
    (contract : BlockExecutionContract)
    (evidence : PrefixExecutionEvidence) : Prop :=
  ∀ atom ∈ contract.forbiddenEffectAtoms,
    atom ∉ evidence.observedEffectAtoms

def blockExecutionAligned
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence) : Prop :=
  evidence.effectsKnown = true
    ∧ evidence.prefixComplete = true
    ∧ evidence.observationWindowComplete = true
    ∧ evidence.observedViolationAtoms = []
    ∧ receiptWindowBound block assessment contract authorization
        receipts evidence
    ∧ expectedEffectsSatisfied contract evidence
    ∧ forbiddenEffectsAbsent contract evidence

theorem every_bound_receipt_uses_same_authorization
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (window :
      receiptWindowBound block assessment contract authorization
        receipts evidence)
    (receipt : StepDispatchReceipt)
    (member : receipt ∈ receipts) :
    receipt.authorizationDigest = authorization.authorizationDigest := by
  exact (window.1 receipt member).1

theorem every_bound_receipt_applies_exact_action
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (window :
      receiptWindowBound block assessment contract authorization
        receipts evidence)
    (receipt : StepDispatchReceipt)
    (member : receipt ∈ receipts) :
    receipt.appliedActionDigest = receipt.authorizedActionDigest := by
  rcases window.1 receipt member with
    ⟨_, _, _, _, _, _, _, _, _, appliedExact⟩
  exact appliedExact

theorem every_bound_receipt_matches_authorized_step
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (window :
      receiptWindowBound block assessment contract authorization
        receipts evidence)
    (receipt : StepDispatchReceipt)
    (member : receipt ∈ receipts) :
    authorization.orderedActionDigests[receipt.stepIndex]? =
      some receipt.appliedActionDigest := by
  rcases window.1 receipt member with
    ⟨_, _, _, _, _, _, _, _, authorizedStep, appliedExact⟩
  simpa [appliedExact] using authorizedStep

theorem unknown_effects_block_execution_alignment
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (unknown : evidence.effectsKnown = false) :
    ¬ blockExecutionAligned block assessment contract authorization
        receipts evidence := by
  intro aligned
  have known : evidence.effectsKnown = true := aligned.1
  rw [unknown] at known
  cases known

theorem incomplete_prefix_blocks_execution_alignment
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (incomplete : evidence.prefixComplete = false) :
    ¬ blockExecutionAligned block assessment contract authorization
        receipts evidence := by
  intro aligned
  have complete : evidence.prefixComplete = true := aligned.2.1
  rw [incomplete] at complete
  cases complete

structure ActiveContract where
  expectedNextPhase : String
  completionAtoms : List String
deriving Repr, DecidableEq

def contractCompletionObserved
    (task : ActiveContract)
    (evidence : PrefixExecutionEvidence) : Prop :=
  ∀ atom ∈ task.completionAtoms, atom ∈ evidence.observedEffectAtoms

def phaseAdvanceAllowed
    (arm : MethodArm)
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (nextPhase : String) : Prop :=
  nextPhase = task.expectedNextPhase
    ∧ contractCompletionObserved task evidence
    ∧ (executionEnabled arm = true →
        blockExecutionAligned block assessment contract authorization
          receipts evidence)

theorem execution_enabled_phase_advance_requires_alignment
    (arm : MethodArm)
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (nextPhase : String)
    (enabled : executionEnabled arm = true)
    (advance :
      phaseAdvanceAllowed arm task block assessment contract
        authorization receipts evidence nextPhase) :
    blockExecutionAligned block assessment contract authorization
      receipts evidence :=
  advance.2.2 enabled

theorem phase_advance_requires_contract_completion
    (arm : MethodArm)
    (task : ActiveContract)
    (block : ActionBlock)
    (assessment : ActionAssessment)
    (contract : BlockExecutionContract)
    (authorization : PrefixAuthorization)
    (receipts : List StepDispatchReceipt)
    (evidence : PrefixExecutionEvidence)
    (nextPhase : String)
    (advance :
      phaseAdvanceAllowed arm task block assessment contract
        authorization receipts evidence nextPhase) :
    contractCompletionObserved task evidence :=
  advance.2.1

end ProofAlign.SemanticIntegrityCore
