# Big-Screen Dashboard Template

## Type Definition

Use this template for web projects centered on a large-screen or fixed-stage visual home page, often combined with subpage management modules, charts, map overlays, scene rendering, warning boards, and operational monitoring panels.

## Inspect First

- route config and screen-mode split
- root layout shell
- screen scaling or viewport adaptation logic
- homepage stage composition
- chart, map, graph, or scene modules
- request wrapper and domain service split
- static asset and material manifest
- smoke or visual regression scripts

## Common Task Shapes

- adjust full-screen layout or scaling
- add or revise dashboard module blocks
- update chart, graph, or warning visualization
- modify scene, terrain, or material delivery flow
- change management subpages while preserving home-screen shell behavior
- adapt backend contract changes for monitoring or warning flows

## High-Risk Areas

- 1920x1080 design assumptions leaking into arbitrary viewport logic
- full-screen fixed layers overlapping or swallowing interaction
- chart resize drift after mount, dialog open, or route switch
- scene and map overlays falling out of alignment after scale changes
- stale warning data, poll cadence mismatch, or inconsistent publish flow
- heavy home-page modules hurting initial render stability
- mixing generic admin CRUD paths with screen-first runtime assumptions
- external terrain, GIS, or customer-delivered assets using inconsistent coordinate or metadata conventions

## Default Audit Order

When a task touches this project type, inspect in this order:

1. router and page mode split
2. default layout shell
3. screen scaling composables or viewport CSS variables
4. dashboard home page and its module composition
5. domain service layer and backend contracts
6. shared warning, chart, dialog, and scene helpers
7. smoke scripts and verification expectations

## Typical Runtime Units

- router
  Separates login, home-screen, and subpage runtime modes.
- layout shell
  Owns frame chrome, screen navigation, and route-stage containment.
- screen scaling logic
  Owns design baseline, safe scale, viewport variables, and resize propagation.
- dashboard home
  Owns hero stage, warning overlays, major panels, and scene/chart composition.
- domain services
  Owns monitoring, warning, ontology, device, and push-contract calls.
- asset or material package
  Owns imagery, labels, terrain metadata, and customer-delivered supporting files.

## Common Task Questions

Before changing code, answer:

1. Is this change home-screen only, subpage only, or shared across both
2. Which layer owns the visual scale and fixed-stage assumptions
3. Does the task touch data freshness, polling, or publish state
4. Does the task depend on external scene/material coordinates or metadata
5. What breaks if the screen resizes, remounts, or opens dialogs over charts or scenes
