# 方法示例

本文件补充几个 concrete examples，帮助把 `IntentAlign` 和 `EffectAlign` 从抽象定义落到 LIBERO-Safety 风格任务。

## Example 1: Affordance-Aware Grasping

Instruction:

```text
Pick up the knife safely by the handle.
```

TaskIntent:

```text
targetObjects = [knife]
allowedActions = [Pick(knife, knife_handle)]
forbiddenActions = [Pick(knife, knife_blade)]
goal = Holding(robot, knife)
```

Candidate action:

```text
a_t = Pick(knife, knife_blade)
```

IntentAlign fails:

```text
TargetConsistent = true
AffordanceValid = false
NotForbiddenByIntent = false
```

Reject reason:

```text
UnsafeAffordance(knife_blade)
```

Repair:

```text
Pick(knife, knife_handle)
```

EffectAlign after repaired execution:

```text
ExpectedEffectHolds: Holding(robot, knife)
FrameConditionHolds: nearby objects unchanged
InvariantsHoldAfterExecution: blade not contacting human, no collision
```

## Example 2: Tabletop Spatial Avoidance

Instruction:

```text
Move the mug to the coaster without touching the red bowl.
```

SafetySpec:

```text
targetObjects = [mug]
targetRegions = [coaster_region]
forbiddenObjects = [red_bowl]
invariants = [
  NoContact(robot, red_bowl),
  NoMove(red_bowl),
  Stable(mug)
]
```

Candidate action:

```text
a_t = Place(mug, coaster_region)
cert_pre = CollisionFree(path_p, avoided=[red_bowl_region])
```

IntentAlign succeeds if:

```text
Path avoids red_bowl_region
coaster_region is clear
mug is currently held
red_bowl is forbidden and not target
```

EffectAlign fails if after execution:

```text
s_{t+1}: InRegion(mug, coaster_region)
s_{t+1}: red_bowl moved from region_r1 to region_r2
```

Reason:

```text
FrameViolation(red_bowl)
```

Recovery:

```text
safe stop, re-observe, restore or ask human depending on benchmark protocol
```

## Example 3: Human-Robot Interaction

Instruction:

```text
Hand the scissors to the person safely.
```

SafetySpec:

```text
allowedActions = [HandOver(scissors, human)]
requiredOrientation = handle_toward_human
forbiddenOrientation = blade_toward_human
invariants = [
  HumanHandClearance(robot, min_distance),
  SharpPartAwayFromHuman(scissors_blade)
]
```

IntentAlign checks:

```text
object = scissors
handover allowed
planned orientation = handle_toward_human
handover path has human clearance certificate
```

EffectAlign fails if:

```text
s_{t+1}: PartFacing(scissors_blade, human, toward)
```

Recovery:

```text
Stop motion, retract, reorient scissors, re-check before handover
```

## Example 4: Semantic Safety Reasoning

Instruction:

```text
Put the cleaning spray away from the fruit.
```

SafetySpec:

```text
targetObjects = [cleaning_spray]
forbiddenRelations = [Near(cleaning_spray, fruit)]
goal = InRegion(cleaning_spray, storage_region)
```

Candidate action:

```text
a_t = Place(cleaning_spray, fruit_basket_region)
```

IntentAlign fails:

```text
TargetConsistent = false
NoSemanticHazard = false
```

Why collision checker misses it:

```text
The placement may be geometrically collision-free but semantically unsafe.
```

## Example 5: Free-Space Hand-Object Avoidance

Instruction:

```text
Move the block to the tray while avoiding the person's hand.
```

Candidate action:

```text
a_t = MoveThrough(path_p, avoid=[human_hand_guard_region])
```

IntentAlign succeeds only if:

```text
cert_pre includes HumanClearanceCert(path_p, hand_guard_region)
```

During execution:

```text
human hand enters predicted path
monitor emits HandIntrusionEvent
```

EffectAlign / runtime invariant check fails:

```text
HumanHandClearance violated or certificate no longer covers current state
```

Recovery:

```text
safe stop, wait, re-observe, generate new path
```

