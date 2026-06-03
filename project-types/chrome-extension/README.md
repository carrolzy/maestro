# Chrome Extension Template

## Type Definition

Use this template for browser extension projects focused on content scripts, message passing, host-page integration, and data push flows.

## Inspect First

- `manifest.json`
- background or service worker entry
- content scripts
- popup or options UI
- message bridge
- host-page selector or injection anchor
- permissions and host permissions
- environment or API base URL config

## Common Task Shapes

- scrape host-page data
- adjust floating UI
- change message flow
- add site adaptation
- troubleshoot injection or permission issues

## High-Risk Areas

- content script injection timing
- background and content message routing
- SPA rerender and DOM invalidation
- permission expansion
- cross-environment network requests
- host-page selector drift
- duplicate injection or repeated listeners

## Default Audit Order

When a task touches this project type, inspect in this order:

1. `manifest.json`
2. background or service worker entry
3. content script entry
4. popup / options / injected UI entry
5. sender and receiver in message flow
6. target host page selectors
7. request and environment config

## Typical Runtime Units

- `manifest.json`
  Declares permissions, host scope, background entry, content scripts, and action UI.
- background / service worker
  Owns extension lifecycle events, storage, routing, and privileged APIs.
- content script
  Runs inside target pages, reads DOM, injects UI, and relays messages.
- popup / options page
  Owns user controls, configuration, and manual action entry points.
- shared request or env config
  Determines which backend, headers, and environments are used.

## Common Task Questions

Before changing code, answer:

1. Which runtime unit owns the behavior being changed
2. Which page or host context triggers the behavior
3. What is the sender and what is the receiver in the message chain
4. Is the change selector-driven, event-driven, permission-driven, or environment-driven
5. What breaks if the host page rerenders or the message arrives twice
