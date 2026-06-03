# Project Override

## Project Terms

- "scope" = the active store context that constrains which products and prices apply

## Module Responsibilities

- shared cart component owns cart UI state; pages own the lock that guards submission
- confirm-order page recomputes totals from cart state on every entry

## Interface or Domain Notes

- totals are store-scope sensitive; recompute on scope change

## Special Components or Utilities

- `components/cart-container` is reused by both catalog and confirm-order

## Release Flow

- run the project verification checklist before submit; see `checklists/`

## Known Incidents and Forbidden Zones

- do not bypass the pre-submit validation lock
- do not cache confirm-order totals across scope changes
