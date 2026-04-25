from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aafinfo.formatting import byte_size, display_basename
from aafinfo.models import ClipEntry, ReportModel, SourceMobEntry


_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _PACKAGE_DIR / "templates"
_STATIC_DIR = _PACKAGE_DIR / "_static"


@dataclass(frozen=True)
class PathDisplay:
    basename: str
    full_path: str


@dataclass(frozen=True)
class ClipRow:
    clip: ClipEntry
    track_name: str
    source_title: str
    fade_in: str
    fade_out: str


@dataclass(frozen=True)
class SourceMobRow:
    source: SourceMobEntry
    short_mob_id: str
    linked_paths: list[PathDisplay]
    status: str
    sample_rate: str
    bit_depth: str
    channel_count: str
    length_edit_units: str


def render_html(
    report: ReportModel,
    *,
    filter_text: str | None = None,
    include_clips: bool = True,
) -> str:
    """Render a self-contained HTML report."""
    css = (_STATIC_DIR / "report.css").read_text(encoding="utf-8")
    template = _environment().get_template("report.html.j2")
    source_mobs_by_id = {source.mob_id: source for source in report.source_mobs}
    all_clip_rows = _clip_rows(report.clips, report, source_mobs_by_id)
    visible_clip_rows = _filter_clip_rows(all_clip_rows, filter_text)

    return template.render(
        css=css,
        report=report,
        input_size=byte_size(report.input.size_bytes),
        aaf_version="Unavailable",
        include_clips=include_clips,
        filter_text=(filter_text or "").strip(),
        clip_rows=visible_clip_rows,
        clip_count_total=len(all_clip_rows),
        clip_count_visible=len(visible_clip_rows),
        source_rows=_source_rows(report.source_mobs),
    )


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(enabled_extensions=("html", "j2")),
    )


def _clip_rows(
    clips: list[ClipEntry],
    report: ReportModel,
    source_mobs_by_id: dict[str, SourceMobEntry],
) -> list[ClipRow]:
    track_names = {track.index: track.name for track in report.tracks}
    rows: list[ClipRow] = []
    for clip in clips:
        source = source_mobs_by_id.get(clip.source_mob_id)
        rows.append(
            ClipRow(
                clip=clip,
                track_name=track_names.get(clip.track_index, f"Track {clip.track_index}"),
                source_title=_source_title(source),
                fade_in=_fade_label(clip.fade_in_edit_units),
                fade_out=_fade_label(clip.fade_out_edit_units),
            )
        )
    return rows


def _filter_clip_rows(rows: list[ClipRow], filter_text: str | None) -> list[ClipRow]:
    needle = (filter_text or "").strip().casefold()
    if not needle:
        return rows

    return [
        row
        for row in rows
        if needle in row.track_name.casefold()
        or needle in row.clip.name.casefold()
        or needle in row.clip.source_basename.casefold()
    ]


def _source_rows(source_mobs: list[SourceMobEntry]) -> list[SourceMobRow]:
    return [
        SourceMobRow(
            source=source,
            short_mob_id=_short_mob_id(source.mob_id),
            linked_paths=[
                PathDisplay(basename=display_basename(path), full_path=path)
                for path in source.linked_paths
            ],
            status="Embedded" if source.is_embedded else "Linked",
            sample_rate=_optional_int(source.sample_rate, suffix=" Hz"),
            bit_depth=_optional_int(source.bit_depth, suffix=" bit"),
            channel_count=_optional_int(source.channel_count),
            length_edit_units=_optional_int(source.length_edit_units),
        )
        for source in source_mobs
    ]


def _source_title(source: SourceMobEntry | None) -> str:
    if source is None or not source.linked_paths:
        return ""
    return source.linked_paths[0]


def _fade_label(value: int | None) -> str:
    if value is None:
        return "-"
    return str(value)


def _optional_int(value: int | None, *, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{value}{suffix}"


def _short_mob_id(mob_id: str) -> str:
    if len(mob_id) <= 24:
        return mob_id
    return f"{mob_id[:10]}...{mob_id[-10:]}"
