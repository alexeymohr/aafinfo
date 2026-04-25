from __future__ import annotations

from pathlib import Path

from aafinfo.models import ReportModel


def build_report(path: Path) -> ReportModel:
    """Build a structured report for an AAF file."""
    _ = path
    raise NotImplementedError("AAF extraction starts in Phase 2.")
