# Big-Screen Dashboard Pitfalls

- fixed-stage layout looks correct at 1920x1080 but breaks at smaller heights
- chart autoresize appears correct on first mount but drifts after dialogs or route switches
- screen-scale CSS variables update, but absolute-position overlays do not
- map, terrain, or warning markers align visually in one asset package but not another
- polling and publish dialogs read stale warning state after asynchronous refresh
- a management subpage change unintentionally breaks the full-screen shell
- customer-delivered scene files omit unit, origin, axis, or coordinate-system metadata
- generic CRUD verification passes while the real home-screen visual path regresses
