# Chrome Extension Pitfalls

- content-script timing
- SPA rerender invalidates selectors
- permission mismatch
- CORS or network environment differences
- duplicate injected UI after route change or repeated mount
- message sender and receiver not aligned
- background listener registered but never triggered in the active context
- host permission exists in one environment but target domain changed in another
- extension storage and in-memory state drift
- relying on static DOM when target page loads incrementally
- popup state looks correct while actual content-script state is stale
- CSS leakage between injected UI and host page
