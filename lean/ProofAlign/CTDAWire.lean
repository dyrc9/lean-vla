import Std

namespace ProofAlign.WireV1

inductive StaticResult where
  | proven
  | refuted
  | unknown
  | inconsistent
deriving Repr, DecidableEq, BEq

inductive MonitorResult where
  | safePending
  | complete
  | violated
  | unknown
  | inconsistent
deriving Repr, DecidableEq, BEq

inductive Truth where
  | true
  | false
  | unknown
deriving Repr, DecidableEq, BEq

inductive Formula where
  | atom (name : String) (expected : Bool)
  | all (items : List Formula)
  | any (items : List Formula)
  | not (item : Formula)
  | eventually (item : Formula) (deadlineNs : Nat)
deriving Repr

mutual
  def evalFormula (observed : List String) (nowNs : Nat) : Formula → Truth
    | .atom name expected =>
        if observed.contains name then
          if expected then .true else .false
        else if expected then .unknown else .true
    | .all items => evalAll observed nowNs items
    | .any items => evalAny observed nowNs items
    | .not item =>
        match evalFormula observed nowNs item with
        | .true => .false
        | .false => .true
        | .unknown => .unknown
    | .eventually item deadlineNs =>
        match evalFormula observed nowNs item with
        | .true => .true
        | _ => if deadlineNs < nowNs then .false else .unknown

  def evalAll (observed : List String) (nowNs : Nat) : List Formula → Truth
    | [] => .true
    | item :: rest =>
        match evalFormula observed nowNs item with
        | .false => .false
        | .unknown =>
            match evalAll observed nowNs rest with
            | .false => .false
            | _ => .unknown
        | .true => evalAll observed nowNs rest

  def evalAny (observed : List String) (nowNs : Nat) : List Formula → Truth
    | [] => .false
    | item :: rest =>
        match evalFormula observed nowNs item with
        | .true => .true
        | .unknown =>
            match evalAny observed nowNs rest with
            | .true => .true
            | _ => .unknown
        | .false => evalAny observed nowNs rest
end

structure SemanticPayload where
  missionDigest : String
  contractSpecDigest : String
  contractDigest : String
  activePhase : String
  contractPhase : String
  enabledObligationIds : List String
  contractObligationIds : List String
  contractTarget : Option String
  obligationTarget : Option String
  contractPart : Option String
  obligationPart : Option String
  contractRegion : Option String
  obligationRegion : Option String
  missionIntegrity : Bool
  contractIntegrity : Bool
  issuedAtNs : Nat
  deadlineNs : Nat
  nowNs : Nat
  guarantee : Formula
deriving Repr

def checkSemantic (payload : SemanticPayload) : StaticResult :=
  if payload.missionIntegrity
      && payload.contractIntegrity
      && payload.missionDigest == payload.contractSpecDigest
      && payload.activePhase == payload.contractPhase
      && payload.enabledObligationIds == payload.contractObligationIds
      && payload.contractTarget == payload.obligationTarget
      && payload.contractPart == payload.obligationPart
      && payload.contractRegion == payload.obligationRegion
      && payload.issuedAtNs ≤ payload.nowNs
      && payload.nowNs ≤ payload.deadlineNs then
    .proven
  else
    .refuted

structure PrefixPrePayload where
  semanticRequestId : String
  semanticVerdict : StaticResult
  missionDigest : String
  contractSpecDigest : String
  contractDigest : String
  binderVerdict : StaticResult
  stateDigest : String
  authorizationStateDigest : String
  monitorDigest : String
  authorizationMonitorDigest : String
  episodeNonce : String
  authorizationNonce : String
  proposalIndex : Nat
  authorizationProposalIndex : Nat
  monitorLastProposalIndex : Int
  proposalDigest : String
  authorizationProposalDigest : String
  commandDigest : String
  authorizationCommandDigest : String
  timeBaseDigest : String
  authorizationTimeBaseDigest : String
  nowNs : Nat
  issuedAtNs : Nat
  validUntilNs : Nat
  durationNs : Nat
deriving Repr

def checkPrefixPre (payload : PrefixPrePayload) : StaticResult :=
  if payload.semanticVerdict == .proven
      && payload.missionDigest == payload.contractSpecDigest
      && payload.binderVerdict == .proven
      && payload.stateDigest == payload.authorizationStateDigest
      && payload.monitorDigest == payload.authorizationMonitorDigest
      && payload.episodeNonce == payload.authorizationNonce
      && payload.proposalIndex == payload.authorizationProposalIndex
      && payload.monitorLastProposalIndex < Int.ofNat payload.proposalIndex
      && payload.proposalDigest == payload.authorizationProposalDigest
      && payload.commandDigest == payload.authorizationCommandDigest
      && payload.timeBaseDigest == payload.authorizationTimeBaseDigest
      && payload.issuedAtNs ≤ payload.nowNs
      && payload.nowNs + payload.durationNs ≤ payload.validUntilNs then
    .proven
  else
    .refuted

structure ObservedPrefixPayload where
  prefixRequestId : String
  prefixVerdict : StaticResult
  plantVerdict : StaticResult
  authorizationDigest : String
  receiptAuthorizationDigest : String
  episodeNonce : String
  receiptEpisodeNonce : String
  authorizedCommandDigest : String
  dispatchedCommandDigest : String
  receiptCommandDigest : String
  missionTimeBaseDigest : String
  plantTimeBaseDigest : String
  dispatchNs : Nat
  observedNs : Nat
  receiptDigest : String
  plantTraceDigest : String
  eventTraceDigest : String
deriving Repr

def checkObservedPrefix (payload : ObservedPrefixPayload) : StaticResult :=
  if payload.prefixVerdict == .proven
      && payload.plantVerdict == .proven
      && payload.authorizationDigest == payload.receiptAuthorizationDigest
      && payload.episodeNonce == payload.receiptEpisodeNonce
      && payload.authorizedCommandDigest == payload.dispatchedCommandDigest
      && payload.authorizedCommandDigest == payload.receiptCommandDigest
      && payload.missionTimeBaseDigest == payload.plantTimeBaseDigest
      && payload.dispatchNs ≤ payload.observedNs then
    .proven
  else
    .refuted

def strictlyIncreasing : List Nat → Bool
  | [] => true
  | [_] => true
  | first :: second :: rest => first < second && strictlyIncreasing (second :: rest)

structure MonitorPayload where
  observedRequestId : String
  observedVerdict : StaticResult
  missionDigest : String
  contractSpecDigest : String
  episodeNonce : String
  monitorEpisodeNonce : String
  contractDigest : String
  monitorContractDigest : String
  activePhase : String
  monitorPhase : String
  previousMonitorDigest : String
  recordMonitorBeforeDigest : String
  previousLastTimestampNs : Int
  eventTimestampsNs : List Nat
  previousObservedAtoms : List String
  currentObservedAtoms : List String
  guarantee : Formula
  invariant : Formula
  expectedPhase : String
  terminalPhaseEvent : Bool
  completionWitness : Bool
  postEvidence : Bool
  nowNs : Nat
  deadlineNs : Nat
  nextProposalIndex : Nat
  recordProposalIndex : Nat
deriving Repr

def monitorBindingsValid (payload : MonitorPayload) : Bool :=
  payload.observedVerdict == .proven
    && payload.missionDigest == payload.contractSpecDigest
    && payload.episodeNonce == payload.monitorEpisodeNonce
    && payload.contractDigest == payload.monitorContractDigest
    && payload.activePhase == payload.monitorPhase
    && payload.previousMonitorDigest == payload.recordMonitorBeforeDigest
    && payload.nextProposalIndex == payload.recordProposalIndex + 1

def monitorTimestampsValid (payload : MonitorPayload) : Bool :=
  let continuation :=
    match payload.eventTimestampsNs with
    | [] => true
    | first :: _ => payload.previousLastTimestampNs < Int.ofNat first
  continuation && strictlyIncreasing payload.eventTimestampsNs

def checkMonitor (payload : MonitorPayload) : MonitorResult :=
  if !monitorBindingsValid payload then
    .inconsistent
  else if !monitorTimestampsValid payload then
    .inconsistent
  else
    let atoms := payload.previousObservedAtoms ++ payload.currentObservedAtoms
    match evalFormula atoms payload.nowNs payload.invariant with
    | .false => .violated
    | .unknown => .unknown
    | .true =>
        let guarantee := evalFormula atoms payload.nowNs payload.guarantee
        if guarantee == .true
            && payload.terminalPhaseEvent
            && payload.completionWitness
            && payload.postEvidence
            && payload.nowNs ≤ payload.deadlineNs then
          .complete
        else if payload.deadlineNs < payload.nowNs || guarantee == .false then
          .violated
        else
          .safePending

end ProofAlign.WireV1
