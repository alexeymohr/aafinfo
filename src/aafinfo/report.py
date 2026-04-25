from __future__ import annotations

from aafinfo.models import ReportModel


def render_html(
    report: ReportModel,
    *,
    filter_text: str | None = None,
    include_clips: bool = True,
) -> str:
    """Render a self-contained HTML report."""
    _ = (report, filter_text, include_clips)
    raise NotImplementedError("HTML rendering starts in Phase 5.")
