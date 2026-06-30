# LIBERO-Safety Integration

This repository has two LIBERO-Safety integration paths:

1. An offline-first adapter that exports ProofAlign-compatible JSON episodes
   from a real LIBERO-Safety checkout, then uses the existing experiment runner
   to produce JSONL records and summary metrics.
2. An online wrapper that runs on the same LIBERO-Safety simulation backend and
   gates each real VLA action chunk with ProofAlign before and after `env.step`.

## Confirmed Upstream

- Project page: https://libero-safety.github.io/
- Code: https://github.com/LIBERO-SAFETY/LIBERO-Safety
- Local checkout used for integration study: `/private/tmp/LIBERO-Safety`
- Commit studied: `ef0f79b70fc50c5fb612a1bbc1cf8b6c033a702a`
- Benchmark registry: `libero/libero/benchmark/__init__.py`
- Task map: `libero/libero/benchmark/vla_safety_task_map.py`
- BDDL files: `libero/libero/bddl_files/<suite>/L<level>/*.bddl`
- Init states: `libero/libero/init_files/<suite>/L<level>/*.pruned_init`

The official README says the package remains import-compatible as `libero`,
with setup via `pip install -e .`, `pip install -r requirements.txt`,
`pip install -r extra_requirements.txt`, and editable install of
`third_party/robosuite-1.4`.

LIBERO-Safety uses the LIBERO environment stack on top of `robosuite` and
MuJoCo. The native evaluation env exposed by the benchmark is
`libero.libero.envs.OffScreenRenderEnv`, which wraps a robosuite
`SingleArmEnv`-derived task and exposes `env.sim`, `env.step`, `env.reset`,
`check_success`, object dictionaries, and safety `info["cost"]` values. The
online ProofAlign integration should therefore wrap this env instead of using
the toy `DiscreteSimulator`.

## Setup

```bash
git clone https://github.com/LIBERO-SAFETY/LIBERO-Safety.git /path/to/LIBERO-Safety
cd /path/to/LIBERO-Safety
git rev-parse HEAD
pip install -e .
pip install -r requirements.txt
pip install -r extra_requirements.txt
pip install -e third_party/robosuite-1.4
export LIBERO_SAFETY_ROOT=/path/to/LIBERO-Safety
```

Also follow the upstream asset instructions so `libero/libero/assets/` and
`~/.libero/config.yaml` point at the LIBERO-Safety checkout.

## Export And Run

```bash
cd /path/to/proofalign
export LIBERO_SAFETY_ROOT=/path/to/LIBERO-Safety

uv run python scripts/export_libero_safety.py \
  --split eval \
  --output examples/libero_safety_export

uv run python -m proofalign.experiments \
  --input examples/libero_safety_export \
  --output results/libero_safety_eval \
  --modes vla_only,collision_only,intent_only,effect_only,dual
```

Use `--split affordance,human_safety` or any single suite name to export a
subset. The five LIBERO-Safety suite mappings are:

- `affordance` -> `AAG`
- `human_safety` -> `HRI`
- `obstacle_avoidance` -> `TSA`
- `obstacle_avoidance_human` -> `FSHOA`
- `reasoning_safety` -> `SSR`

## Candidate Action Sidecars

Real benchmark metrics require VLA action chunks or an execution logger to
provide symbolic candidate actions. Put sidecar JSON under:

```text
$LIBERO_SAFETY_ROOT/proofalign_actions/<suite>/L<level>/<task_name>.json
```

Accepted sidecar shape:

```json
{
  "candidate_actions": [
    {"type": "Pick", "object": "knife_1", "part": "handle"}
  ],
  "expected_decision": "allow",
  "safety_spec": {
    "safety_margin": 0.2
  }
}
```

If no sidecar exists, the adapter emits a conservative heuristic placeholder
action and marks `metadata.candidate_action_source` as
`heuristic_from_instruction_no_vla`. That mode is for plumbing/export checks,
not for reporting benchmark numbers.

## Online VLA Wrapper

For real VLA rollouts, use the same LIBERO-Safety backend and wrap the native
env with `ProofAlignLiberoWrapper`:

```python
from proofalign.benchmark import ProofAlignLiberoWrapper, make_libero_offscreen_env
from proofalign.models import SafetySpec

env = make_libero_offscreen_env(
    bddl_file_name="/path/to/task.bddl",
    camera_names=["agentview", "robot0_eye_in_hand"],
    camera_heights=128,
    camera_widths=128,
)

wrapper = ProofAlignLiberoWrapper(
    env,
    instruction=env.language_instruction,
    spec=SafetySpec.from_dict({"safety_margin": 0.2}),
)

obs = wrapper.reset()
raw_vla_action = policy(obs)
result = wrapper.step(
    {
        "raw_action": raw_vla_action,
        "proofalign_action": {
            "type": "Pick",
            "object": "mug_1",
            "part": "handle",
        },
    }
)
```

The wrapper keeps the two action representations separate:

- `raw_action` is the continuous or low-level VLA action passed to
  `OffScreenRenderEnv.step`.
- `proofalign_action` is the symbolic action contract passed to
  `DualAlignmentChecker`.

If the VLA only emits continuous actions, provide a custom
`LiberoActionAbstractor` that maps each action chunk to a ProofAlign contract:

```python
class MyActionAbstractor:
    def abstract(self, raw_action, *, instruction, observation, state, spec, history):
        # Use policy metadata, skill labels, object detections, or planner output.
        return action_from_dict({"type": "MoveTo", "object": "mug_1", "region": "target_region"})
```

The default abstractor refuses to guess symbolic contracts from bare continuous
arrays. This is deliberate: unsafe or ambiguous abstraction should trigger
integration work, not silent execution.

`LiberoStateObserver` extracts a conservative `WorldState` from the live env:

- object and fixture poses from MuJoCo body positions,
- held object hints from gripper contact checks,
- human hand and obstacle distance from `info` when available or object poses
  when detectable,
- collision/safety violations from `info["cost"]`,
- optional regions from LIBERO site objects.

The online wrapper returns `allow`, `reject`, `replan`, or `safe_stop` through
`LiberoStepResult.decision` and mirrors the decision into `result.info` under
`proofalign_*` keys.

## Online Runner

For an executable end-to-end rollout on the benchmark machine, use:

```bash
uv run python scripts/run_libero_online.py \
  --benchmark affordance \
  --task-id 0 \
  --init-state-id 0 \
  --policy my_vla_eval:create_policy \
  --abstractor my_vla_eval:create_abstractor \
  --output results/libero_online/affordance_task0_init0.json
```

The runner follows the official LIBERO evaluation flow:

1. `get_benchmark(benchmark_name)()` loads the task suite.
2. `benchmark.get_task(task_id)` retrieves language, BDDL, and metadata.
3. `OffScreenRenderEnv` is created from the task BDDL.
4. `env.seed`, `env.reset`, and `env.set_init_state` initialize the fixed
   benchmark state.
5. The VLA policy receives `(instruction, observation, history)` and returns a
   raw action chunk.
6. ProofAlign checks the symbolic contract before `env.step(raw_action)` and
   audits the observed post-state after the MuJoCo step.

The policy plugin must be importable as `module:factory`. Its factory returns a
callable:

```python
def create_policy(**kwargs):
    model = load_my_vla(**kwargs)

    def policy(instruction, observation, history):
        raw_action = model.act(observation, instruction)
        return {
            "raw_action": raw_action,
            "proofalign_action": {
                "type": "Pick",
                "object": "mug_1",
                "part": "handle",
            },
        }

    return policy
```

If the policy cannot produce `proofalign_action` directly, pass an abstractor
plugin:

```python
def create_abstractor(**kwargs):
    class Abstractor:
        def abstract(self, raw_action, *, instruction, observation, state, spec, history):
            return action_from_dict({"type": "MoveTo", "object": "mug_1", "region": "target_region"})

    return Abstractor()
```

For a backend smoke test without a VLA model, the runner can replay logged
actions:

```bash
uv run python scripts/run_libero_online.py \
  --benchmark affordance \
  --task-id 0 \
  --action-file /path/to/actions.json \
  --output results/libero_online/replay.json
```

An action file is a JSON list or JSONL stream whose entries contain the same
`raw_action` / `proofalign_action` pair. A zero-action smoke test is also
available by omitting `--policy` and `--action-file`; that only verifies env
startup and should not be reported as a VLA benchmark result.

## Trusted Boundary

ProofAlign treats perception, VLA planning, low-level action execution, and the
LIBERO simulator as untrusted producers of symbolic abstractions and optional
certificates. The Lean/Python checker verifies the discrete symbolic contract
and returns `allow`, `reject`, `replan`, or `safe_stop`.

Lean does not verify continuous robot dynamics. Continuous distances,
collisions, object poses, and certificate confidence values must be supplied by
the benchmark runtime or perception stack and are checked as symbolic facts.

## Current Assumptions

- LIBERO-Safety does not expose ProofAlign-shaped symbolic states directly.
  The adapter parses BDDL objects, regions, init relations, goals, and
  constraints into a symbolic approximation.
- Native `libero.libero.benchmark.get_benchmark()` is used when dependencies
  are installed. Otherwise the adapter falls back to direct source-tree parsing
  of `vla_safety_task_map.py` and BDDL files.
- Physical safety constraints are read from BDDL predicates such as
  `CheckRobotContact` and `CheckContact`; richer runtime measurements should be
  passed through action sidecars or certificates.
- The included `examples/libero_safety_export/sample_aag_affordance.json` is a
  synthetic schema sample, not an official benchmark result.
