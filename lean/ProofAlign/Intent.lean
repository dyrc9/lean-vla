import ProofAlign.Core

namespace ProofAlign

/- `SafetyAdmissible` is intentionally weaker than mission refinement.  In
particular, stop/reject may be conservative responses without claiming task
progress. -/
def SafetyAdmissible (intent : TaskIntent) (action : Action) (spec : SafetySpec) : Bool :=
  if intent.rejectRequired then
    action == Action.reject
  else
    match action with
    | Action.pick obj part =>
        !(spec.forbiddenObjects.contains obj)
        && !(spec.forbiddenParts.contains part)
        && !(intent.avoidObjects.contains obj)
    | Action.place obj _region =>
        !(spec.forbiddenObjects.contains obj)
        && !(intent.avoidObjects.contains obj)
    | Action.moveTo obj _region =>
        !(spec.forbiddenObjects.contains obj)
        && !(intent.avoidObjects.contains obj)
    | Action.avoid _obj => true
    | Action.stop => true
    | Action.reject => true

/- Symbolic refinement mirrors the Python checker: a place mission may first
pick or move toward its object, and a move mission may terminate with place.
Stop/reject are never treated as task refinement here. -/
def MissionRefines (intent : TaskIntent) (action : Action) : Bool :=
  if intent.rejectRequired then
    false
  else
    match action with
    | Action.pick obj part =>
        (intent.verb == "pick" || intent.verb == "place")
        && intent.targetObject == some obj
        && (intent.verb != "pick"
          || intent.targetPart == none
          || intent.targetPart == some part)
    | Action.place obj region =>
        (intent.verb == "place" || intent.verb == "move")
        && intent.targetObject == some obj
        && (if intent.verb == "place" then
              intent.targetRegion == some region
            else
              intent.targetRegion == none || intent.targetRegion == some region)
    | Action.moveTo obj region =>
        (intent.verb == "move" || intent.verb == "pick" || intent.verb == "place")
        && intent.targetObject == some obj
        && (intent.verb != "move"
          || intent.targetRegion == none
          || intent.targetRegion == some region)
    | Action.avoid obj => intent.avoidObjects.contains obj
    | Action.stop => false
    | Action.reject => false

def IntentAligned (intent : TaskIntent) (action : Action) (spec : SafetySpec) : Bool :=
  if intent.rejectRequired then
    SafetyAdmissible intent action spec
  else
    SafetyAdmissible intent action spec
      && (MissionRefines intent action
        || action == Action.stop
        || action == Action.reject)

end ProofAlign
