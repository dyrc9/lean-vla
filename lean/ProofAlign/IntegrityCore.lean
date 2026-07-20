import Std

namespace ProofAlign.IntegrityCore

/-!
# Minimal ProofAlign integrity core

This module mirrors the two relations, two invariants, and four causal arms in
`proofalign.integrity_*`.  It deliberately omits signatures, provenance,
filters, certificate leases, and physical dynamics.  A future online
Lean-backed claim still requires a refinement/equivalence artifact connecting
the Python fast checker and its concrete serialization to this model.
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

def intentSatisfied (arm : MethodArm) (verdict : LayerVerdict) : Prop :=
  match arm with
  | .intentOnly | .dual => verdict = .proven
  | .vlaOnly | .executionOnly => verdict = .disabled

def executionSatisfied (arm : MethodArm) (verdict : LayerVerdict) : Prop :=
  match arm with
  | .executionOnly | .dual => verdict = .proven
  | .vlaOnly | .intentOnly => verdict = .disabled

structure ActiveContract where
  missionRootDigest : String
  contractDigest : String
  episodeNonce : String
  phaseBefore : String
  expectedNextPhase : String
  completionAtoms : List String
deriving Repr, DecidableEq

structure PrefixAuthorization where
  arm : MethodArm
  verdict : CoreVerdict
  missionRootDigest : String
  contractDigest : String
  episodeNonce : String
  stateDigest : String
  monitorDigest : String
  proposalIndex : Nat
  proposalDigest : String
  finalCommandDigest : Option String
  intentVerdict : LayerVerdict
  executionVerdict : LayerVerdict
  issuedAtNs : Nat
  validUntilNs : Nat
deriving Repr, DecidableEq

def dispatchAuthorized
    (contract : ActiveContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat) : Prop :=
  authorization.verdict = .allow
    ∧ authorization.missionRootDigest = contract.missionRootDigest
    ∧ authorization.contractDigest = contract.contractDigest
    ∧ authorization.episodeNonce = contract.episodeNonce
    ∧ intentSatisfied authorization.arm authorization.intentVerdict
    ∧ executionSatisfied authorization.arm authorization.executionVerdict
    ∧ authorization.issuedAtNs ≤ nowNs
    ∧ nowNs ≤ authorization.validUntilNs
    ∧ authorization.finalCommandDigest.isSome
    ∧ (authorization.arm = .executionOnly ∨ authorization.arm = .dual →
        authorization.finalCommandDigest = some appliedCommandDigest)

theorem dual_dispatch_requires_intent_authorization
    (contract : ActiveContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat)
    (arm : authorization.arm = .dual)
    (dispatch : dispatchAuthorized contract authorization appliedCommandDigest nowNs) :
    authorization.intentVerdict = .proven := by
  rcases dispatch with ⟨_, _, _, _, intent, _⟩
  simpa [intentSatisfied, arm] using intent

theorem dual_dispatch_requires_execution_authorization
    (contract : ActiveContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat)
    (arm : authorization.arm = .dual)
    (dispatch : dispatchAuthorized contract authorization appliedCommandDigest nowNs) :
    authorization.executionVerdict = .proven := by
  rcases dispatch with ⟨_, _, _, _, _, execution, _⟩
  simpa [executionSatisfied, arm] using execution

theorem execution_arm_dispatches_exact_command
    (contract : ActiveContract)
    (authorization : PrefixAuthorization)
    (appliedCommandDigest : String)
    (nowNs : Nat)
    (arm : authorization.arm = .executionOnly ∨ authorization.arm = .dual)
    (dispatch : dispatchAuthorized contract authorization appliedCommandDigest nowNs) :
    authorization.finalCommandDigest = some appliedCommandDigest := by
  exact dispatch.2.2.2.2.2.2.2.2.2 arm

structure ExecutionEvidence where
  authorizationDigest : String
  receiptDigest : String
  episodeNonce : String
  proposalIndex : Nat
  observedCommandDigest : Option String
  observedAtoms : List String
  known : Bool
  violation : Bool
deriving Repr, DecidableEq

def checkedCompletion
    (contract : ActiveContract)
    (evidence : ExecutionEvidence) : Prop :=
  evidence.known = true
    ∧ evidence.violation = false
    ∧ ∀ atom ∈ contract.completionAtoms, atom ∈ evidence.observedAtoms

def phaseAdvanceAllowed
    (contract : ActiveContract)
    (evidence : ExecutionEvidence)
    (nextPhase : String) : Prop :=
  nextPhase = contract.expectedNextPhase ∧ checkedCompletion contract evidence

theorem no_phase_advance_without_checked_completion
    (contract : ActiveContract)
    (evidence : ExecutionEvidence)
    (nextPhase : String)
    (advance : phaseAdvanceAllowed contract evidence nextPhase) :
    checkedCompletion contract evidence :=
  advance.2

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
