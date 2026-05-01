# AAFinfo 0.2.0 Release Notes

## Summary

AAFinfo 0.2.0 is an additive JSON-schema release for downstream consumers such
as AAFpeek. It keeps the v0.1.0 inspection behavior and adds explicit mob roles,
source-file summary counts, and a `--json` CLI alias.

## Highlights

- Report schema version `"2.1"`.
- Package version `0.2.0`.
- `source_mobs[]` entries now include `role`: `composition`, `master`,
  `source`, or `unknown`.
- New `summary.source_files` aggregate with source file `count`, `embedded`,
  and `linked` counts.
- `--json` is accepted as a synonym for `--json-only`.
- Timeline clip and marker timecodes honor AAF start timecode and drop-frame
  formatting.
- Mixed embedded and linked audio reports both file types.

## Dependency Note

The parser dependency is pinned to upstream `markreidvfx/pyaaf2` tag `v1.7.1`.

## Validation Before Tagging

Run:

```bash
uv sync --dev --frozen
uv run pytest
uv run python examples/_smoke.py
```

Expected result: all tests pass and smoke prints one `ok` line for each
generated fixture.

## Tag

Tag:

```bash
git tag -a v0.2.0 -m "Release AAFinfo 0.2.0"
```
