import ProofAlign.CTDAWire

open ProofAlign.WireV1

def replayRequest : PrefixPrePayload :=
  {
    semanticRequestId := (String.mk [Char.ofNat 115, Char.ofNat 101, Char.ofNat 109, Char.ofNat 97, Char.ofNat 110, Char.ofNat 116, Char.ofNat 105, Char.ofNat 99])
    semanticVerdict := StaticResult.proven
    missionDigest := (String.mk [Char.ofNat 109, Char.ofNat 105, Char.ofNat 115, Char.ofNat 115, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    contractSpecDigest := (String.mk [Char.ofNat 109, Char.ofNat 105, Char.ofNat 115, Char.ofNat 115, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    contractDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 110, Char.ofNat 116, Char.ofNat 114, Char.ofNat 97, Char.ofNat 99, Char.ofNat 116])
    binderVerdict := StaticResult.proven
    stateDigest := (String.mk [Char.ofNat 115, Char.ofNat 116, Char.ofNat 97, Char.ofNat 116, Char.ofNat 101])
    authorizationStateDigest := (String.mk [Char.ofNat 115, Char.ofNat 116, Char.ofNat 97, Char.ofNat 116, Char.ofNat 101])
    monitorDigest := (String.mk [Char.ofNat 109, Char.ofNat 111, Char.ofNat 110, Char.ofNat 105, Char.ofNat 116, Char.ofNat 111, Char.ofNat 114])
    authorizationMonitorDigest := (String.mk [Char.ofNat 109, Char.ofNat 111, Char.ofNat 110, Char.ofNat 105, Char.ofNat 116, Char.ofNat 111, Char.ofNat 114])
    episodeNonce := (String.mk [Char.ofNat 101, Char.ofNat 112, Char.ofNat 105, Char.ofNat 115, Char.ofNat 111, Char.ofNat 100, Char.ofNat 101])
    authorizationNonce := (String.mk [Char.ofNat 101, Char.ofNat 112, Char.ofNat 105, Char.ofNat 115, Char.ofNat 111, Char.ofNat 100, Char.ofNat 101])
    proposalIndex := 0
    authorizationProposalIndex := 0
    monitorLastProposalIndex := (-1)
    proposalDigest := (String.mk [Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 112, Char.ofNat 111, Char.ofNat 115, Char.ofNat 97, Char.ofNat 108])
    authorizationProposalDigest := (String.mk [Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 112, Char.ofNat 111, Char.ofNat 115, Char.ofNat 97, Char.ofNat 108])
    commandDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 109, Char.ofNat 109, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100])
    authorizationCommandDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 109, Char.ofNat 109, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100])
    timeBaseDigest := (String.mk [Char.ofNat 116, Char.ofNat 105, Char.ofNat 109, Char.ofNat 101])
    authorizationTimeBaseDigest := (String.mk [Char.ofNat 111, Char.ofNat 116, Char.ofNat 104, Char.ofNat 101, Char.ofNat 114, Char.ofNat 45, Char.ofNat 116, Char.ofNat 105, Char.ofNat 109, Char.ofNat 101])
    nowNs := 20
    issuedAtNs := 10
    validUntilNs := 50
    durationNs := 20
  }

example : checkPrefixPre replayRequest = StaticResult.refuted := by decide
