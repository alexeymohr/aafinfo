# AAFinfo

AAFinfo is a read-only command-line inspector for Advanced Authoring Format
files. It will emit a schema-versioned JSON report and a self-contained HTML
report for local review.

This repository is currently at Phase 1 of the v0.1.0 build plan: package
skeleton, command-line shell, empty model contracts, and CI wiring.

```bash
uv run aafinfo --help
uv run pytest
```

See `docs/PROJECT_OVERVIEW.md` and `docs/CODEX_HANDOFF.md` for the full scope
and phased implementation plan.
