# Uni-app Heavy CMS Return Jank

## Problem

In a uni-app mini-program, a heavy CMS page may feel normal while loading, but after returning to the previous page the app stalls for hundreds of milliseconds or several seconds.

Typical symptoms:

- return to home and taps do not respond immediately
- lower CMS modules stay on skeletons for too long
- anchor jumps do nothing or land before data is ready
- the issue becomes much worse after the user has scrolled through most of the CMS page

## Root Causes

This jank is usually not one single bug. It is a stack of costs:

1. page-scoped requests continue after page exit and still trigger merge or render work
2. module loading is strictly sequential, so slow requests block later visible modules
3. all product modules render real skeleton trees or product card components even when far off-screen
4. active product modules only grow and never shrink, so a full-page scroll leaves the page holding the full component tree
5. page return destroys a large number of Vue components and observers in one burst
6. home `onShow` refresh work overlaps with the return window and competes for the main thread

## Pattern

For heavy CMS pages, apply all of the following together:

1. abort page-owned requests on `onUnload` and on new page reload cycles
2. keep request invalidation guards such as request ids even after adding abort
3. load product modules with bounded concurrency instead of strict sequential waterfalls
4. preserve anchor shells, but do not mount full product skeletons or product cards for far off-screen modules
5. maintain a near-screen active module window and shrink it while scrolling
6. promote visible or anchor-target modules to the front of the deferred queue
7. if the previous page has heavy `onShow` refreshes, scope any delay only to the CMS-return scenario instead of all returns

## Use When

- home -> heavy CMS page -> back home -> tap lag
- CMS pages with many product modules
- anchor navigation combined with lazy product loading
- mini-program pages where full-page scroll makes return jank much worse

## Avoid

- only delaying the previous page `onShow` globally
- only increasing request concurrency without reducing rendered component count
- virtualizing away anchor nodes entirely
- relying only on ignored stale responses while leaving requests running
- keeping every scrolled product module mounted until page exit

## Minimal Recipe

- page owns a request task list and aborts it on unload
- page keeps a request id guard for stale callbacks
- deferred product modules are loaded with bounded concurrency
- off-screen product modules render lightweight placeholders, not full card trees
- active product modules are replaced by a near-screen window on scroll
- anchor clicks first activate and prioritize the target module, then scroll
- previous-page heavy refreshes are delayed only for the CMS-return path

## Example Source

- `example-wxapp` CMS return performance investigation
