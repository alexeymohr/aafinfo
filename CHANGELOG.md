# Changelog

## Unreleased

- Fix clip and marker timeline timecodes to honor AAF timecode start and
  drop-frame formatting.
- Report both embedded and linked audio file types when both are present.
- Align pyaaf2 dependency and HTML report-order documentation with the current
  implementation.

## 0.1.0 - 2026-04-25

- Add Phase 1 package skeleton, CLI shell, empty model contracts, and CI wiring.
- Implement Phase 2 report models, formatting helpers, and pyaaf2-backed engine.
- Add Phase 3 generated AAF fixtures and engine integration coverage.
- Wire the Phase 4 CLI to JSON stdout/file output with slug and collision handling.
- Add Phase 5 self-contained HTML report rendering with clip filtering.
- Add Phase 6 smoke flow, CI smoke coverage, and release documentation.
- Bump report schema to version 2 and add source properties for Pro Tools-style
  headline reporting.
