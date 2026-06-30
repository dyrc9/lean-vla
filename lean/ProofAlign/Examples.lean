import ProofAlign.Safety

namespace ProofAlign

def safeSpec : SafetySpec :=
  { safetyMargin := 20
    forbiddenObjects := ["knife"]
    forbiddenParts := ["blade"]
    protectedObjects := ["human_hand", "obstacle"]
    requireNoCollision := true }

def safeGraspIntent : TaskIntent :=
  { verb := "pick", targetObject := some "mug", targetPart := some "handle" }

def rejectKnifeBladeIntent : TaskIntent :=
  { verb := "reject", rejectRequired := true }

def avoidHandIntent : TaskIntent :=
  { verb := "place", targetObject := some "mug", targetRegion := some "plate", avoidObjects := ["human_hand"] }

def before : WorldState := {}

def afterSafePick : WorldState :=
  { holding := some "mug", humanHandDistance := 100, obstacleDistance := 100 }

def afterCollision : WorldState :=
  { holding := some "mug", collision := true, humanHandDistance := 100, obstacleDistance := 100 }

def safePreCerts : List Certificate :=
  [ { kind := CertKind.objectIdentity, subject := some "mug", confidence := 100 },
    { kind := CertKind.affordance, subject := some "mug", confidence := 100 } ]

def safePostCerts : List Certificate :=
  [ { kind := CertKind.stateTransition, subject := some "mug", confidence := 100 },
    { kind := CertKind.frameCondition, subject := some "mug", confidence := 100 } ]

example : IntentAligned safeGraspIntent (Action.pick "mug" "handle") safeSpec = true := by
  decide

example : IntentAligned safeGraspIntent (Action.pick "knife" "blade") safeSpec = false := by
  decide

example : EffectAligned before (Action.pick "mug" "handle") afterSafePick safeSpec = true := by
  decide

example : EffectAligned before (Action.pick "mug" "handle") afterCollision safeSpec = false := by
  decide

example : DualAligned safeGraspIntent before (Action.pick "mug" "handle") afterSafePick safeSpec = true := by
  decide

example :
    CertifiedDualAligned
      safeGraspIntent
      before
      (Action.pick "mug" "handle")
      afterSafePick
      safeSpec
      safePreCerts
      safePostCerts
      50 = true := by
  decide

example : IntentAligned rejectKnifeBladeIntent (Action.pick "knife" "blade") safeSpec = false := by
  decide

#eval DualAligned safeGraspIntent before (Action.pick "mug" "handle") afterSafePick safeSpec

end ProofAlign
