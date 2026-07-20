import ProofAlign.CTDA
import Std

namespace ProofAlign.CTDAV2

/-!
# CTDA v2 no-dispatch kernel model

This module is versioned independently from the evaluated CTDA v1 model.  It
formalizes the first v2 boundary: a semantic certificate may be long lived in
plant/control epochs, but dispatch still requires a post-proof state rebind and
a short, command-specific authorization.  It does not yet connect the Python v2
wire to kernel replay or prove physical dynamics/filter properties.
-/

abbrev ControlEpoch := Nat

structure RelevantStateSnapshot where
  episodeNonce : String
  stateEpoch : Nat
  stateDigest : Digest
  observedAtNs : Nat
  maxSensorAgeNs : Nat
  producerDigest : Digest
  known : Bool
deriving Repr, DecidableEq, BEq

structure ContractContext where
  missionRootDigest : Digest
  episodeNonce : String
  phase : PhaseId
  residualObligations : List String
  contractVersion : String
  controlEpoch : ControlEpoch
deriving Repr, DecidableEq, BEq

structure SemanticCertificate where
  certificateDigest : Digest
  missionRootDigest : Digest
  episodeNonce : String
  phase : PhaseId
  residualObligations : List String
  contractVersion : String
  proofState : RelevantStateSnapshot
  actionSetDigest : Digest
  checkerDigest : Digest
  proofArtifactDigest : Digest
  proofCompletedAtNs : Nat
  proofAuthenticated : Bool
deriving Repr, DecidableEq, BEq

structure StateRebindLease where
  leaseDigest : Digest
  certificateDigest : Digest
  activationState : RelevantStateSnapshot
  checkerDigest : Digest
  activatedAtNs : Nat
  activatedControlEpoch : ControlEpoch
  validThroughControlEpoch : ControlEpoch
  rebindAuthenticated : Bool
deriving Repr, DecidableEq, BEq

def contextMatches
    (certificate : SemanticCertificate)
    (context : ContractContext) : Bool :=
  certificate.missionRootDigest == context.missionRootDigest
    && certificate.episodeNonce == context.episodeNonce
    && certificate.phase == context.phase
    && certificate.residualObligations == context.residualObligations
    && certificate.contractVersion == context.contractVersion

def postProofStateFresh
    (certificate : SemanticCertificate)
    (lease : StateRebindLease)
    (nowNs : Nat) : Bool :=
  lease.activationState.known
    && certificate.proofCompletedAtNs <= lease.activationState.observedAtNs
    && lease.activationState.observedAtNs <= lease.activatedAtNs
    && lease.activatedAtNs <= nowNs
    && nowNs <= lease.activationState.observedAtNs + lease.activationState.maxSensorAgeNs

def controlLeaseCovers
    (lease : StateRebindLease)
    (controlEpoch : ControlEpoch) : Bool :=
  lease.activatedControlEpoch <= controlEpoch
    && controlEpoch <= lease.validThroughControlEpoch

def leaseAuthorized
    (certificate : SemanticCertificate)
    (lease : StateRebindLease)
    (context : ContractContext)
    (nowNs : Nat) : Bool :=
  certificate.proofAuthenticated
    && lease.rebindAuthenticated
    && lease.certificateDigest == certificate.certificateDigest
    && lease.checkerDigest == certificate.checkerDigest
    && lease.activationState.episodeNonce == context.episodeNonce
    && contextMatches certificate context
    && postProofStateFresh certificate lease nowNs
    && controlLeaseCovers lease context.controlEpoch

theorem lease_authorized_requires_context
    (certificate : SemanticCertificate)
    (lease : StateRebindLease)
    (context : ContractContext)
    (nowNs : Nat) :
    leaseAuthorized certificate lease context nowNs = true →
      contextMatches certificate context = true := by
  simp [leaseAuthorized]
  intro _ _ _ _ _ contextMatch _ _
  exact contextMatch

theorem lease_authorized_requires_post_proof_freshness
    (certificate : SemanticCertificate)
    (lease : StateRebindLease)
    (context : ContractContext)
    (nowNs : Nat) :
    leaseAuthorized certificate lease context nowNs = true →
      postProofStateFresh certificate lease nowNs = true := by
  simp [leaseAuthorized]
  intro _ _ _ _ _ _ freshness _
  exact freshness

inductive Intervention where
  | pass
  | projectOrBrake
  | replan
  | hardBlock
deriving Repr, DecidableEq, BEq

structure PrefixDecision where
  certificateDigest : Digest
  leaseDigest : Digest
  episodeNonce : String
  controlEpoch : ControlEpoch
  nominalCommandDigest : Digest
  adjustedCommandDigest : Option Digest
  intervention : Intervention
  filterEvidenceDigest : Option Digest
  membershipAuthenticated : Bool
deriving Repr, DecidableEq, BEq

def decisionBindingHolds (decision : PrefixDecision) : Bool :=
  match decision.intervention with
  | .pass =>
      decision.adjustedCommandDigest == some decision.nominalCommandDigest
        && decision.filterEvidenceDigest.isNone
        && decision.membershipAuthenticated
  | .projectOrBrake =>
      decision.adjustedCommandDigest.isSome
        && decision.adjustedCommandDigest != some decision.nominalCommandDigest
        && decision.filterEvidenceDigest.isSome
        && decision.membershipAuthenticated
  | .replan | .hardBlock =>
      decision.adjustedCommandDigest.isNone
        && decision.filterEvidenceDigest.isNone
        && !decision.membershipAuthenticated

structure PrefixAuthorization where
  authorizationDigest : Digest
  decisionDigest : Digest
  certificateDigest : Digest
  leaseDigest : Digest
  episodeNonce : String
  controlEpoch : ControlEpoch
  authorizedCommandDigest : Digest
  issuedAtNs : Nat
  validUntilNs : Nat
  authenticated : Bool
  unused : Bool
deriving Repr, DecidableEq, BEq

def dispatchAuthorized
    (certificate : SemanticCertificate)
    (lease : StateRebindLease)
    (context : ContractContext)
    (decision : PrefixDecision)
    (authorization : PrefixAuthorization)
    (decisionDigest : Digest)
    (nowNs : Nat) : Bool :=
  leaseAuthorized certificate lease context nowNs
    && decisionBindingHolds decision
    && (decision.intervention == .pass || decision.intervention == .projectOrBrake)
    && decision.certificateDigest == certificate.certificateDigest
    && decision.leaseDigest == lease.leaseDigest
    && decision.episodeNonce == context.episodeNonce
    && decision.controlEpoch == context.controlEpoch
    && authorization.authenticated
    && authorization.unused
    && authorization.decisionDigest == decisionDigest
    && authorization.certificateDigest == certificate.certificateDigest
    && authorization.leaseDigest == lease.leaseDigest
    && authorization.episodeNonce == context.episodeNonce
    && authorization.controlEpoch == context.controlEpoch
    && authorization.issuedAtNs <= nowNs
    && nowNs <= authorization.validUntilNs
    && decision.adjustedCommandDigest == some authorization.authorizedCommandDigest

theorem no_dispatch_without_fresh_lease
    (certificate : SemanticCertificate)
    (lease : StateRebindLease)
    (context : ContractContext)
    (decision : PrefixDecision)
    (authorization : PrefixAuthorization)
    (decisionDigest : Digest)
    (nowNs : Nat) :
    dispatchAuthorized certificate lease context decision authorization decisionDigest nowNs = true →
      leaseAuthorized certificate lease context nowNs = true := by
  simp [dispatchAuthorized]
  intro lease _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
  exact lease

theorem pass_preserves_nominal_digest
    (decision : PrefixDecision) :
    decision.intervention = .pass →
      decisionBindingHolds decision = true →
      decision.adjustedCommandDigest = some decision.nominalCommandDigest := by
  intro intervention
  simp [decisionBindingHolds, intervention]
  intro command _ _
  exact command

structure ProgressLedger where
  revision : Nat
  progressEpoch : Nat
  consecutiveNonprogressControlEpochs : Nat
  cumulativeTranslation : Nat
  cumulativeMotion : Nat
  replanCount : Nat
deriving Repr, DecidableEq, BEq

def recordReplan (ledger : ProgressLedger) : ProgressLedger :=
  { ledger with
    revision := ledger.revision + 1
    replanCount := ledger.replanCount + 1 }

theorem replan_does_not_refund_translation (ledger : ProgressLedger) :
    (recordReplan ledger).cumulativeTranslation = ledger.cumulativeTranslation := by
  rfl

theorem replan_does_not_refund_motion (ledger : ProgressLedger) :
    (recordReplan ledger).cumulativeMotion = ledger.cumulativeMotion := by
  rfl

theorem replan_does_not_manufacture_progress (ledger : ProgressLedger) :
    (recordReplan ledger).progressEpoch = ledger.progressEpoch := by
  rfl

end ProofAlign.CTDAV2
