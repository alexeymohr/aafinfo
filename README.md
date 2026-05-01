# AAFinfo

AAFinfo is a local, read-only command-line inspector for Advanced Authoring
Format (AAF) files. It reads one AAF, builds a schema-versioned report model,
then emits both JSON and a self-contained HTML report.

AAFinfo does not modify input files, write AAFs, call external AAF tools, make
network requests, run telemetry, or fetch remote assets. The HTML report is a
single file with inline CSS and no JavaScript.

## Install

This project uses `uv` and Python 3.11 or newer.

```bash
uv sync --dev --frozen
```

The parser dependency is pinned to upstream `markreidvfx/pyaaf2` tag `v1.7.1`.

## Quick Start

Generate local fixtures:

```bash
uv run python examples/_generate.py
```

Inspect a fixture and write reports:

```bash
uv run aafinfo examples/_generated/simple_stereo.aaf
```

Default output goes to `./aafinfo-report/`:

```text
aafinfo-report/simple-stereo-report.json
aafinfo-report/simple-stereo-report.html
```

Print JSON only:

```bash
uv run aafinfo examples/_generated/simple_stereo.aaf --json
```

Run tests and the smoke flow:

```bash
uv run pytest
uv run python examples/_smoke.py
```

## Command Reference

```bash
uv run aafinfo <file.aaf> [--out <dir>] [--json] [--filter <text>]
                          [--no-clips] [--name <slug>] [--version]
```

Options:

- `--out <dir>`: directory for report artifacts. Defaults to
  `./aafinfo-report/`.
- `--json`: write nothing; print schema-versioned JSON to stdout.
  Mutually exclusive with explicit `--out`. `--json-only` is accepted as a
  synonym.
- `--filter <text>`: case-insensitive substring filter for the HTML clips
  table. It matches track name, clip name, and source basename. JSON still
  contains every clip.
- `--no-clips`: omit the per-clip table from the HTML report. JSON is
  unaffected.
- `--name <slug>`: explicit output filename slug. Without this, the slug is
  derived from the input filename.
- `--version`: print the installed AAFinfo version.

If an output artifact already exists, AAFinfo writes a numbered sibling such as
`simple-stereo-report-01.json` and `simple-stereo-report-01.html`.

## Output

JSON reports use schema version `"2.2"` and include:

- input path, basename, size, and SHA-256
- source properties: name, type, start time, timecode format, creating
  application, audio format summary, and video frame rate
- composition summary
- source-file summary counts under `summary.source_files`, counting only
  `source_mobs[]` entries where `role == "source"` and `has_essence == true`
- tracks
- clips
- source mobs with explicit `role` values: `composition`, `master`, `source`,
  or `unknown`
- source mob file metadata for GUI consumers: `container`, `data_size_bytes`,
  `has_essence`, and `format_summary`
- markers
- warnings

For `source_mobs[]`, `container` is one of `WAV`, `BWF`, `AIFF`, `MP3`, or
`null`; BWF is reported when a WAV `Summary` contains a RIFF `bext` chunk.
`data_size_bytes` is populated only for embedded essence stored in the AAF.
`has_essence` is true when audio sample rate, bit depth, and channel count are
known, and `format_summary` is the display string such as `WAV 24/48`.

HTML reports contain the same report data in this order:

1. Source properties header
2. Report details
3. Tracks
4. Clips
5. Source mobs
6. Markers
7. Warnings

The HTML is designed as a factual datasheet and can be printed to PDF by a
browser. The CLI does not generate PDF files directly.

## Scope

AAFinfo v0.3.1 is the inspection MVP plus additive JSON fields for downstream
consumers such as AAFpeek.

In scope:

- one AAF input at a time
- pyaaf2-backed reading only
- composition, tracks, clips, source mobs, mob roles, source-file summary
  counts, source file format metadata, markers, and warnings
- JSON and self-contained HTML report output
- generated test fixtures only, no real-show media in the repository

Out of scope:

- writing or editing AAFs
- embedded essence extraction
- transition and automation deep parsing
- LibAAF or `aaftool` integration

## Library Use

The engine and model layers are importable without Click or Jinja2 coupling:

```python
from pathlib import Path

from aafinfo import build_report

report = build_report(Path("example.aaf"))
print(report.model_dump(mode="json"))
```

The model layer is the contract for the forthcoming AAFpeek app.

## Development

Useful commands:

```bash
uv run aafinfo --help
uv run python examples/_generate.py
uv run pytest
uv run python examples/_smoke.py
```

CI runs `uv sync --dev --frozen`, `uv run pytest`, and the smoke flow on
Python 3.11 and 3.12.

## License

MIT. See `LICENSE`.
