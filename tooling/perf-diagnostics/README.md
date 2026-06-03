# Perf Diagnostics

Local performance diagnostics tooling for Chrome Performance exported JSON.

## Commands

```bash
bin/perf-case init --project example-wxapp --trace /path/to/Profile.json --label home-cms-return-lag
bin/perf-case analyze --case-dir runtime/perf-cases/example-wxapp/2026-05-26-home-cms-return-lag
bin/perf-case writeback --case-dir runtime/perf-cases/example-wxapp/2026-05-26-home-cms-return-lag
```

## Runtime Layout

- `01_raw/trace.json`
- `02_parsed/trace_overview.json`
- `03_analysis/summary.json`
- `03_analysis/hotspots.json`
- `03_analysis/report.md`
- `04_writeback/writeback.md`

This tool writes runtime artifacts only. It does not write directly into `memory/`.
