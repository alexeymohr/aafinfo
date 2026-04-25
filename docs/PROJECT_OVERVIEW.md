# AAFinfo

AAFinfo is a local command-line inspector for Advanced Authoring Format (AAF)
files. It reads a single AAF, builds a structured report model, emits a
machine-readable JSON report, and renders a self-contained HTML report for
review. It is read-only and never modifies the input file.

AAFinfo is built for the practical "what is in this AAF" question that comes
up during turnover, archive audit, and troubleshooting in post-production
workflows. It is the open-source engine layer; a paid macOS app (AAFpeek)
will later wrap it with drag-and-drop, customization, Quick Look support, and
PDF export. AAFpeek lives in a separate repository and does not influence
v0.1.0 of AAFinfo, except that the engine and model layers must remain
importable as a Python library, free of CLI/HTML coupling.

This repository targets a `0.1.0` initial release: the inspection MVP.

## Scope (v0.1.0)

In scope:

- Single AAF file as input.
- pyaaf2 as the sole parsing engine.
- Composition summary, tracks list, clips list, source mob registry, and
  markers extraction.
- JSON report with explicit schema version.
- Self-contained HTML report (inline CSS, no external assets, no JavaScript).
- Filename-only display in primary tables, with a source registry holding
  full paths.
- Deterministic behavior: same input file yields the same report, modulo
  `run_id` and `run_started_at`.

Out of scope for 0.1.0 (reserved for 0.2.0 or later):

- Writing or editing AAFs of any kind.
- Embedded essence extraction.
- Transition and automation deep parsing (basic counts only in 0.1.0).
- LibAAF / aaftool integration or cross-engine reconciliation.

## Permanent Non-Goals

AAFinfo will never:

- Modify the input file.
- Make network calls during analysis.
- Emit telemetry.
- Replace AAF authoring tools, NLEs, or DAWs.
- Validate against any specific delivery spec (that is FinalPass).

## Architecture

AAFinfo follows the same layered pattern proven in FinalPass:

```
                 ┌──────────────┐
                 │   cli.py     │  Click commands, flags, exit codes
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │  engine.py   │  pyaaf2 read, build report model
                 └──────┬───────┘
                        │
                 ┌──────▼───────┐
                 │  models.py   │  Pydantic v2, schema_version
                 └──────┬───────┘
                        │
            ┌───────────┼────────────┐
            │                        │
     ┌──────▼──────┐          ┌──────▼──────┐
     │   JSON      │          │  report.py  │  Jinja2 → self-contained HTML
     └─────────────┘          └─────────────┘
```

The engine and models layers know nothing about Click, Jinja2, or HTML.
The report layer renders only from the persisted model. The CLI shell is the
only layer that performs file I/O for outputs.

This separation lets AAFpeek (the paid macOS app) consume the engine + model
layers directly without going through the CLI. **The model is the contract.**

## Modules

- `src/aafinfo/cli.py` — Click command, option validation, terminal output,
  exit-code behavior.
- `src/aafinfo/engine.py` — pyaaf2-backed extraction. Walks composition,
  tracks, segments, source clips, source mobs, markers. Builds and returns a
  `ReportModel`. Public entry point: `build_report(path: Path) -> ReportModel`.
- `src/aafinfo/models.py` — Pydantic v2 models with `extra="forbid"`.
  Top-level `ReportModel` plus nested types: `InputInfo`, `CompositionSummary`,
  `SourceProperties`, `TrackEntry`, `ClipEntry`, `SourceMobEntry`,
  `MarkerEntry`, `Warning`. `schema_version: 2`.
- `src/aafinfo/report.py` — Jinja2 HTML rendering. Loads template, inlines
  CSS, produces a single self-contained `.html` file from a `ReportModel`.
- `src/aafinfo/templates/report.html.j2` — single Jinja2 template.
- `src/aafinfo/_static/report.css` — inlined into the rendered HTML at render
  time inside a `<style>` tag.
- `src/aafinfo/errors.py` — user-facing error types: `AAFInfoError`,
  `UnreadableFileError`, `UnsupportedAAFError`.
- `src/aafinfo/formatting.py` — formatters for timecode strings, durations,
  channel formats, basenames, byte sizes.

`aafinfo/__init__.py` re-exports `build_report` and `ReportModel` for
library consumers (i.e. AAFpeek).

Supporting:

- `tests/` — pytest, unit and integration coverage.
- `examples/_generate.py` — programmatically generates small deterministic
  AAF fixtures using pyaaf2's write side. No bundled real-show material.
- `examples/_smoke.py` — runs the CLI against generated fixtures end-to-end.
- `.github/workflows/ci.yml` — CI on Python 3.11 and 3.12.

## CLI

Single-command shape. No subcommands.

```
uv run aafinfo <file.aaf> [--out <dir>] [--json-only] [--filter <text>]
                          [--no-clips] [--name <slug>] [--version]
```

Flags:

- `<file.aaf>` — required, positional. Path to the input AAF.
- `--out <dir>` — directory for report artifacts. Default: `./aafinfo-report/`.
- `--json-only` — write nothing; print JSON to stdout. Mutually exclusive
  with `--out`.
- `--filter <text>` — case-insensitive substring filter applied to the HTML
  report's clips table (matches against track name, clip name, source
  basename). Filtering is render-time only; the JSON report always contains
  everything.
- `--no-clips` — exclude the per-clip table from the HTML report. Useful for
  long sessions. JSON unaffected.
- `--name <slug>` — explicit slug for output filenames; otherwise derived
  from the input filename.
- `--version` — print version and exit.

Exit codes:

- `0` — file parsed successfully, report written or printed.
- `1` — reserved (currently unused).
- `2` — file unreadable, unsupported, or runtime error.

## Output Artifacts

Default `--out` directory is `./aafinfo-report/`. Artifact names are derived
from the input filename:

- `<slug>-report.json`
- `<slug>-report.html`

If a stable slug cannot be derived, fall back to `report.json` /
`report.html`. On collision, write a numbered sibling
(`<slug>-report-01.html`) instead of overwriting.

## JSON Report

Schema version: `2`.

Top-level shape:

```jsonc
{
  "schema_version": 2,
  "aafinfo_version": "0.1.0",
  "run_id": "uuid",
  "run_started_at": "ISO-8601",
  "input": {
    "path": "/abs/path/to/file.aaf",
    "basename": "file.aaf",
    "size_bytes": 1234567,
    "sha256": "lower-case-hex"
  },
  "source_properties": {
    "name": "exported composition name",
    "file_type": "AAF File",
    "start_timecode": "00:59:50;00",
    "timecode_format": "29.97 fps drop",
    "created_by": "Avid Media Composer 24.12.1",
    "audio_bit_depths": [24],
    "audio_sample_rates": [48000],
    "audio_file_types": ["Embedded"],
    "video_frame_rate": "29.97 fps"
  },
  "composition": {
    "name": "...",
    "edit_rate": "25/1",
    "edit_rate_decimal": 25.0,
    "length_edit_units": 1234,
    "length_timecode": "01:00:00:00",
    "track_count": 8,
    "marker_count": 12
  },
  "tracks": [
    {
      "index": 1,
      "name": "Audio 1",
      "kind": "audio",
      "channel_format": "mono",
      "channel_count": 1,
      "length_edit_units": 1234,
      "length_timecode": "01:00:00:00",
      "clip_count": 42
    }
  ],
  "clips": [
    {
      "track_index": 1,
      "clip_index": 0,
      "name": "...",
      "source_basename": "...",
      "source_mob_id": "...",
      "in_edit_units": 0,
      "out_edit_units": 240,
      "in_timecode": "01:00:00:00",
      "out_timecode": "01:00:10:00",
      "duration_timecode": "00:00:10:00",
      "fade_in_edit_units": 12,
      "fade_out_edit_units": 12,
      "comment": null
    }
  ],
  "source_mobs": [
    {
      "mob_id": "...",
      "name": "...",
      "kind": "audio",
      "is_embedded": false,
      "linked_paths": ["/abs/path/to/external.wav"],
      "sample_rate": 48000,
      "bit_depth": 24,
      "channel_count": 2,
      "length_edit_units": 480000
    }
  ],
  "markers": [
    {
      "track_index": 1,
      "name": "scene 12",
      "comment": "...",
      "position_edit_units": 24000,
      "position_timecode": "01:01:00:00",
      "color": "red"
    }
  ],
  "warnings": [
    { "code": "...", "message": "..." }
  ]
}
```

Field rules:

- `kind` for tracks: `"audio" | "video" | "timecode" | "other"`.
- `channel_format`: `"mono" | "stereo" | "5.0" | "5.1" | "7.1" | "multi"`.
- `kind` for source mobs: `"audio" | "video" | "other"`.
- `edit_rate` is always a string fraction (e.g. `"24000/1001"`) so non-integer
  rates round-trip losslessly. `edit_rate_decimal` is convenience-only.
- All timecode strings derive from edit units and the composition's edit rate
  using exact rational arithmetic. No premature rounding.

`extra="forbid"` is enforced on every model. New fields require a
`schema_version` bump.

## HTML Report

Self-contained. Inline `<style>`. No external assets, no network fonts, no
JavaScript. Open in any browser, email it, archive it next to the AAF.

**Aesthetic: factual datasheet.** Monospace where appropriate (paths, mob
IDs, edit rates, timecodes), proportional elsewhere. Tight tables. Restrained
color (neutral grayscale plus a single accent for warnings or counts).
Visual continuity with FinalPass reports is desirable but not required.
Cold and readable, not warm or inviting.

Sections, in order:

1. **Header** — input filename, full path, file size, SHA-256, AAF version
   if extractable, run timestamp, AAFinfo version, run id.
2. **Composition summary** — name, edit rate, total length (edit units +
   timecode), track count, marker count.
3. **Tracks** — table: index, name, kind, channel format, length, clip count.
4. **Clips** — table: track, clip name, source basename, in TC, out TC,
   duration, fade in/out. Filtered by `--filter` if provided. Hidden by
   `--no-clips`.
5. **Source mobs** — registry: mob id (truncated), name, embedded vs linked,
   external path basename(s) with full path on hover/title, sample rate,
   bit depth, channels, length.
6. **Markers** — table: track, position TC, name, comment, color chip.
7. **Warnings** — bulleted list of any structural issues encountered during
   parsing. Empty section if none, but the section header is always present.

The HTML must:

- Display basenames in primary tables, with full paths only in the source
  mob registry and on `title` hover attributes elsewhere.
- Use fixed-width fonts for paths, mob IDs, timecodes, edit rates.
- Be printable: include `@media print` styles that hide nothing essential and
  produce a usable PDF when a browser prints the page.

## Engine Behavior

The pyaaf2 walk should:

- Open the file in read-only mode.
- Walk the top-level composition mob; one composition per file is the
  expected case. If multiple are present, report the first and list others
  as a warning.
- For each track, resolve its segment(s) and enumerate operation groups,
  source clips, transitions, and filler.
- For each source clip, resolve to its source mob and capture the source
  basename, mob id, and sample/channel info if extractable.
- Capture markers as encountered on tracks or at composition level.
- Treat any pyaaf2 exception during a per-track or per-clip walk as a
  `warnings[]` entry, not a hard failure. Continue with the rest of the
  file. A warning is preferable to an empty report.
- Treat a top-level open failure as a hard error (exit 2).

Timecode strings are derived from edit units and the composition's edit
rate. If edit rate is non-integer (e.g. 24000/1001), use exact rational
arithmetic for sample-accurate strings; never round prematurely.

## Dependencies

- `pyaaf2` — pinned to a fork until upstream PRs land. In `pyproject.toml`:

  ```toml
  [tool.uv.sources]
  pyaaf2 = { git = "https://github.com/alexeymohr/pyaaf2.git", rev = "<commit-sha>" }
  ```

  README documents the open PRs and the path back to upstream.
- `pydantic` v2.
- `click`.
- `jinja2`.
- `pytest`, `pytest-cov` (dev only).
- `uv` for environment and lock management.

No runtime network calls. No optional cloud features. No analytics.

## Testing

- Unit tests for: model validation, formatters, slug derivation, edit-rate
  rational arithmetic, source-mob resolution.
- Integration tests for: end-to-end CLI runs against fixtures, JSON schema
  shape, HTML rendering completeness.
- Fixtures generated programmatically via pyaaf2's write side at test time
  (`examples/_generate.py`). No bundled real-show AAFs in version control.
- CI runs the example smoke flow and pytest on Python 3.11 and 3.12.

## License

MIT. See `LICENSE`.
