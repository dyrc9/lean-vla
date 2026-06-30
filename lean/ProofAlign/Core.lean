namespace ProofAlign

abbrev ObjectId := String
abbrev PartId := String
abbrev RegionId := String

inductive Action where
  | pick : ObjectId -> PartId -> Action
  | place : ObjectId -> RegionId -> Action
  | moveTo : ObjectId -> RegionId -> Action
  | avoid : ObjectId -> Action
  | stop : Action
  | reject : Action
deriving Repr, DecidableEq, BEq

structure TaskIntent where
  verb : String
  targetObject : Option ObjectId := none
  targetPart : Option PartId := none
  targetRegion : Option RegionId := none
  avoidObjects : List ObjectId := []
  rejectRequired : Bool := false
deriving Repr, DecidableEq, BEq

structure SafetySpec where
  safetyMargin : Nat := 20
  forbiddenObjects : List ObjectId := []
  forbiddenParts : List PartId := []
  protectedObjects : List ObjectId := []
  requireNoCollision : Bool := true
deriving Repr, DecidableEq, BEq

structure WorldState where
  holding : Option ObjectId := none
  inRegion : List (ObjectId × RegionId) := []
  collision : Bool := false
  humanHandDistance : Nat := 1000
  obstacleDistance : Nat := 1000
deriving Repr, DecidableEq, BEq

def held (s : WorldState) (obj : ObjectId) : Bool :=
  s.holding == some obj

def objectInRegion (s : WorldState) (obj : ObjectId) (region : RegionId) : Bool :=
  s.inRegion.contains (obj, region)

def respectsDistances (s : WorldState) (spec : SafetySpec) : Bool :=
  s.humanHandDistance >= spec.safetyMargin && s.obstacleDistance >= spec.safetyMargin

end ProofAlign
