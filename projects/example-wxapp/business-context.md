# Business Context

## Project in One Sentence

`example-wxapp` is a sample e-commerce mini-program used to demonstrate how this system captures business semantics; it is fictional and carries no real company data.

## Business Goals

- let shoppers browse a product catalog, manage a cart, and place orders
- keep cart totals and the confirm-order page consistent across store/scope changes
- serve as the worked example and test fixture for the task-package builder

## User Roles

- guest shopper (browse only)
- signed-in shopper (cart, checkout, orders)

## Core Business Objects

- Product, SKU, Cart, CartItem, Order, Store

## Key Business Flows

- browse catalog -> add to cart -> review cart -> confirm order -> pay
- switch store/scope -> recompute cart eligibility and totals

## Page or Module Mapping

- `pages/catalog` product listing
- `components/cart-container` shared cart UI
- `pages/confirm-order` order confirmation and totals

## Critical Rules and Boundaries

- cart, store scope, and confirm-order totals are tightly coupled; changes to one must be re-validated against the others
- never submit an order while a pre-submit validation is still pending

## Interface Semantics

- cart state is the source of truth for confirm-order; confirm-order must not cache stale totals

## Historical Pitfalls

- duplicate order submission when the confirm button is tapped repeatedly during validation (see `memory/patterns/pre-submit-validation-button-lock.md`)
