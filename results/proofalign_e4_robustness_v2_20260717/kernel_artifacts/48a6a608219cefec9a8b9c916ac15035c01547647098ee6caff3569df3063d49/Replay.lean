import ProofAlign.CTDAWire

open ProofAlign.WireV1

def replayRequest : SemanticPayload :=
  {
    missionDigest := (String.mk [Char.ofNat 109, Char.ofNat 105, Char.ofNat 115, Char.ofNat 115, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    contractSpecDigest := (String.mk [Char.ofNat 109, Char.ofNat 105, Char.ofNat 115, Char.ofNat 115, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    contractDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 110, Char.ofNat 116, Char.ofNat 114, Char.ofNat 97, Char.ofNat 99, Char.ofNat 116])
    activePhase := (String.mk [Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104])
    contractPhase := (String.mk [Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104])
    enabledObligationIds := [(String.mk [Char.ofNat 112, Char.ofNat 105, Char.ofNat 99, Char.ofNat 107, Char.ofNat 58, Char.ofNat 109, Char.ofNat 117, Char.ofNat 103])]
    contractObligationIds := [(String.mk [Char.ofNat 112, Char.ofNat 105, Char.ofNat 99, Char.ofNat 107, Char.ofNat 58, Char.ofNat 109, Char.ofNat 117, Char.ofNat 103])]
    contractTarget := some ((String.mk [Char.ofNat 109, Char.ofNat 117, Char.ofNat 103]))
    obligationTarget := some ((String.mk [Char.ofNat 109, Char.ofNat 117, Char.ofNat 103]))
    contractPart := some ((String.mk [Char.ofNat 104, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100, Char.ofNat 108, Char.ofNat 101]))
    obligationPart := some ((String.mk [Char.ofNat 104, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100, Char.ofNat 108, Char.ofNat 101]))
    contractRegion := none
    obligationRegion := none
    missionIntegrity := true
    contractIntegrity := true
    issuedAtNs := 10
    deadlineNs := 100
    nowNs := 20
    guarantee := Formula.atom (String.mk [Char.ofNat 104, Char.ofNat 111, Char.ofNat 108, Char.ofNat 100, Char.ofNat 105, Char.ofNat 110, Char.ofNat 103, Char.ofNat 58, Char.ofNat 109, Char.ofNat 117, Char.ofNat 103]) true
  }

example : checkSemantic replayRequest = StaticResult.proven := by decide
