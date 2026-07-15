# External reproduction patches

`phantom_menace_r0_runner.mbox.b64` is a Base64-encoded two-commit mbox. The encoding avoids normalizing historical
trailing whitespace in the upstream source while keeping the root repository's whitespace checks clean.

- encoded payload SHA-256: `e0c12e8c5fb07cbfdf79b32270972356611c613f78b06c378bb73ac486389cde`
- decoded mbox SHA-256: `b8fe708aa4a8db65fb37a44530a55274a620b73260edf703e9423821ff2a0b3e`
- upstream parent: `a0e4c8b2a661ea2fe64bdb9055353b2e12575729`
- expected final commit after `git am --committer-date-is-author-date`:
  `d03fcbdfa4d49985dabd60e11e12008e2af3a783`

Exact reconstruction commands are in `docs/next_agent_prompt_20260715.md`.
