import ProofAlign.Core

namespace ProofAlign

inductive CertKind where
  | objectIdentity
  | affordance
  | collisionFree
  | humanClearance
  | obstacleClearance
  | regionOccupancy
  | stateTransition
  | frameCondition
deriving Repr, DecidableEq, BEq

inductive CertStatus where
  | valid
  | invalid
  | missing
  | expired
  | lowConfidence
  | unknown
deriving Repr, DecidableEq, BEq

structure Certificate where
  kind : CertKind
  status : CertStatus := CertStatus.valid
  subject : Option ObjectId := none
  target : Option String := none
  value : Nat := 100
  threshold : Nat := 0
  confidence : Nat := 100
deriving Repr, DecidableEq, BEq

def CertificateValid (minConfidence : Nat) (cert : Certificate) : Bool :=
  cert.status == CertStatus.valid
  && cert.confidence >= minConfidence
  && cert.value >= cert.threshold

def HasValidCertificate
    (certs : List Certificate)
    (kind : CertKind)
    (subject : Option ObjectId)
    (minConfidence : Nat) : Bool :=
  certs.any (fun cert =>
    cert.kind == kind
    && cert.subject == subject
    && CertificateValid minConfidence cert)

def PreCertificatesValid (certs : List Certificate) (action : Action) (minConfidence : Nat) : Bool :=
  match action with
  | Action.pick obj _part =>
      HasValidCertificate certs CertKind.objectIdentity (some obj) minConfidence
      && HasValidCertificate certs CertKind.affordance (some obj) minConfidence
  | Action.place obj _region =>
      HasValidCertificate certs CertKind.objectIdentity (some obj) minConfidence
      && HasValidCertificate certs CertKind.collisionFree none minConfidence
      && HasValidCertificate certs CertKind.humanClearance none minConfidence
  | Action.moveTo obj _region =>
      HasValidCertificate certs CertKind.objectIdentity (some obj) minConfidence
      && HasValidCertificate certs CertKind.collisionFree none minConfidence
      && HasValidCertificate certs CertKind.humanClearance none minConfidence
  | Action.avoid _obj => true
  | Action.stop => true
  | Action.reject => true

def PostCertificatesValid (certs : List Certificate) (action : Action) (minConfidence : Nat) : Bool :=
  match action with
  | Action.pick obj _part =>
      HasValidCertificate certs CertKind.stateTransition (some obj) minConfidence
      && HasValidCertificate certs CertKind.frameCondition (some obj) minConfidence
  | Action.place obj _region =>
      HasValidCertificate certs CertKind.stateTransition (some obj) minConfidence
      && HasValidCertificate certs CertKind.frameCondition (some obj) minConfidence
  | Action.moveTo obj _region =>
      HasValidCertificate certs CertKind.stateTransition (some obj) minConfidence
      && HasValidCertificate certs CertKind.frameCondition (some obj) minConfidence
  | Action.avoid _obj => true
  | Action.stop => true
  | Action.reject => true

end ProofAlign
