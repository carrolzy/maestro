# Chrome Extension Verification

- validate manifest consistency
- verify injection occurs on the target page
- verify message flow end to end
- test the target-site happy path
- verify sender and receiver both run in the expected context
- verify selector still works after SPA route change or host-page rerender
- verify no duplicate injected UI or duplicate listeners are created
- verify permission and host permission still match the active target domain
- verify environment-specific API routing and request success path
- verify the failure path when host DOM or message payload is missing
