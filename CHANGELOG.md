# Changelog

## 0.3.1 - 2026-05-01

- Fix `summary.source_files` to count only actual essence-bearing source mobs
  (`role == "source"` and `has_essence == true`).
- Reference-only source mobs no longer inflate the aggregate linked count, so
  summaries now match Source Files tables that filter to real audio files.
- Keep report schema at `"2.2"` because the JSON shape is unchanged.

## 0.3.0 - 2026-05-01

- Add SourceMobEntry `container`, `data_size_bytes`, `has_essence`, and
  `format_summary` fields for downstream source-file tables.
- Classify WAV, BWF, AIFF, and MP3-like source descriptors, including BWF
  detection via the WAV `Summary` RIFF `bext` chunk.
- Report embedded essence stream sizes when data is stored in the AAF.
- Bump package version to 0.3.0 and report schema to `"2.2"`.

## 0.2.0 - 2026-04-30

- Fix clip and marker timeline timecodes to honor AAF timecode start and
  drop-frame formatting.
- Report both embedded and linked audio file types when both are present.
- Align pyaaf2 dependency and HTML report-order documentation with the current
  implementation.
- Add source mob `role`, `summary.source_files`, and `--json` as a synonym for
  `--json-only`.
- Bump package version to 0.2.0 and report schema to `"2.1"`.

## 0.1.0 - 2026-04-25

- Add Phase 1 package skeleton, CLI shell, empty model contracts, and CI wiring.
- Implement Phase 2 report models, formatting helpers, and pyaaf2-backed engine.
- Add Phase 3 generated AAF fixtures and engine integration coverage.
- Wire the Phase 4 CLI to JSON stdout/file output with slug and collision handling.
- Add Phase 5 self-contained HTML report rendering with clip filtering.
- Add Phase 6 smoke flow, CI smoke coverage, and release documentation.
- Bump report schema to version 2 and add source properties for Pro Tools-style
  headline reporting.
