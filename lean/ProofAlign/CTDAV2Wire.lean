import ProofAlign.CTDAV2
import Std

namespace ProofAlign.WireV2

/-!
# Executable CTDA v2 wire replay boundary

The Python decoder owns canonical JSON, exact-field, digest-format, and request-id
validation.  This module independently evaluates the normalized six-stage wire
payload.  External attestation verification is represented by an explicit
authenticated bit plus exact subject/producer bindings; false or mismatched
bindings fail closed.
-/

open ProofAlign.CTDAV2

inductive V2Result where
  | proven
  | refuted
  | replan
  | hardBlock
  | inconsistent
deriving Repr, DecidableEq, BEq

structure SemanticCertificatePayload where
  claimDigest : String
  certificateDigest : String
  missionRootDigest : String
  episodeNonce : String
  phase : String
  residualObligations : List String
  contractVersion : String
  proofStateEpisodeNonce : String
  proofStateKnown : Bool
  proofStateObservedAtNs : Nat
  proofStartedAtNs : Nat
  proofCompletedAtNs : Nat
  proofAttestationIssuedAtNs : Nat
  proofAttestationSubjectDigest : String
  proofProducerId : String
  expectedProofProducerId : String
  proofProducerVersion : String
  expectedProofProducerVersion : String
  proofAuthenticated : Bool
  fastCheckerDigest : String
  expectedFastCheckerDigest : String
deriving Repr, DecidableEq, BEq

def checkSemanticCertificate (payload : SemanticCertificatePayload) : V2Result :=
  if payload.proofStateKnown
      && payload.proofStateEpisodeNonce == payload.episodeNonce
      && payload.proofStateObservedAtNs ≤ payload.proofStartedAtNs
      && payload.proofStartedAtNs ≤ payload.proofCompletedAtNs
      && payload.proofAttestationIssuedAtNs == payload.proofCompletedAtNs
      && payload.proofAttestationSubjectDigest == payload.claimDigest
      && payload.proofProducerId == payload.expectedProofProducerId
      && payload.proofProducerVersion == payload.expectedProofProducerVersion
      && payload.proofAuthenticated
      && payload.fastCheckerDigest == payload.expectedFastCheckerDigest then
    .proven
  else
    .refuted

structure StateRebindPayload where
  certificateVerdict : V2Result
  certificateDigest : String
  leaseDigest : String
  leaseClaimDigest : String
  leaseCertificateDigest : String
  certificateCheckerDigest : String
  leaseCheckerDigest : String
  certificateMissionRootDigest : String
  contextMissionRootDigest : String
  certificateEpisodeNonce : String
  activationEpisodeNonce : String
  contextEpisodeNonce : String
  certificatePhase : String
  contextPhase : String
  certificateResidualObligations : List String
  contextResidualObligations : List String
  certificateContractVersion : String
  contextContractVersion : String
  proofCompletedAtNs : Nat
  activationStateKnown : Bool
  activationObservedAtNs : Nat
  activationMaxSensorAgeNs : Nat
  activatedAtNs : Nat
  nowNs : Nat
  activatedControlEpoch : Nat
  validThroughControlEpoch : Nat
  contextControlEpoch : Nat
  rebindAttestationSubjectDigest : String
  rebindAuthenticated : Bool
deriving Repr, DecidableEq, BEq

def checkStateRebind (payload : StateRebindPayload) : V2Result :=
  if payload.certificateVerdict == .proven
      && payload.certificateDigest == payload.leaseCertificateDigest
      && payload.certificateCheckerDigest == payload.leaseCheckerDigest
      && payload.certificateMissionRootDigest == payload.contextMissionRootDigest
      && payload.certificateEpisodeNonce == payload.activationEpisodeNonce
      && payload.certificateEpisodeNonce == payload.contextEpisodeNonce
      && payload.certificatePhase == payload.contextPhase
      && payload.certificateResidualObligations == payload.contextResidualObligations
      && payload.certificateContractVersion == payload.contextContractVersion
      && payload.activationStateKnown
      && 0 < payload.activationMaxSensorAgeNs
      && payload.proofCompletedAtNs ≤ payload.activationObservedAtNs
      && payload.activationObservedAtNs ≤ payload.activatedAtNs
      && payload.activatedAtNs ≤ payload.nowNs
      && payload.nowNs ≤ payload.activationObservedAtNs + payload.activationMaxSensorAgeNs
      && payload.activatedControlEpoch ≤ payload.contextControlEpoch
      && payload.contextControlEpoch ≤ payload.validThroughControlEpoch
      && payload.rebindAttestationSubjectDigest == payload.leaseClaimDigest
      && payload.rebindAuthenticated then
    .proven
  else
    .refuted

structure PrefixDecisionPayload where
  leaseVerdict : V2Result
  certificateDigest : String
  decisionCertificateDigest : String
  leaseDigest : String
  decisionLeaseDigest : String
  contextEpisodeNonce : String
  decisionEpisodeNonce : String
  contextControlEpoch : Nat
  decisionControlEpoch : Nat
  activationSnapshotDigest : String
  decisionStateSnapshotDigest : String
  safetyBundleDigest : String
  decisionSafetyBundleDigest : String
  requiredSafetyChannelsComplete : Bool
  safetyUnknown : Bool
  safetyViolated : Bool
  decisionClaimDigest : String
  nominalCommandDigest : String
  intervention : Intervention
  adjustedCommandDigest : Option String
  filterApplicationDigest : Option String
  filterNominalCommandDigest : Option String
  filterAdjustedCommandDigest : Option String
  membershipAttestationSubjectDigest : Option String
  membershipAuthenticated : Bool
deriving Repr, DecidableEq, BEq

def decisionBindingHolds (payload : PrefixDecisionPayload) : Bool :=
  match payload.intervention with
  | .pass =>
      payload.adjustedCommandDigest == some payload.nominalCommandDigest
        && payload.filterApplicationDigest.isNone
        && payload.filterNominalCommandDigest.isNone
        && payload.filterAdjustedCommandDigest.isNone
        && payload.membershipAttestationSubjectDigest == some payload.decisionClaimDigest
        && payload.membershipAuthenticated
  | .projectOrBrake =>
      payload.adjustedCommandDigest.isSome
        && payload.adjustedCommandDigest != some payload.nominalCommandDigest
        && payload.filterApplicationDigest.isSome
        && payload.filterNominalCommandDigest == some payload.nominalCommandDigest
        && payload.filterAdjustedCommandDigest == payload.adjustedCommandDigest
        && payload.membershipAttestationSubjectDigest == some payload.decisionClaimDigest
        && payload.membershipAuthenticated
  | .replan | .hardBlock =>
      payload.adjustedCommandDigest.isNone
        && payload.filterApplicationDigest.isNone
        && payload.filterNominalCommandDigest.isNone
        && payload.filterAdjustedCommandDigest.isNone
        && payload.membershipAttestationSubjectDigest.isNone
        && !payload.membershipAuthenticated

def decisionSafetyHolds (payload : PrefixDecisionPayload) : Bool :=
  (!payload.safetyUnknown
      || payload.intervention == .replan
      || payload.intervention == .hardBlock)
    && (!payload.safetyViolated || payload.intervention == .hardBlock)

def checkPrefixDecision (payload : PrefixDecisionPayload) : V2Result :=
  if payload.leaseVerdict == .proven
      && payload.certificateDigest == payload.decisionCertificateDigest
      && payload.leaseDigest == payload.decisionLeaseDigest
      && payload.contextEpisodeNonce == payload.decisionEpisodeNonce
      && payload.contextControlEpoch == payload.decisionControlEpoch
      && payload.activationSnapshotDigest == payload.decisionStateSnapshotDigest
      && payload.safetyBundleDigest == payload.decisionSafetyBundleDigest
      && payload.requiredSafetyChannelsComplete
      && decisionBindingHolds payload
      && decisionSafetyHolds payload then
    .proven
  else
    .refuted

structure PrefixAuthorizationPayload where
  decisionVerdict : V2Result
  intervention : Intervention
  decisionDigest : String
  authorizationDecisionDigest : String
  certificateDigest : String
  authorizationCertificateDigest : String
  leaseDigest : String
  authorizationLeaseDigest : String
  contextEpisodeNonce : String
  authorizationEpisodeNonce : String
  decisionProposalIndex : Nat
  authorizationProposalIndex : Nat
  contextControlEpoch : Nat
  authorizationControlEpoch : Nat
  decisionAdjustedCommandDigest : Option String
  authorizedCommandDigest : String
  issuedAtNs : Nat
  validUntilNs : Nat
  nowNs : Nat
  authorizationClaimDigest : String
  authorizationAttestationSubjectDigest : String
  authorizationAuthenticated : Bool
  authorizationUnused : Bool
deriving Repr, DecidableEq, BEq

def dispatchCapable : Intervention → Bool
  | .pass | .projectOrBrake => true
  | .replan | .hardBlock => false

def checkPrefixAuthorization (payload : PrefixAuthorizationPayload) : V2Result :=
  if payload.decisionVerdict == .proven
      && dispatchCapable payload.intervention
      && payload.decisionDigest == payload.authorizationDecisionDigest
      && payload.certificateDigest == payload.authorizationCertificateDigest
      && payload.leaseDigest == payload.authorizationLeaseDigest
      && payload.contextEpisodeNonce == payload.authorizationEpisodeNonce
      && payload.decisionProposalIndex == payload.authorizationProposalIndex
      && payload.contextControlEpoch == payload.authorizationControlEpoch
      && payload.decisionAdjustedCommandDigest == some payload.authorizedCommandDigest
      && payload.issuedAtNs ≤ payload.nowNs
      && payload.nowNs ≤ payload.validUntilNs
      && payload.authorizationAttestationSubjectDigest == payload.authorizationClaimDigest
      && payload.authorizationAuthenticated
      && payload.authorizationUnused then
    .proven
  else
    .refuted

structure DispatchReceiptPayload where
  authorizationVerdict : V2Result
  authorizationDigest : String
  receiptAuthorizationDigest : String
  authorizationEpisodeNonce : String
  receiptEpisodeNonce : String
  authorizationProposalIndex : Nat
  receiptProposalIndex : Nat
  authorizationControlEpoch : Nat
  receiptControlEpoch : Nat
  decisionNominalCommandDigest : String
  receiptNominalCommandDigest : String
  authorizedCommandDigest : String
  executedCommandDigest : String
  issuedAtNs : Nat
  validUntilNs : Nat
  dispatchedAtNs : Nat
  receiptActuatorSubjectDigest : String
  expectedActuatorSubjectDigest : String
  actuatorAuthenticated : Bool
  authorizationUnused : Bool
deriving Repr, DecidableEq, BEq

def checkDispatchReceipt (payload : DispatchReceiptPayload) : V2Result :=
  if payload.authorizationVerdict == .proven
      && payload.authorizationUnused
      && payload.authorizationDigest == payload.receiptAuthorizationDigest
      && payload.authorizationEpisodeNonce == payload.receiptEpisodeNonce
      && payload.authorizationProposalIndex == payload.receiptProposalIndex
      && payload.authorizationControlEpoch == payload.receiptControlEpoch
      && payload.decisionNominalCommandDigest == payload.receiptNominalCommandDigest
      && payload.authorizedCommandDigest == payload.executedCommandDigest
      && payload.issuedAtNs ≤ payload.dispatchedAtNs
      && payload.dispatchedAtNs ≤ payload.validUntilNs
      && payload.receiptActuatorSubjectDigest == payload.expectedActuatorSubjectDigest
      && payload.actuatorAuthenticated then
    .proven
  else
    .refuted

structure ProgressUpdatePayload where
  certificateDigest : String
  ledgerCertificateDigest : String
  beforeSnapshotDigest : String
  ledgerLastSnapshotDigest : String
  afterEpisodeNonce : String
  ledgerEpisodeNonce : String
  lastStateEpoch : Nat
  afterStateEpoch : Nat
  afterStateKnown : Bool
  afterObservedAtNs : Nat
  afterMaxSensorAgeNs : Nat
  nowNs : Nat
  progressClaimDigest : String
  progressAttestationSubjectDigest : String
  progressAuthenticated : Bool
  distanceBeforeUm : Option Nat
  distanceAfterUm : Option Nat
  minimumProgressUm : Nat
  elapsedControlEpochs : Nat
  consecutiveNonprogressControlEpochs : Nat
  maxNonprogressControlEpochs : Nat
  cumulativeTranslationUm : Nat
  translationConsumedUm : Nat
  translationBudgetUm : Nat
  cumulativeMotionUnits : Nat
  motionConsumedUnits : Nat
  motionBudgetUnits : Nat
deriving Repr, DecidableEq, BEq

def progressBindingHolds (payload : ProgressUpdatePayload) : Bool :=
  payload.certificateDigest == payload.ledgerCertificateDigest
    && payload.beforeSnapshotDigest == payload.ledgerLastSnapshotDigest
    && payload.afterEpisodeNonce == payload.ledgerEpisodeNonce
    && payload.lastStateEpoch < payload.afterStateEpoch
    && payload.afterStateKnown
    && payload.afterObservedAtNs ≤ payload.nowNs
    && payload.nowNs ≤ payload.afterObservedAtNs + payload.afterMaxSensorAgeNs
    && payload.progressAttestationSubjectDigest == payload.progressClaimDigest
    && payload.progressAuthenticated
    && 0 < payload.minimumProgressUm
    && 0 < payload.elapsedControlEpochs

def progressBudgetExhausted
    (payload : ProgressUpdatePayload)
    (nonprogressControlEpochs : Nat) : Bool :=
  payload.translationBudgetUm
      < payload.cumulativeTranslationUm + payload.translationConsumedUm
    || payload.motionBudgetUnits
      < payload.cumulativeMotionUnits + payload.motionConsumedUnits
    || payload.maxNonprogressControlEpochs < nonprogressControlEpochs

def checkProgressUpdate (payload : ProgressUpdatePayload) : V2Result :=
  if !progressBindingHolds payload then
    .hardBlock
  else
    match payload.distanceBeforeUm, payload.distanceAfterUm with
    | some before, some after =>
        let madeProgress := after + payload.minimumProgressUm ≤ before
        let nonprogress :=
          if madeProgress then 0
          else payload.consecutiveNonprogressControlEpochs + payload.elapsedControlEpochs
        if progressBudgetExhausted payload nonprogress then
          .hardBlock
        else if madeProgress then
          .proven
        else
          .replan
    | none, none =>
        if progressBudgetExhausted payload payload.consecutiveNonprogressControlEpochs then
          .hardBlock
        else
          .replan
    | _, _ => .hardBlock

theorem authorization_proven_requires_unused
    (payload : PrefixAuthorizationPayload) :
    checkPrefixAuthorization payload = .proven → payload.authorizationUnused = true := by
  simp [checkPrefixAuthorization]

theorem receipt_proven_preserves_adjusted_command
    (payload : DispatchReceiptPayload) :
    checkDispatchReceipt payload = .proven →
      payload.executedCommandDigest = payload.authorizedCommandDigest := by
  simp [checkDispatchReceipt]
  intro _ _ _ _ _ _ _ command _ _ _ _
  exact command.symm

end ProofAlign.WireV2
