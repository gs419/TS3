# Repository instructions

## Project scope

- TowerGlance is an independently designed, local-first real-time webview for Tower! Simulator 3.
- Define product functionality only through repository-owned requirements, domain documentation, architectural decisions, and independently obtained evidence.
- TowerGlance must operate using Tower! Simulator 3 and locally available game data without requiring another companion application, account, subscription, or hosted data service.
- Derive runtime information independently from Tower! Simulator 3 interfaces, game-generated logs, and local game or airport files.
- Do not use, copy, adapt, bundle, or depend on third-party application code, assets, private APIs, authentication, subscriptions, data streams, installation files, or implementation details.
- Do not reproduce proprietary visual assets or implementation details from third-party applications.
- Keep protocol fixtures minimal, synthetic or sanitized, and free of personal data, credentials, absolute user paths, and third-party proprietary content.
- Separate observed evidence, engineering inference, and maintainer decisions when documenting undocumented interfaces.

## Development flow

- Before tracker, planning, implementation, review, or publication work, read the relevant configuration under `docs/agents/`.
- Treat `AGENTS.md` as the canonical shared project instructions; keep `CLAUDE.md` limited to `@AGENTS.md` plus Claude-specific deltas.
- Treat `.docs/` as local-only working documentation and keep it ignored by Git.
