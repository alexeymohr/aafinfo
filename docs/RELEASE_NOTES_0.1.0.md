# AAFinfo 0.1.0 Release Notes

## Summary

AAFinfo 0.1.0 is the initial inspection MVP. It reads one AAF file locally and
produces both a schema-versioned JSON report and a self-contained HTML report.

## Highlights

- Read-only pyaaf2-backed AAF inspection.
- Schema version 1 Pydantic report model.
- Composition summary, tracks, clips, source mobs, markers, and warnings.
- JSON output for automation and library consumers.
- Self-contained HTML report with inline CSS, no JavaScript, and print styles.
- `--filter` for render-time clip filtering in HTML.
- `--no-clips` for omitting large clip tables from HTML while preserving JSON.
- Generated AAF fixtures and smoke coverage for every fixture.
- CI coverage on Python 3.11 and 3.12.

## Dependency Note

The current parser dependency is pinned to upstream `markreidvfx/pyaaf2` tag
`v1.7.1`. The planned switch to the project fork is tracked in `TODO.md` and is
deferred until the first upstream PR is open.

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

Suggested tag once release approval is explicit:

```bash
git tag -a v0.1.0 -m "Release AAFinfo 0.1.0"
```

Do not push the tag until the release is approved.
