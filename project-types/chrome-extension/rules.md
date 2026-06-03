# Chrome Extension Rules

1. Name the host-page selector or injection anchor for scraping changes.
2. Explain why any new permission is required.
3. State sender and receiver when changing message communication.
4. Prefer minimal permission and minimal host-scope changes.
5. Do not change `manifest.json` casually; every permission, host scope, and entry change must be justified.
6. When modifying content scripts, explain injection timing and rerender behavior.
7. When adding floating UI or injected controls, state how duplicate injection is prevented.
8. When changing message flow, describe the full chain: trigger, sender, transport, receiver, and side effect.
9. When touching environment or API routing, name every affected environment and target domain.
10. Prefer a single source of truth for selectors, env config, and message types when the project already has one.
11. If scraping depends on host-page DOM structure, call out brittleness and fallback strategy.
12. When touching background logic, verify whether the code runs in service worker lifecycle constraints rather than assuming page-like persistence.
