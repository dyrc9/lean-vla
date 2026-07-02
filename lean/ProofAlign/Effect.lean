import ProofAlign.Core

namespace ProofAlign

def basicRuntimeSafe (after : WorldState) (spec : SafetySpec) : Bool :=
  (!(spec.requireNoCollision && after.collision)) && respectsDistances after spec

def ChunkRuntimeSafe (summary : TraceSummary) (spec : SafetySpec) : Bool :=
  !(summary.collision || summary.cost)
  && traceRespectsDistances summary spec
  && !summary.protectedObjectMoved

def actionTarget (action : Action) : Option ObjectId :=
  match action with
  | Action.pick obj _part => some obj
  | Action.place obj _region => some obj
  | Action.moveTo obj _region => some obj
  | Action.avoid obj => some obj
  | Action.stop => none
  | Action.reject => none

def objectRegionFacts (state : WorldState) (obj : ObjectId) : List RegionId :=
  state.inRegion.foldr
    (fun fact acc =>
      if fact.fst == obj then fact.snd :: acc else acc)
    []

def objectFrameHolds (before after : WorldState) (obj : ObjectId) : Bool :=
  (objectRegionFacts before obj == objectRegionFacts after obj)
  && (!(before.holding == some obj) || after.holding == some obj)
  && (!(after.holding == some obj) || before.holding == some obj)

def objectsFrameHold (before after : WorldState) (objects : List ObjectId) (target : Option ObjectId) : Bool :=
  objects.all (fun obj =>
    if target == some obj then true else objectFrameHolds before after obj)

def FrameConditionHolds
    (before after : WorldState)
    (action : Action)
    (spec : SafetySpec) : Bool :=
  objectsFrameHold before after (spec.forbiddenObjects ++ spec.protectedObjects) (actionTarget action)

def EffectAligned (_before : WorldState) (action : Action) (after : WorldState) (spec : SafetySpec) : Bool :=
  basicRuntimeSafe after spec
  &&
  match action with
  | Action.pick obj _part => held after obj
  | Action.place obj region => after.holding == none && objectInRegion after obj region
  | Action.moveTo _obj _region => true
  | Action.avoid obj => !(after.holding == some obj)
  | Action.stop => true
  | Action.reject => true

def ChunkEffectAligned
    (before : WorldState)
    (action : Action)
    (after : WorldState)
    (summary : TraceSummary)
    (spec : SafetySpec) : Bool :=
  ChunkRuntimeSafe summary spec
  && FrameConditionHolds before after action spec
  &&
  match action with
  | Action.pick obj _part => held after obj && summary.objectBecameHeld
  | Action.place obj region => after.holding == none && objectInRegion after obj region && summary.objectReleased
  | Action.moveTo _obj _region => true
  | Action.avoid obj => !(after.holding == some obj) && !(summary.movedObjects.contains obj)
  | Action.stop => true
  | Action.reject => true

end ProofAlign
