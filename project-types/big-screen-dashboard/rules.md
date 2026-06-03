# Big-Screen Dashboard Rules

1. Preserve the distinction between home-screen runtime and management-subpage runtime unless the task explicitly changes that boundary.
2. Treat screen scaling logic as shared infrastructure; do not duplicate viewport math inside individual panels.
3. When changing charts, scenes, or overlays, explain resize behavior, data freshness, and layering impact.
4. Keep domain service boundaries explicit when generic project APIs and screen-domain APIs both exist.
5. When a task depends on customer-delivered terrain or scene materials, call out coordinate, unit, and metadata assumptions explicitly.
