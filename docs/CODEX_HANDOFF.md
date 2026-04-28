# AAFinfo — Codex Handoff

This document is the execution plan for AAFinfo v0.1.0. **Read
`PROJECT_OVERVIEW.md` first; this document assumes it.**

## Operating Rules

1. **Stay in scope.** v0.1.0 is the inspection MVP. Anything labeled "out of
   scope" or reserved for v0.2 in `PROJECT_OVERVIEW.md` is off-limits without
   an explicit instruction. No transitions deep-parse, no aaftool subprocess,
   no PDF rendering, no embedded essence extraction.
2. **Read-only.** AAFinfo never modifies the input file. Open AAFs in
   read-only mode through pyaaf2. Never write back to the input path. Do not
   touch the input file's mtime.
3. **Models are the contract.** All flow goes through Pydantic models with
   `extra="forbid"`. No ad-hoc dictionaries leaking into the report layer.
   New fields require a `schema_version` bump and a CHANGELOG entry.
4. **Engine is library-friendly.** `engine.py` and `models.py` must be
   importable without Click, Jinja2, or filesystem side-effects. AAFpeek
   will import them directly later. `aafinfo/__init__.py` re-exports
   `build_report` and `ReportModel`.
5. **No network calls.** Anywhere. Including telemetry, font fetching,
   analytics, or update checks.
6. **Determinism.** Same AAF in → same JSON out, modulo `run_id` and
   `run_started_at`. Sort everything that has no inherent order: warnings by
   code, source mobs by `mob_id`, etc. Tracks and clips preserve composition
   order.
7. **Errors.** Hard parse failures → exit 2 with a single-line stderr message
   plus a structured detail line. Per-track/per-clip recoverables → record
   in `warnings[]` and continue.

## Build Order

### Phase 1 — Skeleton

- `pyproject.toml` with uv-managed deps, pinned pyaaf2 tag, Python 3.11+.
- Package skeleton: `src/aafinfo/{__init__,cli,engine,models,report,errors,formatting}.py`,
  `src/aafinfo/templates/`, `src/aafinfo/_static/`.
- Stub Click CLI that accepts `<file.aaf>` and prints `"ok"`.
- Empty Pydantic models matching the JSON schema in `PROJECT_OVERVIEW.md`.
- `README.md`, `LICENSE` (MIT), `CHANGELOG.md`, `.gitignore`, `TODO.md`.
- CI workflow: `uv sync --dev --frozen`, `uv run pytest`.

**Deliverable:** `uv run aafinfo --help` works. CI passes on an empty test
suite.

### Phase 2 — Engine and Models

- Implement `models.py` fully. All nested types. `extra="forbid"`. Schema
  version 1. Frozen models where useful.
- Implement `formatting.py`: timecode from edit-unit + edit rate (rational
  arithmetic via `fractions.Fraction`), duration string, basename,
  channel-format inference from channel count, byte size formatting.
- Implement `engine.py`:
  - Open AAF via pyaaf2 (read-only).
  - Walk composition mob → tracks → segments → clips.
  - Resolve source mobs; capture sample rate, bit depth, channel info,
    embedded vs linked, paths.
  - Walk markers (CommentMarkers).
  - Build and return a `ReportModel`.
- Unit tests for formatters and model round-trips (validate → dump → re-validate).

**Deliverable:** A Python session can `from aafinfo import build_report`,
call `build_report(path)`, and get a populated `ReportModel`.

### Phase 3 — Fixture Generation and Engine Tests

- `examples/_generate.py` writes 3–5 deterministic AAF fixtures using
  pyaaf2's write side:
  1. **simple_stereo** — 1 stereo audio track, 4 clips, no fades, no markers.
  2. **multi_track** — 4 audio tracks (2 mono DX, 1 stereo MX, 1 stereo SFX),
     mixed clip counts, basic fades.
  3. **with_markers** — 1 track plus 5 markers at varied timecodes,
     including at least one colored marker.
  4. **embedded_essence** — 1 track with 1 clip whose source mob has
     embedded essence (just to exercise the `is_embedded: true` path).
  5. **non_integer_rate** — `24000/1001` edit rate to exercise rational TC
     math.
- Integration tests run `engine.build_report` against each fixture and
  assert on key fields (track counts, clip counts, expected timecodes,
  embedded flag, etc.).

**Deliverable:** `uv run python examples/_generate.py` produces fixtures
under `examples/_generated/`. `uv run pytest` exercises the engine
end-to-end.

### Phase 4 — CLI and JSON

- Wire `cli.py` to `engine.build_report`.
- Implement `--json-only`, `--out`, `--name`, `--version`, exit codes.
- Slug derivation from input filename: lowercase, replace runs of
  non-alphanumerics with single dashes, strip leading/trailing dashes; fall
  back to `report` if empty.
- Numbered-sibling collision handling for output files.
- Integration tests: full CLI invocation via Click's `CliRunner`, JSON
  round-trips through Pydantic, exit code coverage.

**Deliverable:** `uv run aafinfo path/to/fixture.aaf --json-only` prints
valid schema-1 JSON. `uv run aafinfo path/to/fixture.aaf --out ./out` writes
`<slug>-report.json`.

### Phase 5 — HTML Report

- `report.html.j2` and `_static/report.css`. CSS is read at render time and
  inlined into a `<style>` tag — the rendered HTML must be a single file
  with no external references.
- All sections from `PROJECT_OVERVIEW.md`, in the documented order.
- Print stylesheet (`@media print`) usable for browser-driven PDF export.
- `--filter` applied to the clips section only, at render time.
- `--no-clips` removes the clips section entirely.
- **No JavaScript in 0.1.0.** Filtering is server-side.
- Integration tests: render HTML, parse with `lxml`, assert key tables exist
  and contain expected basenames; verify no external `<link>`, `<script>`,
  or `@import` references slipped in.

**Deliverable:** `uv run aafinfo path/to/fixture.aaf` writes both
`<slug>-report.json` and `<slug>-report.html`. Opening the HTML in a
browser shows a complete, self-contained, factual report.

### Phase 6 — Polish and Release Prep

- `examples/_smoke.py` mirrors FinalPass: generate fixtures, run the CLI
  against each, assert exit codes and artifact existence.
- CI runs the smoke helper on 3.11 and 3.12.
- README with install, quick start, command reference, output examples,
  scope and non-goals, license, and pyaaf2 dependency note.
- CHANGELOG `0.1.0` entry.
- Tag and release notes ready.

## Conventions

- **Python**: 3.11+. Type hints everywhere. `from __future__ import annotations`
  in every module.
- **Pydantic**: v2. `extra="forbid"`. Frozen models where practical.
- **Click**: single command, not a `Group`. Long-form flags only in 0.1.0;
  no short aliases.
- **Jinja2**: autoescape on. No custom filters that hide logic from the
  template reader.
- **Tests**: pytest. Click's `CliRunner` for CLI tests. No live AAFs in
  version control; everything generated by `examples/_generate.py`.
- **Imports**: standard lib, then third-party, then local. No star imports.
- **File paths**: `pathlib.Path` everywhere internally; `str` only at the
  CLI boundary.
- **Style**: `ruff` is welcome but not required.

## Forbidden in 0.1.0

- Writing AAFs.
- Modifying the input file in any way (including touching its mtime).
- Network calls of any kind.
- JavaScript in the HTML output.
- Subprocess calls to `aaftool` or any other external tool.
- PDF generation libraries.
- macOS-only code paths or imports.
- Any dependency not listed in `PROJECT_OVERVIEW.md`.
- Reading LibAAF source code while implementing AAFinfo. (LibAAF is GPL2
  and out of scope; format knowledge needed beyond pyaaf2 belongs in upstream
  pyaaf2 PRs, not here.)

## When in Doubt

If a real-world AAF causes pyaaf2 to fail on some specific structure, do
**not** attempt to work around it inside AAFinfo. Record the failure in
`warnings[]`, keep going, and note the case in `TODO.md` for a future
upstream pyaaf2 PR. That is the explicit philosophy:

> AAFinfo wraps pyaaf2; gaps in pyaaf2 are fixed in pyaaf2.

Anything that would constitute "AAFinfo's own AAF parser" violates this
principle and should be flagged for review before implementation.
