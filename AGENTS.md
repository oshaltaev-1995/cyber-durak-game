# Agent guidance

- Before relevant gameplay, product, or architecture work, read `docs/GAME_RULES.md`,
  `docs/PRODUCT_BRIEF.md`, and `docs/IMPLEMENTATION_NOTES.md`.
- Treat `docs/GAME_RULES.md` as the gameplay source of truth, `docs/PRODUCT_BRIEF.md` as the MVP and
  product-scope source of truth, and `docs/IMPLEMENTATION_NOTES.md` as the preferred technical
  direction.
- Never invent or silently reinterpret missing or ambiguous rules. Report ambiguity and ask for
  clarification.
- Keep the rules engine deterministic, testable, and independent of the UI, Angular, and network
  transport.
- Add tests for every gameplay behavior and regression.
- Document deliberate rule changes in `docs/GAME_RULES.md` before or together with the implementing
  code change.
- Design multiplayer with an eventually authoritative server; do not trust clients with game state.
- Avoid unnecessary dependencies, premature abstractions, and speculative feature scaffolding.
- Prefer small, reviewable changes that follow the existing project structure.
- Run all checks relevant to changed code before considering work complete.
- Do not implement future product scope unless it is explicitly requested.
- Never commit secrets, generated build output, dependency directories, or local environment files.
