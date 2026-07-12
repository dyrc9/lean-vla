# Lean-backed LIBERO Macro-Chunk Plan

> 状态说明（2026-07-10）：本文是 legacy chunk runtime 的设计与落地记录。
> `TraceSummary`、chunk effect/frame checks 和 `step_chunk` 已经实现；当前主方法已升级为
> CTDA。CTDA 让 semantic contract 跨多个 policy call 持续存在，但为了 fresh authorization
> 当前每次只 dispatch 一个 raw `env.step`。最新方法与实现边界见
> [`method.md`](method.md) 和 [`system_architecture.md`](system_architecture.md)。

## Goal

ProofAlign should run on LIBERO / LIBERO-Safety as an online VLA safety wrapper,
not as an offline theorem-proving demo. The intended runtime unit is a semantic
macro-chunk rather than a single low-level 7D VLA action.

The target flow is:

```text
LIBERO instruction + BDDL/task metadata
  -> TaskIntent + SafetySpec + required certificates

OpenVLA low-level action stream
  -> semantic macro-chunk contract

LIBERO execution trace
  -> chunk-level TraceSummary and certificates

Lean checks:
  1. Intent-Action Alignment before chunk execution
  2. Action-Effect Alignment after chunk execution
```

Lean remains the trusted checker for typed symbolic contracts. It does not
verify raw images, continuous dynamics, MuJoCo contact physics, or VLA inference.

## Why Macro-Chunks

OpenVLA and OpenVLA-OFT produce low-level action slices. A single action step is
usually only a small end-effector delta plus gripper command, so checking each
step independently often collapses to repeated `MoveTo` checks. Manipulation
semantics such as pick, place, handover, or pour only become visible over
multiple simulator steps.

The runtime checker should therefore operate on semantic macro-chunks:

```text
raw_action_chunk[0:K] -> symbolic contract
```

Short-term, `K` can follow the policy chunk length, for example the OpenVLA-OFT
8-step action chunk. Longer-term, chunk boundaries should be event-triggered:

- gripper close: `MoveTo -> Pick`
- gripper open: `Holding -> Place`
- object becomes held: pick chunk ends
- object is released: place chunk ends
- target region reached: move/place chunk ends
- LIBERO `cost` or collision signal: immediate effect audit / safe stop
- timeout or no progress: replan

This keeps the method aligned with how LIBERO manipulation tasks actually
unfold.

## Spec Compiler

The current repository derives `TaskIntent` from a narrow rule-based parser and
derives `SafetySpec` mostly from suite-level templates, BDDL parsing, and
optional JSON overrides. The missing method component is an explicit compiler:

```text
LIBERO language instruction
BDDL objects / regions / predicates
suite name and task metadata
optional benchmark annotations
  -> TaskIntent
  -> SafetySpec
  -> RequiredCertificates
```

The compiler should not ask an LLM to emit arbitrary Lean code. If an LLM is
used, it should only extract or normalize structured slots. The final spec must
be assembled through typed schemas and fixed pattern templates.

Example compiler output:

```json
{
  "task_intent": {
    "verb": "place",
    "target_object": "fork_1",
    "target_region": "plate_region"
  },
  "safety_spec": {
    "forbidden_parts": ["blade", "tines"],
    "protected_objects": ["human_hand", "obstacle"],
    "require_no_collision": true,
    "safety_margin": 0.2,
    "frame_conditions": ["knife_1", "human_hand"]
  },
  "required_certificates": [
    "object_identity",
    "collision_free",
    "human_clearance",
    "state_transition",
    "frame_condition"
  ]
}
```

LIBERO suite mappings should remain explicit:

- `affordance`: safe grasp parts, forbidden sharp parts, affordance constraints.
- `human_safety`: human hand protection, handover / hand-held-region constraints.
- `obstacle_avoidance`: obstacle protection, collision-free or clearance certificates.
- `obstacle_avoidance_human`: both obstacle and human-hand protections.
- `reasoning_safety`: semantic unsafe instruction detection and reject contracts.

## Layer 1: Intent-Action Alignment

Intent-Action Alignment answers:

```text
Should this semantic action chunk be executed?
```

Inputs:

- `TaskIntent`
- current symbolic `WorldState`
- semantic chunk `Action`
- `SafetySpec`
- pre-execution certificates

Lean obligation, current form:

```lean
IntentAligned intent action spec = true
```

Target form:

```lean
CertifiedIntentAligned intent state action spec preCerts = true
```

Checks:

- action object, part, and region match the task intent;
- forbidden objects are not manipulated;
- forbidden or unsafe parts are not contacted;
- explicitly dangerous instructions only compile to `Reject`;
- protected objects are not selected as targets;
- required pre-certificates such as object identity, affordance, collision-free
  path, and human clearance are valid.

Failure policy:

```text
IntentAlign fail -> reject before env.step(raw_action)
```

## Layer 2: Action-Effect Alignment

Action-Effect Alignment answers:

```text
Did the executed chunk produce the promised effect without violating safety?
```

Inputs:

- pre-chunk `WorldState`
- semantic chunk `Action`
- post-chunk `WorldState`
- `TraceSummary`
- `SafetySpec`
- post-execution certificates

Trace summary is accumulated from LIBERO over the raw steps in the chunk:

```json
{
  "num_raw_steps": 8,
  "collision": false,
  "cost": {},
  "min_human_hand_distance": 0.31,
  "min_obstacle_distance": 0.27,
  "object_became_held": true,
  "object_released": false,
  "moved_objects": ["fork_1"],
  "protected_object_moved": false
}
```

Lean obligation, current form:

```lean
EffectAligned before action after spec = true
```

Target forms:

```lean
ChunkEffectAligned before action after summary spec = true
FrameConditionHolds before after action spec = true
CertifiedEffectAligned before action after summary spec postCerts = true
```

Checks:

- `Pick(obj)` ends with `holding = obj`;
- `Place(obj, region)` ends with the object in the region and the gripper
  released;
- no collision or LIBERO safety cost occurred during the chunk;
- minimum human-hand and obstacle distances stayed above the spec margin;
- forbidden and protected objects did not move;
- non-target objects satisfy the frame condition;
- required post-certificates such as state transition and frame condition are
  valid.

Failure policy:

```text
collision/cost or severe hazard -> safe_stop
postcondition miss or no progress -> replan
unknown state or missing critical certificate -> reobserve / replan
```

## Lean Additions

The current Lean layer defines a minimal `WorldState`, `Action`, `TaskIntent`,
`SafetySpec`, `IntentAligned`, `EffectAligned`, and certificate validity. The
macro-chunk method needs these additions:

```lean
structure TraceSummary where
  numSteps : Nat
  collision : Bool
  minHumanHandDistance : Nat
  minObstacleDistance : Nat
  movedObjects : List ObjectId
  objectBecameHeld : Bool
  objectReleased : Bool
deriving Repr, DecidableEq, BEq

def FrameConditionHolds
  (before after : WorldState)
  (action : Action)
  (spec : SafetySpec) : Bool := ...

def ChunkRuntimeSafe
  (summary : TraceSummary)
  (spec : SafetySpec) : Bool := ...

def ChunkEffectAligned
  (before : WorldState)
  (action : Action)
  (after : WorldState)
  (summary : TraceSummary)
  (spec : SafetySpec) : Bool := ...

def DualChunkAligned
  (intent : TaskIntent)
  (before : WorldState)
  (action : Action)
  (after : WorldState)
  (summary : TraceSummary)
  (spec : SafetySpec) : Bool :=
  IntentAligned intent action spec
  && ChunkEffectAligned before action after summary spec

def CertifiedDualChunkAligned
  (intent : TaskIntent)
  (before : WorldState)
  (action : Action)
  (after : WorldState)
  (summary : TraceSummary)
  (spec : SafetySpec)
  (preCerts postCerts : List Certificate)
  (minConfidence : Nat) : Bool :=
  DualChunkAligned intent before action after summary spec
  && PreCertificatesValid preCerts action minConfidence
  && PostCertificatesValid postCerts action minConfidence
```

The Python bridge should generate these expressions from typed objects rather
than from free-form LLM output.

## Python / LIBERO Runtime Changes

Add a chunk-level wrapper API alongside the existing single-step API:

```python
ProofAlignLiberoWrapper.step_chunk(policy_or_raw_actions, max_chunk_steps=8)
```

Runtime algorithm:

```text
1. observe pre-chunk WorldState
2. obtain raw action chunk from policy or pending OpenVLA actions
3. abstract chunk into one semantic Action contract
4. run Lean-backed IntentAlign
5. if intent fails, reject without env.step
6. execute raw env.step actions until max steps or event boundary
7. accumulate TraceSummary from LIBERO info, poses, contacts, and gripper events
8. observe post-chunk WorldState
9. run Lean-backed ChunkEffectAlign / CertifiedDualChunkAligned
10. return allow / reject / replan / safe_stop and write chunk trace
```

Chunk trace shape:

```json
{
  "chunk_id": 3,
  "contract": {"type": "Pick", "object": "fork_1", "part": "handle"},
  "raw_actions": [[0.0, 0.1, 0.0, 0.0, 0.0, 0.0, -1.0]],
  "intent": {"passed": true, "lean_mode": "lean"},
  "effect": {"passed": true, "lean_mode": "lean"},
  "summary": {
    "num_raw_steps": 8,
    "collision": false,
    "object_became_held": true
  },
  "decision": "allow"
}
```

## Experiments

Run on the same LIBERO-Safety suites, task ids, init states, and VLA action
source:

- VLA only
- collision / cost only
- intent only
- effect only
- dual macro-chunk alignment

Report:

- task success;
- unsafe success;
- collision / cost rate;
- rejection rate;
- false rejection rate;
- spec violation rate;
- average chunk length;
- Lean check time per chunk;
- process-level risk accumulated over chunks.

The paper should separate task success from safety decision. LIBERO can report
task success even when ProofAlign rejects before execution; that is not a
contradiction but a sign that task completion and safety should be reported as
separate axes.

## Related Work Anchors

Recent VLA safety work motivates the need for process-level safety evaluation:

- [LIBERO-Safety, 2026](https://arxiv.org/abs/2606.23686): physical and
  semantic safety benchmark for VLA models.
- [ForesightSafety-VLA, 2026](https://arxiv.org/abs/2606.27079): diagnostic VLA
  safety benchmark with process-level risk and unsafe-success analysis.

Recent NL-to-formal-spec work motivates the compiler design:

- [Req2LTL, 2025](https://arxiv.org/abs/2512.17334): hierarchical semantic
  decomposition and deterministic LTL synthesis.
- [LTLGuard, 2026](https://arxiv.org/abs/2603.05728): constrained generation,
  formal consistency checking, and repair.
- [NeuroNL2LTL, 2026](https://arxiv.org/abs/2605.22874): neurosymbolic
  intermediate representation, satisfiability checks, and verifier feedback.
- [LTLCodeGen, 2025](https://arxiv.org/abs/2503.07902): code-generation style
  generation of syntactically correct LTL for robot planning.
- [CaStL, 2024/2025](https://arxiv.org/abs/2410.22225): staged extraction of
  constraints into PDDL and Python constraints for TAMP.
- [LLM-Grounded Dynamic Task Planning with Hierarchical Temporal Logic, 2026](https://arxiv.org/abs/2602.09472):
  hierarchical LTL and receding-horizon replanning for dynamic multi-robot tasks.

Recent Lean / autoformalization work motivates using Lean as a typed checker
instead of asking the LLM to write trusted specifications directly:

- [CktFormalizer, 2026](https://arxiv.org/abs/2605.07782): natural language
  hardware specifications routed through a Lean 4 embedded typed language.
- [Process-Driven Autoformalization in Lean 4](https://arxiv.org/abs/2406.01940):
  compiler feedback for Lean 4 autoformalization.
- [Evaluating Robustness of Proof Autoformalization in Lean 4, 2026](https://arxiv.org/abs/2606.14867):
  robustness and faithfulness limits of Lean autoformalization.

## Paper Wording

A safe one-sentence method statement:

```text
ProofAlign compiles LIBERO task instructions and benchmark constraints into
Lean-checkable symbolic safety contracts, abstracts low-level VLA controls into
semantic macro-chunks, and performs dual Lean-backed checks: intent-action
alignment before chunk execution and certificate-grounded action-effect
auditing after chunk execution.
```

Avoid claiming that Lean proves continuous robot safety or that the system
solves general natural-language-to-Lean specification generation.
