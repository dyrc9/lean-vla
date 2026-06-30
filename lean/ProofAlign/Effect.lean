import ProofAlign.Core

namespace ProofAlign

def basicRuntimeSafe (after : WorldState) (spec : SafetySpec) : Bool :=
  (!(spec.requireNoCollision && after.collision)) && respectsDistances after spec

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

end ProofAlign
