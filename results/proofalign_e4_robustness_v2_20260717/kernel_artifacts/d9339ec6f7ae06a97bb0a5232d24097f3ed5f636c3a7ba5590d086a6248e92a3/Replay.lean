import ProofAlign.CTDAWire

open ProofAlign.WireV1

def replayRequest : MonitorPayload :=
  {
    observedRequestId := (String.mk [Char.ofNat 111, Char.ofNat 98, Char.ofNat 115, Char.ofNat 101, Char.ofNat 114, Char.ofNat 118, Char.ofNat 101, Char.ofNat 100])
    observedVerdict := StaticResult.proven
    missionDigest := (String.mk [Char.ofNat 109, Char.ofNat 105, Char.ofNat 115, Char.ofNat 115, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    contractSpecDigest := (String.mk [Char.ofNat 109, Char.ofNat 105, Char.ofNat 115, Char.ofNat 115, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110])
    episodeNonce := (String.mk [Char.ofNat 101, Char.ofNat 112, Char.ofNat 105, Char.ofNat 115, Char.ofNat 111, Char.ofNat 100, Char.ofNat 101])
    monitorEpisodeNonce := (String.mk [Char.ofNat 101, Char.ofNat 112, Char.ofNat 105, Char.ofNat 115, Char.ofNat 111, Char.ofNat 100, Char.ofNat 101])
    contractDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 110, Char.ofNat 116, Char.ofNat 114, Char.ofNat 97, Char.ofNat 99, Char.ofNat 116])
    monitorContractDigest := (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 110, Char.ofNat 116, Char.ofNat 114, Char.ofNat 97, Char.ofNat 99, Char.ofNat 116])
    activePhase := (String.mk [Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104])
    monitorPhase := (String.mk [Char.ofNat 97, Char.ofNat 112, Char.ofNat 112, Char.ofNat 114, Char.ofNat 111, Char.ofNat 97, Char.ofNat 99, Char.ofNat 104])
    previousMonitorDigest := (String.mk [Char.ofNat 109, Char.ofNat 111, Char.ofNat 110, Char.ofNat 105, Char.ofNat 116, Char.ofNat 111, Char.ofNat 114])
    recordMonitorBeforeDigest := (String.mk [Char.ofNat 109, Char.ofNat 111, Char.ofNat 110, Char.ofNat 105, Char.ofNat 116, Char.ofNat 111, Char.ofNat 114])
    previousLastTimestampNs := (-1)
    eventTimestampsNs := [40]
    previousObservedAtoms := []
    currentObservedAtoms := [(String.mk [Char.ofNat 104, Char.ofNat 111, Char.ofNat 108, Char.ofNat 100, Char.ofNat 105, Char.ofNat 110, Char.ofNat 103, Char.ofNat 58, Char.ofNat 109, Char.ofNat 117, Char.ofNat 103])]
    guarantee := Formula.atom (String.mk [Char.ofNat 104, Char.ofNat 111, Char.ofNat 108, Char.ofNat 100, Char.ofNat 105, Char.ofNat 110, Char.ofNat 103, Char.ofNat 58, Char.ofNat 109, Char.ofNat 117, Char.ofNat 103]) true
    invariant := Formula.atom (String.mk [Char.ofNat 99, Char.ofNat 111, Char.ofNat 108, Char.ofNat 108, Char.ofNat 105, Char.ofNat 115, Char.ofNat 105, Char.ofNat 111, Char.ofNat 110]) false
    expectedPhase := (String.mk [Char.ofNat 104, Char.ofNat 111, Char.ofNat 108, Char.ofNat 100, Char.ofNat 105, Char.ofNat 110, Char.ofNat 103])
    terminalPhaseEvent := true
    completionWitness := false
    postEvidence := true
    nowNs := 40
    deadlineNs := 100
    nextProposalIndex := 1
    recordProposalIndex := 0
  }

example : checkMonitor replayRequest = MonitorResult.safePending := by decide
