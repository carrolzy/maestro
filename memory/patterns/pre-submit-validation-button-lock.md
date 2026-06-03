# Pre-Submit Validation Button Lock

## Problem

Some actions require pre-submit validation before navigation or final submission.

If validation takes noticeable time, users may click repeatedly, causing duplicate requests, repeated navigation, or inconsistent UI state.

## Pattern

When an action has a validation pause before submit or navigation:

1. set a page-local lock before validation starts
2. pass the lock into the shared button component
3. show a busy label such as `校验中...`
4. disable the button while the lock is active
5. release the lock on:
   - validation failure
   - navigation failure
   - submit failure
   - successful page transition callback

## Use When

- checkout before confirm-order
- submit before payment
- save before route change
- any action where backend freshness must be checked first

## Avoid

- relying on silent pauses without visible feedback
- only disabling after the second click
- keeping the lock only in the shared component while page logic can still re-enter

## Minimal Recipe

- page owns the boolean lock
- shared button receives the lock as a prop
- action handler exits immediately if lock is already true

## Example Source

- `example-wxapp` shared cart checkout validation flow

