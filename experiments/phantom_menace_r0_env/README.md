# Phantom Menace isolated R0 client environment

This directory tracks the small reconstruction inputs that would otherwise exist only under the ignored
`results/` tree. They correspond to the isolated 2026-07-15 R0 run:

- `client_requirements.txt`: uv pip snapshot; SHA-256
  `f3b1dcf0bc9b862f5287eaf3bfdb84e7c7648ca7188be400e8d1591bf0ea197e`.
- `sitecustomize.py`: optional robosuite 1.4.0 private-macro overlay; SHA-256
  `b4647c9f8c31c14f08b11a7c719bc228c453bfacf734f0e6898da32ba55879f1`.
- `libero_config.yaml`: clean standard-LIBERO path binding for this workspace; SHA-256
  `e4baaab540912d9231cf22e88bfacf29a8adff5c3f18c4aa552808c6c319c765`.
- `config.yaml`: byte-identical runtime filename required by LIBERO when
  `LIBERO_CONFIG_PATH` points at this directory; it has the same SHA-256 as
  `libero_config.yaml`.

The requirements and LIBERO config intentionally bind `/home/ldx/lean-vla`; a different workspace must generate a
new manifest rather than silently rewriting these frozen files. Use the Conda-provided uv and `/data0/ldx` cache
locations documented in `docs/next_agent_prompt_20260715.md`.
