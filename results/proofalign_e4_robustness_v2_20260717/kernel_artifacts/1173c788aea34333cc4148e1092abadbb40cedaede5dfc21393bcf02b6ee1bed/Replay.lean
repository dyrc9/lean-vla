import ProofAlign.CTDAWire

open ProofAlign.WireV1

def replayRequest : ObservedPrefixPayload :=
  {
    prefixRequestId := (String.mk [Char.ofNat 112, Char.ofNat 114, Char.ofNat 101, Char.ofNat 102, Char.ofNat 105, Char.ofNat 120])
    prefixVerdict := StaticResult.proven
    plantVerdict := StaticResult.proven
    authorizationDigest := (String.mk [Char.ofNat 97, Char.ofNat 117, Char.ofNat 116, Char.ofNat 104, Char.ofNat 111, Char.ofNat 114, Char.ofNat 105, Char.ofNat 122, Char.ofNat 97, Char.ofNat 116, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    receiptAuthorizationDigest := (String.mk [Char.ofNat 111, Char.ofNat 116, Char.ofNat 104, Char.ofNat 101, Char.ofNat 114, Char.ofNat 45, Char.ofNat 97, Char.ofNat 117, Char.ofNat 116, Char.ofNat 104, Char.ofNat 111, Char.ofNat 114, Char.ofNat 105, Char.ofNat 122, Char.ofNat 97, Char.ofNat 116, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    episodeNonce := (String.mk [Char.ofNat 101, Char.ofNat 112, Char.ofNat 105, Char.ofNat 115, Char.ofNat 111, Char.ofNat 100, Char.ofNat 101])
    receiptEpisodeNonce := (String.mk [Char.ofNat 101, Char.ofNat 112, Char.ofNat 105, Char.ofNat 115, Char.ofNat 111, Char.ofNat 100, Char.ofNat 101])
    authorizedCommandDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 109, Char.ofNat 109, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100])
    dispatchedCommandDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 109, Char.ofNat 109, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100])
    receiptCommandDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 109, Char.ofNat 109, Char.ofNat 97, Char.ofNat 110, Char.ofNat 100])
    missionTimeBaseDigest := (String.mk [Char.ofNat 116, Char.ofNat 105, Char.ofNat 109, Char.ofNat 101])
    plantTimeBaseDigest := (String.mk [Char.ofNat 116, Char.ofNat 105, Char.ofNat 109, Char.ofNat 101])
    dispatchNs := 30
    observedNs := 40
    receiptDigest := (String.mk [Char.ofNat 114, Char.ofNat 101, Char.ofNat 99, Char.ofNat 101, Char.ofNat 105, Char.ofNat 112, Char.ofNat 116])
    plantTraceDigest := (String.mk [Char.ofNat 112, Char.ofNat 108, Char.ofNat 97, Char.ofNat 110, Char.ofNat 116])
    eventTraceDigest := (String.mk [Char.ofNat 101, Char.ofNat 118, Char.ofNat 101, Char.ofNat 110, Char.ofNat 116, Char.ofNat 115])
  }

example : checkObservedPrefix replayRequest = StaticResult.refuted := by decide
