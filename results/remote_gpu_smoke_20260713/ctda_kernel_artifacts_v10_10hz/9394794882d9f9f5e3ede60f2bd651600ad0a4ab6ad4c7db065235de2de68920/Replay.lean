import ProofAlign.CTDAWire

open ProofAlign.WireV1

def replayRequest : SemanticPayload :=
  {
    missionDigest := (String.mk [Char.ofNat 56, Char.ofNat 48, Char.ofNat 99, Char.ofNat 101, Char.ofNat 99, Char.ofNat 97, Char.ofNat 53, Char.ofNat 57, Char.ofNat 52, Char.ofNat 57, Char.ofNat 48, Char.ofNat 55, Char.ofNat 100, Char.ofNat 55, Char.ofNat 98, Char.ofNat 98, Char.ofNat 97, Char.ofNat 102, Char.ofNat 57, Char.ofNat 102, Char.ofNat 49, Char.ofNat 102, Char.ofNat 99, Char.ofNat 54, Char.ofNat 100, Char.ofNat 102, Char.ofNat 98, Char.ofNat 100, Char.ofNat 98, Char.ofNat 54, Char.ofNat 57, Char.ofNat 53, Char.ofNat 49, Char.ofNat 99, Char.ofNat 102, Char.ofNat 48, Char.ofNat 97, Char.ofNat 98, Char.ofNat 100, Char.ofNat 101, Char.ofNat 57, Char.ofNat 50, Char.ofNat 100, Char.ofNat 55, Char.ofNat 51, Char.ofNat 97, Char.ofNat 56, Char.ofNat 48, Char.ofNat 99, Char.ofNat 51, Char.ofNat 102, Char.ofNat 52, Char.ofNat 54, Char.ofNat 54, Char.ofNat 50, Char.ofNat 52, Char.ofNat 53, Char.ofNat 55, Char.ofNat 102, Char.ofNat 54, Char.ofNat 57, Char.ofNat 51, Char.ofNat 98, Char.ofNat 99])
    contractSpecDigest := (String.mk [Char.ofNat 56, Char.ofNat 48, Char.ofNat 99, Char.ofNat 101, Char.ofNat 99, Char.ofNat 97, Char.ofNat 53, Char.ofNat 57, Char.ofNat 52, Char.ofNat 57, Char.ofNat 48, Char.ofNat 55, Char.ofNat 100, Char.ofNat 55, Char.ofNat 98, Char.ofNat 98, Char.ofNat 97, Char.ofNat 102, Char.ofNat 57, Char.ofNat 102, Char.ofNat 49, Char.ofNat 102, Char.ofNat 99, Char.ofNat 54, Char.ofNat 100, Char.ofNat 102, Char.ofNat 98, Char.ofNat 100, Char.ofNat 98, Char.ofNat 54, Char.ofNat 57, Char.ofNat 53, Char.ofNat 49, Char.ofNat 99, Char.ofNat 102, Char.ofNat 48, Char.ofNat 97, Char.ofNat 98, Char.ofNat 100, Char.ofNat 101, Char.ofNat 57, Char.ofNat 50, Char.ofNat 100, Char.ofNat 55, Char.ofNat 51, Char.ofNat 97, Char.ofNat 56, Char.ofNat 48, Char.ofNat 99, Char.ofNat 51, Char.ofNat 102, Char.ofNat 52, Char.ofNat 54, Char.ofNat 54, Char.ofNat 50, Char.ofNat 52, Char.ofNat 53, Char.ofNat 55, Char.ofNat 102, Char.ofNat 54, Char.ofNat 57, Char.ofNat 51, Char.ofNat 98, Char.ofNat 99])
    contractDigest := (String.mk [Char.ofNat 101, Char.ofNat 99, Char.ofNat 48, Char.ofNat 57, Char.ofNat 100, Char.ofNat 53, Char.ofNat 48, Char.ofNat 98, Char.ofNat 53, Char.ofNat 56, Char.ofNat 56, Char.ofNat 51, Char.ofNat 99, Char.ofNat 48, Char.ofNat 97, Char.ofNat 57, Char.ofNat 50, Char.ofNat 97, Char.ofNat 98, Char.ofNat 57, Char.ofNat 51, Char.ofNat 48, Char.ofNat 55, Char.ofNat 51, Char.ofNat 51, Char.ofNat 54, Char.ofNat 100, Char.ofNat 49, Char.ofNat 51, Char.ofNat 53, Char.ofNat 51, Char.ofNat 57, Char.ofNat 100, Char.ofNat 57, Char.ofNat 55, Char.ofNat 48, Char.ofNat 57, Char.ofNat 99, Char.ofNat 53, Char.ofNat 101, Char.ofNat 51, Char.ofNat 56, Char.ofNat 48, Char.ofNat 98, Char.ofNat 97, Char.ofNat 102, Char.ofNat 53, Char.ofNat 55, Char.ofNat 97, Char.ofNat 99, Char.ofNat 50, Char.ofNat 52, Char.ofNat 51, Char.ofNat 102, Char.ofNat 52, Char.ofNat 51, Char.ofNat 48, Char.ofNat 102, Char.ofNat 51, Char.ofNat 52, Char.ofNat 56, Char.ofNat 52, Char.ofNat 97, Char.ofNat 99])
    activePhase := (String.mk [Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104])
    contractPhase := (String.mk [Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104])
    enabledObligationIds := [(String.mk [Char.ofNat 108, Char.ofNat 101, Char.ofNat 103, Char.ofNat 97, Char.ofNat 99, Char.ofNat 121, Char.ofNat 58, Char.ofNat 48, Char.ofNat 58, Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104, Char.ofNat 58, Char.ofNat 80, Char.ofNat 105, Char.ofNat 99, Char.ofNat 107, Char.ofNat 58, Char.ofNat 104, Char.ofNat 111, Char.ofNat 108, Char.ofNat 100, Char.ofNat 105, Char.ofNat 110, Char.ofNat 103])]
    contractObligationIds := [(String.mk [Char.ofNat 108, Char.ofNat 101, Char.ofNat 103, Char.ofNat 97, Char.ofNat 99, Char.ofNat 121, Char.ofNat 58, Char.ofNat 48, Char.ofNat 58, Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104, Char.ofNat 58, Char.ofNat 80, Char.ofNat 105, Char.ofNat 99, Char.ofNat 107, Char.ofNat 58, Char.ofNat 104, Char.ofNat 111, Char.ofNat 108, Char.ofNat 100, Char.ofNat 105, Char.ofNat 110, Char.ofNat 103])]
    contractTarget := some ((String.mk [Char.ofNat 102, Char.ofNat 111, Char.ofNat 114, Char.ofNat 107, Char.ofNat 95, Char.ofNat 49]))
    obligationTarget := some ((String.mk [Char.ofNat 102, Char.ofNat 111, Char.ofNat 114, Char.ofNat 107, Char.ofNat 95, Char.ofNat 49]))
    contractPart := some ((String.mk [Char.ofNat 104, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100, Char.ofNat 108, Char.ofNat 101]))
    obligationPart := some ((String.mk [Char.ofNat 104, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100, Char.ofNat 108, Char.ofNat 101]))
    contractRegion := none
    obligationRegion := none
    missionIntegrity := true
    contractIntegrity := true
    issuedAtNs := 337569959163298
    deadlineNs := 337609959163298
    nowNs := 337569959163298
    guarantee := Formula.eventually (Formula.atom (String.mk [Char.ofNat 104, Char.ofNat 111, Char.ofNat 108, Char.ofNat 100, Char.ofNat 105, Char.ofNat 110, Char.ofNat 103, Char.ofNat 58, Char.ofNat 102, Char.ofNat 111, Char.ofNat 114, Char.ofNat 107, Char.ofNat 95, Char.ofNat 49]) true) 337609959163298
  }

example : checkSemantic replayRequest = StaticResult.proven := by decide
