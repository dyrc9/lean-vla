import ProofAlign.CTDA

namespace ProofAlign

def ctdaTimeBase : TimeBase :=
  { digest := "timebase-v1"
    clockId := "sim-monotonic"
    nanosecondsPerTick := 1000000
    controlPeriod := ⟨20⟩
    maxSamplingJitter := ⟨2⟩
    maxMonitorLatency := ⟨5⟩ }

def pickGuarantee : TraceFormula :=
  .eventuallyWithin ⟨50⟩ (.atom (.holding "mug"))

def placeGoal : TraceFormula :=
  .atom (.inRegion "mug" "plate")

def placeAutomaton : TaskAutomaton :=
  { initialPhase := "approach"
    terminalPhases := ["released-stable"]
    transitions :=
      [ { source := "approach", skill := .pick, destination := "holding" },
        { source := "holding", skill := .transport, destination := "at-target" },
        { source := "at-target", skill := .place, destination := "released-stable" } ] }

def placeMission : MissionSpec :=
  { specId := "mission-place-mug"
    specDigest := "spec-digest-v2"
    authority :=
      { authorityId := "libero-manifest"
        sourceDigest := "manifest-digest"
        version := "2"
        authenticated := true }
    instructionDigest := "instruction-digest"
    goal := placeGoal
    hardInvariants := [.always (.atom .noBadContact)]
    taskAutomaton := placeAutomaton
    phaseObligations :=
      [ { phase := "holding"
          obligations := [pickGuarantee]
          terminalEvent := .holding "mug"
          requiredPart := some "handle" },
        { phase := "at-target"
          obligations := [.eventuallyWithin ⟨80⟩ (.atom (.inRegion "mug" "plate"))]
          terminalEvent := .inRegion "mug" "plate"
          requiredPart := none },
        { phase := "released-stable"
          obligations := [placeGoal]
          terminalEvent := .inRegion "mug" "plate"
          requiredPart := none } ]
    objectRoles :=
      [ { objectId := "mug"
          ontologyClass := "container"
          registryDigest := "registry-v1"
          allowedParts := ["handle"] },
        { objectId := "plate"
          ontologyClass := "support"
          registryDigest := "registry-v1"
          allowedParts := [] },
        { objectId := "human_hand"
          ontologyClass := "protected"
          registryDigest := "registry-v1"
          allowedParts := [] } ]
    defaultMustPreserve := ["human_hand"]
    requiredEvidence := ["authority"]
    timeBase := ctdaTimeBase }

def pickContract : SemanticSkillContract :=
  { contractId := "contract-pick-mug"
    contractDigest := "contract-digest-pick"
    specId := placeMission.specId
    specDigest := placeMission.specDigest
    phaseBefore := "approach"
    expectedNextPhase := "holding"
    skill := .pick
    target := some "mug"
    part := some "handle"
    issuedAt := ⟨0⟩
    deadline := ⟨⟨100⟩⟩
    guards := [.atom .collisionFree]
    guarantee := [pickGuarantee]
    advancesObligations := [pickGuarantee]
    terminalEvent := .holding "mug"
    mayModify := ["mug"]
    mustPreserve := ["human_hand"]
    fallbackClass := .retreat
    fallbackId := "retreat-v1"
    semanticPreRequirements := ["grounding"]
    physicalPreRequirements := ["tube", "fallback"]
    runtimeRequirements := ["observer", "timing"]
    postRequirements := ["grasp-state"] }

def semanticExampleRequest : SemanticCheckRequest :=
  { mission := placeMission
    phase := "approach"
    state := { collision := false }
    currentTime := ⟨0⟩
    contract := pickContract
    evidence := ["authority", "grounding"] }

example : GuaranteeRefinesMission placeMission pickContract = true := by decide

example : SemanticTemporalRefines semanticExampleRequest := by decide

example :
    checkSemantic semanticExampleRequest = .proven "semantic:contract-digest-pick" := by
  decide

def safeTube : ReachableTube :=
  { tubeDigest := "tube-digest"
    authorizedCommandDigest := "filtered-command"
    dynamicsModelDigest := "kinematic-model-v2"
    horizon := ⟨10⟩
    fallbackId := "retreat-v1"
    fallbackWitnessRef := "fallback-witness"
    slices :=
      [ { offset := ⟨0⟩
          validUntil := ⟨5⟩
          invariantMargin := 12
          safeThroughout := true
          recoverableThroughout := true
          safetyWitnessRef := "tube-safe-0-5"
          recoveryWitnessRef := "recoverable-0-5" },
        { offset := ⟨5⟩
          validUntil := ⟨10⟩
          invariantMargin := 4
          safeThroughout := true
          recoverableThroughout := true
          safetyWitnessRef := "tube-safe-5-10"
          recoveryWitnessRef := "recoverable-5-10" } ] }

def safeCandidate : PrefixCandidate :=
  { proposal :=
      { contractId := pickContract.contractId
        contractDigest := pickContract.contractDigest
        proposalIndex := 1
        proposalDigest := "proposal-1"
        proposedHorizon := ⟨16⟩
        issuedAt := ⟨0⟩ }
    authorization :=
      { authorizationDigest := "authorization-1"
        contractId := pickContract.contractId
        contractDigest := pickContract.contractDigest
        semanticWitnessRef := "semantic:contract-digest-pick"
        specDigest := placeMission.specDigest
        stateDigest := "state-0"
        monitorStateDigest := "monitor-0"
        proposalIndex := 1
        proposalDigest := "proposal-1"
        authorizedCommandDigest := "filtered-command"
        filterPolicyDigest := "filter-v2"
        dynamicsModelDigest := "kinematic-model-v2"
        timeBaseDigest := ctdaTimeBase.digest
        tubeDigest := "tube-digest"
        maxAuthorizedDuration := ⟨10⟩
        fallbackId := "retreat-v1"
        fallbackWitnessRef := "fallback-witness"
        issuedAt := ⟨1⟩
        validUntil := ⟨20⟩ }
    tube := safeTube
    preEvidence :=
      { proposalDigest := "proposal-1"
        authorizedCommandDigest := "filtered-command"
        filterPolicyDigest := "filter-v2"
        dynamicsModelDigest := "kinematic-model-v2"
        tubeDigest := "tube-digest"
        fallbackId := "retreat-v1"
        fallbackWitnessRef := "fallback-witness"
        worstCaseSwitchLatency := ⟨4⟩
        maxCertifiedSwitchLatency := ⟨5⟩
        proposalEvidence :=
          { kind := .proposalAdmissibility
            contractDigest := pickContract.contractDigest
            proposalDigest := "proposal-1"
            authorizedCommandDigest := ""
            policyDigest := ""
            producerId := "proposal-contract-checker"
            producerVersion := "1"
            witnessRef := "proposal-contract-witness"
            verified := true }
        filterEvidence :=
          { kind := .filterPreservation
            contractDigest := pickContract.contractDigest
            proposalDigest := "proposal-1"
            authorizedCommandDigest := "filtered-command"
            policyDigest := "filter-v2"
            producerId := "filter-envelope-checker"
            producerVersion := "1"
            witnessRef := "filter-envelope-witness"
            verified := true }
        coveredRequirements := ["tube", "fallback"]
      } }

def monitorBeforePick : MonitorState :=
  { monitorStateDigest := "monitor-0"
    contractId := pickContract.contractId
    specDigest := placeMission.specDigest
    phase := "approach"
    stateDigest := "state-0"
    nextProposalIndex := 1
    pending := pickContract.guarantee
    hasPending := true
    lastEventTimestamp := ⟨0⟩ }

def prefixExampleRequest : PrefixPreCheckRequest :=
  { mission := placeMission
    state := { collision := false }
    stateDigest := "state-0"
    monitorState := monitorBeforePick
    currentTime := ⟨1⟩
    previousProposalIndex := some 0
    contract := pickContract
    semanticRequest := semanticExampleRequest
    semanticWitness := "semantic:contract-digest-pick"
    candidate := safeCandidate }

example : PrefixPreCertified prefixExampleRequest := by decide

example :
    checkPrefixPre prefixExampleRequest = .proven "prefix-pre:authorization-1" := by
  decide

def completedPlantTrace : PlantTrace :=
  [ { timestamp := ⟨2⟩
      sampleDigest := "sample-0"
      stateDigest := "state-mid"
      authorizationDigest := "authorization-1"
      executedCommandDigest := "filtered-command"
      humanClearance := ⟨20, 22⟩
      obstacleClearance := ⟨18, 20⟩
      force := ⟨0, 2⟩
      hardInvariantsHold := true
      withinReachableTube := true
      modelAssumptionsHold := true },
    { timestamp := ⟨10⟩
      sampleDigest := "sample-1"
      stateDigest := "state-1"
      authorizationDigest := "authorization-1"
      executedCommandDigest := "filtered-command"
      humanClearance := ⟨19, 21⟩
      obstacleClearance := ⟨17, 19⟩
      force := ⟨1, 3⟩
      hardInvariantsHold := true
      withinReachableTube := true
      modelAssumptionsHold := true } ]

def completedPickTrace : SymbolicEventTrace :=
  [ { timestamp := ⟨2⟩
      facts := [.noBadContact]
      sourcePlantSampleDigest := "sample-0" },
    { timestamp := ⟨10⟩
      facts := [.noBadContact, .holding "mug"]
      sourcePlantSampleDigest := "sample-1" } ]

def completedRecord : PrefixExecutionRecord :=
  { recordDigest := "record-1"
    candidate := safeCandidate
    receipt :=
      { authorizationDigest := "authorization-1"
        authorizedCommandDigest := "filtered-command"
        executedCommandDigest := "filtered-command"
        executedAt := ⟨1⟩
        withinAuthorizedError := true
        actuatorEvidence := "actuator-receipt"
        errorBoundWitness := "exact-command" }
    plantTrace := completedPlantTrace
    plantTraceDigest := "plant-trace-1"
    plantTimeBaseDigest := ctdaTimeBase.digest
    eventTrace := completedPickTrace
    symbolicEventTraceDigest := "event-trace-1"
    runtimeEvidence :=
      { authorizationDigest := "authorization-1"
        executedCommandDigest := "filtered-command"
        plantTraceDigest := "plant-trace-1"
        tubeDigest := "tube-digest"
        monitorBeforeDigest := "monitor-0"
        allSamplesWithinTube := true
        allHardInvariantsHold := true
        allModelAssumptionsHold := true
        observerWitness := "observer-witness"
        timingWitness := "timing-witness"
        coveredRequirements := ["observer", "timing"] }
    abstractionEvidence :=
      { plantTraceDigest := "plant-trace-1"
        symbolicEventTraceDigest := "event-trace-1"
        timeBaseDigest := ctdaTimeBase.digest
        abstractorId := "libero-state-abstractor"
        abstractorVersion := "2"
        witnessRef := "abstraction-witness"
        verified := true
        links :=
          [ { frameIndex := 0
              factIndex := 0
              sampleDigest := "sample-0"
              atom := .noBadContact
              derivationDigest := "derive-no-contact-0"
              witnessRef := "fact-witness-0-0"
              verified := true },
            { frameIndex := 1
              factIndex := 0
              sampleDigest := "sample-1"
              atom := .noBadContact
              derivationDigest := "derive-no-contact-1"
              witnessRef := "fact-witness-1-0"
              verified := true },
            { frameIndex := 1
              factIndex := 1
              sampleDigest := "sample-1"
              atom := .holding "mug"
              derivationDigest := "derive-holding-1"
              witnessRef := "fact-witness-1-1"
              verified := true } ] }
    monitorBeforeDigest := "monitor-0"
    monitorAfterDigest := "monitor-1" }

def observedExampleRequest : ObservedEvidenceCheckRequest :=
  { prefixRequest := prefixExampleRequest
    prefixWitness := "prefix-pre:authorization-1"
    record := completedRecord }

example : ObservedPrefixEvidenceValid observedExampleRequest := by decide

example :
    checkObservedEvidence observedExampleRequest = .proven "observed:record-1" := by
  decide

def completeMonitorRequest : MonitorCheckRequest :=
  { observed := observedExampleRequest
    observedWitness := "observed:record-1"
    priorState := monitorBeforePick
    currentStateDigest := "state-1"
    nextProposalIndex := 2
    currentTime := ⟨10⟩
    postEvidence :=
      { evidenceDigest := "post-evidence-1"
        contractDigest := pickContract.contractDigest
        recordDigest := "record-1"
        finalStateDigest := "state-1"
        terminalFrameSourceDigest := "sample-1"
        terminalFrameTimestamp := ⟨10⟩
        monitorAfterDigest := "monitor-1"
        producerId := "grasp-state-checker"
        producerVersion := "1"
        witnessRef := "grasp-state-witness"
        verified := true
        coveredRequirements := ["grasp-state"] } }

example :
    monitorStep completeMonitorRequest =
      .complete
        "complete:contract-digest-pick:record-1:post-evidence-1:monitor-1" := by
  decide

example : CompletedTraceConforms completeMonitorRequest := by
  apply monitor_complete_sound completeMonitorRequest
    "complete:contract-digest-pick:record-1:post-evidence-1:monitor-1"
  decide

/-! ## Regression examples for previously fail-open or overclaiming paths -/

def wrongMissionContract : SemanticSkillContract :=
  { pickContract with
    contractDigest := "contract-wrong-spec"
    specDigest := "another-spec" }

def wrongMissionSemanticRequest : SemanticCheckRequest :=
  { semanticExampleRequest with contract := wrongMissionContract }

example :
    checkSemantic wrongMissionSemanticRequest =
      .refuted ["semantic-temporal mission refinement failed"] := by
  decide

def wrongSemanticWitnessPrefix : PrefixPreCheckRequest :=
  { prefixExampleRequest with semanticWitness := "semantic:wrong" }

example :
    checkPrefixPre wrongSemanticWitnessPrefix =
      .refuted ["semantic witness, prefix authorization, or reachable-tube evidence failed"] := by
  decide

def latePrefixRequest : PrefixPreCheckRequest :=
  { prefixExampleRequest with currentTime := ⟨11⟩ }

example :
    checkPrefixPre latePrefixRequest =
      .refuted ["semantic witness, prefix authorization, or reachable-tube evidence failed"] := by
  decide

def wrongProposalEvidenceCandidate : PrefixCandidate :=
  { safeCandidate with
    preEvidence :=
      { safeCandidate.preEvidence with
        proposalEvidence :=
          { safeCandidate.preEvidence.proposalEvidence with
            proposalDigest := "another-proposal" } } }

def wrongProposalEvidencePrefix : PrefixPreCheckRequest :=
  { prefixExampleRequest with candidate := wrongProposalEvidenceCandidate }

example :
    checkPrefixPre wrongProposalEvidencePrefix =
      .refuted ["semantic witness, prefix authorization, or reachable-tube evidence failed"] := by
  decide

def wrongFilterEvidenceCandidate : PrefixCandidate :=
  { safeCandidate with
    preEvidence :=
      { safeCandidate.preEvidence with
        filterEvidence :=
          { safeCandidate.preEvidence.filterEvidence with
            authorizedCommandDigest := "another-command" } } }

def wrongFilterEvidencePrefix : PrefixPreCheckRequest :=
  { prefixExampleRequest with candidate := wrongFilterEvidenceCandidate }

example :
    checkPrefixPre wrongFilterEvidencePrefix =
      .refuted ["semantic witness, prefix authorization, or reachable-tube evidence failed"] := by
  decide

def badPartContract : SemanticSkillContract :=
  { pickContract with
    contractDigest := "contract-bad-part"
    part := some "blade" }

def badPartSemanticRequest : SemanticCheckRequest :=
  { semanticExampleRequest with contract := badPartContract }

example :
    checkSemantic badPartSemanticRequest =
      .refuted ["semantic-temporal mission refinement failed"] := by
  decide

def sparseTube : ReachableTube :=
  { safeTube with
    tubeDigest := "sparse-tube"
    slices :=
      [ { offset := ⟨0⟩
          validUntil := ⟨1⟩
          invariantMargin := 10
          safeThroughout := true
          recoverableThroughout := true
          safetyWitnessRef := "only-first-tick"
          recoveryWitnessRef := "only-first-cut" } ] }

example :
    tubeSafeAndRecoverableFor sparseTube ⟨10⟩
      "retreat-v1" "fallback-witness" = false := by
  decide

def unauthorizedRecord : PrefixExecutionRecord :=
  { completedRecord with
    recordDigest := "record-unauthorized"
    receipt :=
      { completedRecord.receipt with
        executedCommandDigest := "different-command"
        withinAuthorizedError := false
        errorBoundWitness := "" } }

def unauthorizedObservedRequest : ObservedEvidenceCheckRequest :=
  { observedExampleRequest with record := unauthorizedRecord }

example :
    checkObservedEvidence unauthorizedObservedRequest =
      .refuted ["execution receipt, authorization, tube, monitor, or trace provenance failed"] := by
  decide

def lateDispatchRecord : PrefixExecutionRecord :=
  { completedRecord with
    recordDigest := "record-late-dispatch"
    receipt := { completedRecord.receipt with executedAt := ⟨11⟩ }
    monitorAfterDigest := "monitor-late-dispatch" }

def lateDispatchObservedRequest : ObservedEvidenceCheckRequest :=
  { observedExampleRequest with record := lateDispatchRecord }

example :
    checkObservedEvidence lateDispatchObservedRequest =
      .refuted ["execution receipt, authorization, tube, monitor, or trace provenance failed"] := by
  decide

def forgedFactRecord : PrefixExecutionRecord :=
  { completedRecord with
    recordDigest := "record-forged-fact"
    eventTrace :=
      [ { timestamp := ⟨2⟩
          facts := [.noBadContact]
          sourcePlantSampleDigest := "sample-0" },
        { timestamp := ⟨10⟩
          facts := [.noBadContact, .holding "mug", .goalReached]
          sourcePlantSampleDigest := "sample-1" } ]
    symbolicEventTraceDigest := "event-trace-forged-fact"
    abstractionEvidence :=
      { completedRecord.abstractionEvidence with
        symbolicEventTraceDigest := "event-trace-forged-fact" }
    monitorAfterDigest := "monitor-forged-fact" }

def forgedFactObservedRequest : ObservedEvidenceCheckRequest :=
  { observedExampleRequest with record := forgedFactRecord }

example :
    checkObservedEvidence forgedFactObservedRequest =
      .refuted ["execution receipt, authorization, tube, monitor, or trace provenance failed"] := by
  decide

example :
    evalTraceFormulaPartial ⟨22⟩ [] 0 false (.neg (.atom .goalReached)) = .pending := by
  decide

def sparseStableTrace : SymbolicEventTrace :=
  [ { timestamp := ⟨0⟩
      facts := [.stable "mug"]
      sourcePlantSampleDigest := "sample-0" },
    { timestamp := ⟨100⟩
      facts := [.noBadContact]
      sourcePlantSampleDigest := "sample-1" } ]

example :
    evalTraceFormulaPartial ⟨22⟩ sparseStableTrace 0 true
      (.stableFor ⟨50⟩ (.atom (.stable "mug"))) = .pending := by
  decide

def lostTerminalTrace : SymbolicEventTrace :=
  [ { timestamp := ⟨2⟩
      facts := [.noBadContact, .holding "mug"]
      sourcePlantSampleDigest := "sample-0" },
    { timestamp := ⟨10⟩
      facts := [.noBadContact]
      sourcePlantSampleDigest := "sample-1" } ]

def lostTerminalRecord : PrefixExecutionRecord :=
  { completedRecord with
    recordDigest := "record-lost-terminal"
    eventTrace := lostTerminalTrace
    symbolicEventTraceDigest := "event-trace-lost-terminal"
    abstractionEvidence :=
      { completedRecord.abstractionEvidence with
        symbolicEventTraceDigest := "event-trace-lost-terminal"
        links :=
          [ { frameIndex := 0
              factIndex := 0
              sampleDigest := "sample-0"
              atom := .noBadContact
              derivationDigest := "derive-no-contact-0"
              witnessRef := "fact-witness-lost-0-0"
              verified := true },
            { frameIndex := 0
              factIndex := 1
              sampleDigest := "sample-0"
              atom := .holding "mug"
              derivationDigest := "derive-holding-0"
              witnessRef := "fact-witness-lost-0-1"
              verified := true },
            { frameIndex := 1
              factIndex := 0
              sampleDigest := "sample-1"
              atom := .noBadContact
              derivationDigest := "derive-no-contact-1"
              witnessRef := "fact-witness-lost-1-0"
              verified := true } ] }
    monitorAfterDigest := "monitor-lost-terminal" }

def lostTerminalObservedRequest : ObservedEvidenceCheckRequest :=
  { observedExampleRequest with record := lostTerminalRecord }

example : ObservedPrefixEvidenceValid lostTerminalObservedRequest := by decide

def lostTerminalMonitorRequest : MonitorCheckRequest :=
  { completeMonitorRequest with
    observed := lostTerminalObservedRequest
    observedWitness := "observed:record-lost-terminal" }

example :
    monitorStep lostTerminalMonitorRequest =
      .safePending (pendingMonitorState lostTerminalMonitorRequest) := by
  decide

def emptyEventRecord : PrefixExecutionRecord :=
  { completedRecord with
    recordDigest := "record-empty-events"
    eventTrace := []
    symbolicEventTraceDigest := "event-trace-empty"
    abstractionEvidence :=
      { completedRecord.abstractionEvidence with
        symbolicEventTraceDigest := "event-trace-empty"
        witnessRef := "empty-abstraction-witness"
        links := [] }
    monitorAfterDigest := "monitor-empty-events" }

def emptyObservedRequest : ObservedEvidenceCheckRequest :=
  { observedExampleRequest with
    record := emptyEventRecord }

def emptyMonitorRequest : MonitorCheckRequest :=
  { completeMonitorRequest with
    observed := emptyObservedRequest
    observedWitness := "observed:record-empty-events" }

example :
    monitorStep emptyMonitorRequest =
      .safePending (pendingMonitorState emptyMonitorRequest) := by
  decide

def expiredMonitorRequest : MonitorCheckRequest :=
  { completeMonitorRequest with currentTime := ⟨101⟩ }

example :
    monitorStep expiredMonitorRequest =
      .violated ["contract deadline expired before completion was accepted"] := by
  decide

def missingPostMonitorRequest : MonitorCheckRequest :=
  { completeMonitorRequest with
    postEvidence :=
      { completeMonitorRequest.postEvidence with
        evidenceDigest := "post-evidence-missing"
        coveredRequirements := [] } }

example :
    monitorStep missingPostMonitorRequest =
      .unknown ["required post-condition evidence is missing"] := by
  decide

def wrongPostBindingMonitorRequest : MonitorCheckRequest :=
  { completeMonitorRequest with
    postEvidence :=
      { completeMonitorRequest.postEvidence with
        evidenceDigest := "post-evidence-wrong-state"
        finalStateDigest := "another-state" } }

example :
    monitorStep wrongPostBindingMonitorRequest =
      .unknown ["required post-condition evidence is missing"] := by
  decide

end ProofAlign
