# Task Context

## Current Task

Keep cart and confirm-order totals consistent after add-to-cart.

## Why This Task Exists

Shoppers reported that totals on the confirm-order page could disagree with the cart after rapid edits.

## Business Delta for This Task

Confirm-order must always recompute from current cart state instead of a cached snapshot.

## Affected Pages or Modules

- `components/cart-container`
- `pages/confirm-order`

## Constraints for This Task

- no duplicate submissions during validation
- totals must stay store-scope consistent

## Verification Focus

- cart edits reflect on confirm-order
- store-scope changes recompute totals
