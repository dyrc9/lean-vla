# Remote full-120 result handoff

This file is machine-generated from the terminal manifest and analysis JSON.

- Checkout base: `9c9d08ff6754c5957a17f44da26ef43646ff52ca`
- Experiment branch: `exp/remote-full120-four-arm-20260818`
- Protocol: `experiments/proofalign_remote_full120_successor_protocol_20260818.json`
- Protocol SHA-256: `fbdb4ecd03a85f75ff83bf62f0c97397604d2b2767b61d88906e70bae90b151b`
- Classification: `remote_full120_clean_terminal_invalid_conservative`
- Planned/completed/valid/missing clean episodes: 480/1/1/479
- Reuse decision: 0 reused; the full 960 rerun was required because historical replan_steps, runner, and raw schema did not match.
- Attacked episodes: 0. The frozen clean prerequisite did not pass, so attacked execution was not authorized.
- Fail-closed error: `SemanticPolicyWrapperError: trusted BDDL goal has no supported semantic predicates`
- Failure interpretation: the fixed affordance BDDL uses Checkgrippercontactpart, but the frozen qualified semantic compiler has no trusted part-level geometry. No threshold, arm, population, or risk definition was changed.
- Historical baseline remains 39/86 = 45.35% and `confirmatory_attack_foundation_nonpass`; it was not reclassified or copied into a defense arm.
- Risk-transition output: not estimable because clean did not complete and attacked was correctly blocked.
- Raw root: `results/proofalign_remote_full120_clean_20260818_fresh1`
- Ledgers: `execution_ledger.jsonl` and `episodes_ledger.jsonl`
- Checksums: `SHA256SUMS`
- Terminal analysis: `terminal_analysis.json`
- Generated tables: `tables/remote_full120_terminal_status.{json,csv,tex}`
- stdout/stderr capture: missing; manifest error and Python traceback were observed, so this retention check is non-pass.

No paper or Overleaf source was modified.
