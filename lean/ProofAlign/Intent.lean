import ProofAlign.Core

namespace ProofAlign

def IntentAligned (intent : TaskIntent) (action : Action) (spec : SafetySpec) : Bool :=
  if intent.rejectRequired then
    action == Action.reject
  else
    match action with
    | Action.pick obj part =>
        intent.verb == "pick"
        && intent.targetObject == some obj
        && (intent.targetPart == none || intent.targetPart == some part)
        && !(spec.forbiddenObjects.contains obj)
        && !(spec.forbiddenParts.contains part)
        && !(intent.avoidObjects.contains obj)
    | Action.place obj region =>
        intent.verb == "place"
        && intent.targetObject == some obj
        && intent.targetRegion == some region
        && !(spec.forbiddenObjects.contains obj)
        && !(intent.avoidObjects.contains obj)
    | Action.moveTo obj region =>
        intent.verb == "move"
        && intent.targetObject == some obj
        && (intent.targetRegion == none || intent.targetRegion == some region)
        && !(spec.forbiddenObjects.contains obj)
        && !(intent.avoidObjects.contains obj)
    | Action.avoid obj =>
        intent.avoidObjects.contains obj
    | Action.stop => true
    | Action.reject => true

end ProofAlign
