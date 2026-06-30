import ProofAlign.Intent
import ProofAlign.Effect
import ProofAlign.Certificate

namespace ProofAlign

def SafeAction (after : WorldState) (spec : SafetySpec) : Bool :=
  basicRuntimeSafe after spec

def DualAligned (intent : TaskIntent) (before : WorldState) (action : Action) (after : WorldState) (spec : SafetySpec) : Bool :=
  IntentAligned intent action spec && EffectAligned before action after spec

def CertifiedDualAligned
    (intent : TaskIntent)
    (before : WorldState)
    (action : Action)
    (after : WorldState)
    (spec : SafetySpec)
    (preCerts : List Certificate)
    (postCerts : List Certificate)
    (minConfidence : Nat) : Bool :=
  DualAligned intent before action after spec
  && PreCertificatesValid preCerts action minConfidence
  && PostCertificatesValid postCerts action minConfidence

end ProofAlign
