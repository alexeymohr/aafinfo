from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import uuid4

import aaf2
from aaf2 import components, essence, mobs, mobslots

from aafinfo._version import __version__
from aafinfo.errors import UnreadableFileError, UnsupportedAAFError
from aafinfo.formatting import (
    channel_format,
    display_basename,
    duration_timecode,
    edit_rate_decimal,
    edit_rate_fraction,
    edit_units_to_timecode,
    format_edit_rate,
    frame_rate_label,
    frames_to_timecode,
    timecode_format_label,
)
from aafinfo.models import (
    ClipEntry,
    CompositionSummary,
    InputInfo,
    MarkerEntry,
    ReportModel,
    ReportSummary,
    SourceProperties,
    SourceFilesSummary,
    SourceMobEntry,
    TrackEntry,
    TrackKind,
    Warning as ReportWarning,
)


@dataclass(frozen=True)
class _PositionedClip:
    clip: components.SourceClip
    start_edit_units: int


@dataclass(frozen=True)
class _TimecodeInfo:
    start_frames: int
    fps: int
    drop: bool
    edit_rate: object


_TRACK_FORMAT_CHANNEL_COUNTS = {
    2: 2,
    3: 6,
    4: 8,
}


def build_report(path: Path) -> ReportModel:
    """Build a structured report for an AAF file."""
    input_info = _input_info(path)

    try:
        with aaf2.open(str(Path(input_info.path)), "r") as aaf_file:
            return _build_report(aaf_file, input_info)
    except (UnreadableFileError, UnsupportedAAFError):
        raise
    except OSError as exc:
        raise UnreadableFileError(
            f"Cannot read input AAF: {input_info.path}",
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise UnsupportedAAFError(
            f"Cannot parse input AAF: {input_info.path}",
            detail=str(exc),
        ) from exc


def _input_info(path: Path) -> InputInfo:
    try:
        resolved = path.expanduser().resolve(strict=True)
        stat = resolved.stat()
    except OSError as exc:
        raise UnreadableFileError(
            f"Cannot read input AAF: {path}",
            detail=str(exc),
        ) from exc

    if not resolved.is_file():
        raise UnreadableFileError(
            f"Input path is not a file: {resolved}",
            detail="AAFinfo expects a single AAF file.",
        )

    return InputInfo(
        path=str(resolved),
        basename=resolved.name,
        size_bytes=stat.st_size,
        sha256=_sha256(resolved),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_report(aaf_file: object, input_info: InputInfo) -> ReportModel:
    warnings: list[ReportWarning] = []
    content = aaf_file.content
    embedded_mob_ids = _embedded_mob_ids(content)
    composition = _select_composition(content, warnings)
    edit_rate = _composition_edit_rate(composition, warnings)
    timecode_info = _composition_timecode_info(composition)

    tracks, clips, markers = _extract_composition(
        composition,
        edit_rate,
        timecode_info,
        warnings,
    )
    source_mobs = _extract_source_mobs(content, embedded_mob_ids, warnings)
    source_mobs_by_id = {source.mob_id: source for source in source_mobs}
    clips = [
        _clip_with_source_basename(clip, source_mobs_by_id)
        for clip in clips
    ]

    composition_summary = CompositionSummary(
        name=_safe_text(getattr(composition, "name", None), fallback="Untitled composition"),
        edit_rate=format_edit_rate(edit_rate),
        edit_rate_decimal=edit_rate_decimal(edit_rate),
        length_edit_units=max((track.length_edit_units for track in tracks), default=0),
        length_timecode=edit_units_to_timecode(
            max((track.length_edit_units for track in tracks), default=0),
            edit_rate,
        ),
        track_count=len(tracks),
        marker_count=len(markers),
    )

    return ReportModel(
        aafinfo_version=__version__,
        run_id=str(uuid4()),
        run_started_at=datetime.now(timezone.utc).isoformat(),
        input=input_info,
        source_properties=_source_properties(
            aaf_file,
            composition_summary,
            source_mobs,
            timecode_info,
            composition,
        ),
        composition=composition_summary,
        summary=ReportSummary(source_files=_source_files_summary(source_mobs)),
        tracks=tracks,
        clips=clips,
        source_mobs=sorted(source_mobs, key=lambda source: source.mob_id),
        markers=markers,
        warnings=sorted(warnings, key=lambda warning: (warning.code, warning.message)),
    )


def _select_composition(content: object, warnings: list[ReportWarning]) -> mobs.CompositionMob:
    top_level = list(_safe_iter(content.toplevel()))
    compositions = top_level or list(_safe_iter(content.compositionmobs()))

    if not compositions:
        raise UnsupportedAAFError(
            "No composition mob found in input AAF.",
            detail="Expected at least one CompositionMob.",
        )

    if len(compositions) > 1:
        names = ", ".join(_safe_text(getattr(mob, "name", None)) for mob in compositions[1:])
        warnings.append(
            ReportWarning(
                code="multiple_compositions",
                message=f"Using first composition mob; additional composition mobs ignored: {names}",
            )
        )

    return compositions[0]


def _composition_edit_rate(
    composition: mobs.CompositionMob,
    warnings: list[ReportWarning],
) -> object:
    for slot in _safe_iter(composition.slots):
        edit_rate = _safe_get_value(slot, "EditRate")
        if edit_rate is not None:
            return edit_rate

    warnings.append(
        ReportWarning(
            code="missing_edit_rate",
            message="No timeline edit rate found; using 25/1 for timecode formatting.",
        )
    )
    return 25


def _composition_timecode_info(composition: mobs.CompositionMob) -> _TimecodeInfo | None:
    for slot in _safe_iter(composition.slots):
        if _track_kind(_safe_text(getattr(slot, "media_kind", None))) != "timecode":
            continue

        timecode = _find_timecode_segment(getattr(slot, "segment", None))
        if timecode is None:
            continue

        start = _safe_int(_safe_get_value(timecode, "Start"))
        fps = _safe_int(_safe_get_value(timecode, "FPS"))
        edit_rate = _safe_get_value(slot, "EditRate")
        if start is None or fps is None or edit_rate is None:
            continue

        return _TimecodeInfo(
            start_frames=start,
            fps=fps,
            drop=bool(_safe_get_value(timecode, "Drop")),
            edit_rate=edit_rate,
        )
    return None


def _find_timecode_segment(segment: object, visited: set[int] | None = None) -> components.Timecode | None:
    if segment is None:
        return None

    visited = visited or set()
    identity = id(segment)
    if identity in visited:
        return None
    visited.add(identity)

    if isinstance(segment, components.Timecode):
        return segment

    input_segment = _safe_get_value(segment, "InputSegment")
    timecode = _find_timecode_segment(input_segment, visited)
    if timecode is not None:
        return timecode

    if isinstance(segment, components.Sequence):
        for component in _safe_iter(segment.components):
            timecode = _find_timecode_segment(component, visited)
            if timecode is not None:
                return timecode

    return None


def _source_properties(
    aaf_file: object,
    composition: CompositionSummary,
    source_mobs: list[SourceMobEntry],
    timecode_info: _TimecodeInfo | None,
    composition_mob: mobs.CompositionMob,
) -> SourceProperties:
    return SourceProperties(
        name=composition.name,
        file_type="AAF File",
        start_timecode=_start_timecode_label(timecode_info),
        timecode_format=_timecode_format_label(timecode_info, composition.edit_rate),
        created_by=_created_by(aaf_file),
        audio_bit_depths=_audio_bit_depths(source_mobs),
        audio_sample_rates=_audio_sample_rates(source_mobs),
        audio_file_types=_audio_file_types(source_mobs),
        video_frame_rate=_video_frame_rate(composition_mob, timecode_info, composition.edit_rate),
    )


def _start_timecode_label(timecode_info: _TimecodeInfo | None) -> str | None:
    if timecode_info is None:
        return None
    return frames_to_timecode(
        timecode_info.start_frames,
        timecode_info.fps,
        drop=timecode_info.drop,
    )


def _timecode_format_label(timecode_info: _TimecodeInfo | None, edit_rate: object) -> str:
    if timecode_info is None:
        return timecode_format_label(edit_rate)
    return timecode_format_label(
        timecode_info.edit_rate,
        fps=timecode_info.fps,
        drop=timecode_info.drop,
    )


def _created_by(aaf_file: object) -> str | None:
    identifications = list(_safe_iter(_safe_get_value(getattr(aaf_file, "header", None), "IdentificationList")))
    if not identifications:
        return None

    identification = identifications[-1]
    product_name = _safe_optional_text(_safe_get_value(identification, "ProductName"))
    version = _safe_optional_text(_safe_get_value(identification, "ProductVersionString"))
    company = _safe_optional_text(_safe_get_value(identification, "CompanyName"))
    if product_name and version and version.lower() != "unknown version" and version not in product_name:
        return f"{product_name} {version}"
    if product_name:
        return product_name
    return company


def _audio_bit_depths(source_mobs: list[SourceMobEntry]) -> list[int]:
    return sorted(
        {
            source.bit_depth
            for source in source_mobs
            if source.kind == "audio" and source.bit_depth is not None
        }
    )


def _audio_sample_rates(source_mobs: list[SourceMobEntry]) -> list[int]:
    return sorted(
        {
            source.sample_rate
            for source in source_mobs
            if source.kind == "audio" and source.sample_rate is not None
        }
    )


def _audio_file_types(source_mobs: list[SourceMobEntry]) -> list[str]:
    audio_sources = [source for source in source_mobs if source.kind == "audio"]
    file_types: list[str] = []
    if any(source.is_embedded for source in audio_sources):
        file_types.append("Embedded")
    if any(source.linked_paths for source in audio_sources):
        file_types.append("Linked")
    return file_types


def _source_files_summary(source_mobs: list[SourceMobEntry]) -> SourceFilesSummary:
    source_file_mobs = [source for source in source_mobs if source.role == "source"]
    embedded = sum(1 for source in source_file_mobs if source.is_embedded)
    # Conservative QC default: if a source mob is not proven embedded, assume it is external.
    linked = len(source_file_mobs) - embedded
    return SourceFilesSummary(
        count=len(source_file_mobs),
        embedded=embedded,
        linked=linked,
    )


def _video_frame_rate(
    composition: mobs.CompositionMob,
    timecode_info: _TimecodeInfo | None,
    fallback_edit_rate: object,
) -> str:
    for slot in _safe_iter(composition.slots):
        if _track_kind(_safe_text(getattr(slot, "media_kind", None))) != "video":
            continue
        edit_rate = _safe_get_value(slot, "EditRate")
        if edit_rate is not None:
            return frame_rate_label(edit_rate)

    if timecode_info is not None:
        return frame_rate_label(timecode_info.edit_rate)
    return frame_rate_label(fallback_edit_rate)


def _extract_composition(
    composition: mobs.CompositionMob,
    edit_rate: object,
    timecode_info: _TimecodeInfo | None,
    warnings: list[ReportWarning],
) -> tuple[list[TrackEntry], list[ClipEntry], list[MarkerEntry]]:
    tracks: list[TrackEntry] = []
    clips: list[ClipEntry] = []
    markers: list[MarkerEntry] = []
    physical_to_track: dict[int, int] = {}
    track_slots: list[tuple[int, object]] = []
    marker_slots: list[object] = []

    for slot in _safe_iter(composition.slots):
        if _is_marker_slot(slot):
            marker_slots.append(slot)
            continue

        if not _is_reportable_track_slot(slot):
            continue

        track_index = len(track_slots) + 1
        track_slots.append((track_index, slot))
        physical_number = _safe_int(_safe_get_value(slot, "PhysicalTrackNumber"))
        if physical_number is not None:
            physical_to_track[physical_number] = track_index

    for track_index, slot in track_slots:
        track_kind = _track_kind(_safe_text(getattr(slot, "media_kind", None)))
        track_name = _track_name(slot, track_kind, track_index)
        length_edit_units = max(0, _safe_int(getattr(slot, "length", None)) or 0)
        positioned_clips: list[_PositionedClip] = []

        try:
            positioned_clips = list(_iter_source_clips(getattr(slot, "segment", None), 0))
        except Exception as exc:
            warnings.append(
                ReportWarning(
                    code="track_walk_failed",
                    message=f"Track {track_index} could not be fully walked: {exc}",
                )
            )

        track_clip_entries: list[ClipEntry] = []
        source_channel_counts: list[int] = []
        for clip_index, positioned in enumerate(positioned_clips):
            try:
                clip_entry, channel_count = _clip_entry(
                    positioned,
                    track_index,
                    clip_index,
                    edit_rate,
                    timecode_info,
                    warnings,
                )
            except Exception as exc:
                warnings.append(
                    ReportWarning(
                        code="clip_walk_failed",
                        message=f"Track {track_index} clip {clip_index} could not be read: {exc}",
                    )
                )
                continue

            track_clip_entries.append(clip_entry)
            if channel_count is not None:
                source_channel_counts.append(channel_count)

        track_channel_count = _track_channel_count(slot, track_kind, source_channel_counts)
        tracks.append(
            TrackEntry(
                index=track_index,
                name=track_name,
                kind=track_kind,
                channel_format=channel_format(track_channel_count),
                channel_count=track_channel_count,
                length_edit_units=length_edit_units,
                length_timecode=edit_units_to_timecode(length_edit_units, edit_rate),
                clip_count=len(track_clip_entries),
            )
        )
        clips.extend(track_clip_entries)
        markers.extend(
            _extract_markers(
                slot,
                track_index,
                edit_rate,
                timecode_info,
                physical_to_track,
                warnings,
            )
        )

    for slot in marker_slots:
        markers.extend(
            _extract_markers(
                slot,
                None,
                edit_rate,
                timecode_info,
                physical_to_track,
                warnings,
            )
        )

    return tracks, clips, markers


def _is_marker_slot(slot: object) -> bool:
    media_kind = _safe_text(getattr(slot, "media_kind", None)).lower()
    return isinstance(slot, mobslots.EventMobSlot) or media_kind == "descriptivemetadata"


def _is_reportable_track_slot(slot: object) -> bool:
    return _track_kind(_safe_text(getattr(slot, "media_kind", None))) in {"audio", "video"}


def _track_kind(media_kind: str) -> TrackKind:
    normalized = media_kind.lower()
    if normalized == "sound":
        return "audio"
    if normalized == "picture":
        return "video"
    if normalized == "timecode":
        return "timecode"
    return "other"


def _track_name(slot: object, track_kind: TrackKind, track_index: int) -> str:
    name = _safe_optional_text(getattr(slot, "name", None))
    if name is not None:
        return name

    physical_number = _safe_int(_safe_get_value(slot, "PhysicalTrackNumber"))
    if track_kind == "audio" and physical_number is not None:
        return f"A{physical_number}"
    if track_kind == "video" and physical_number is not None:
        return f"V{physical_number}"
    return f"Track {track_index}"


def _track_channel_count(
    slot: object,
    track_kind: TrackKind,
    source_channel_counts: Sequence[int],
) -> int:
    if track_kind != "audio":
        return 0

    track_format_count = _track_format_channel_count(slot)
    if track_format_count is not None:
        return track_format_count

    combiner_count = _audio_channel_combiner_channel_count(getattr(slot, "segment", None))
    if combiner_count is not None:
        return combiner_count

    if source_channel_counts:
        return max(source_channel_counts)

    return 1


def _track_format_channel_count(slot: object) -> int | None:
    for tagged_value in _safe_iter(_safe_get_value(slot, "TimelineMobAttributeList")):
        name = _safe_text(_safe_get_value(tagged_value, "Name"))
        if name != "_TRACK_FORMAT":
            continue

        track_format = _safe_int(_safe_get_value(tagged_value, "Value"))
        if track_format is None:
            continue
        return _TRACK_FORMAT_CHANNEL_COUNTS.get(track_format)
    return None


def _audio_channel_combiner_channel_count(
    segment: object,
    visited: set[int] | None = None,
) -> int | None:
    if segment is None:
        return None

    visited = visited or set()
    identity = id(segment)
    if identity in visited:
        return None
    visited.add(identity)

    if isinstance(segment, components.OperationGroup):
        children = list(_safe_iter(getattr(segment, "segments", [])))
        if _is_audio_channel_combiner(segment):
            channels = sum(1 for child in children if _segment_contains_source_clip(child))
            return channels or (len(children) if children else None)

        counts = [
            count
            for child in children
            if (count := _audio_channel_combiner_channel_count(child, visited)) is not None
        ]
        return max(counts, default=None)

    if isinstance(segment, components.Sequence):
        counts = [
            count
            for component in _safe_iter(segment.components)
            if (count := _audio_channel_combiner_channel_count(component, visited)) is not None
        ]
        return max(counts, default=None)

    if isinstance(segment, components.NestedScope):
        counts = [
            count
            for nested_slot in _safe_iter(segment.slots)
            if (
                count := _audio_channel_combiner_channel_count(
                    getattr(nested_slot, "segment", None),
                    visited,
                )
            )
            is not None
        ]
        return max(counts, default=None)

    if isinstance(segment, components.EssenceGroup):
        counts = [
            count
            for choice in _safe_iter(_safe_get_value(segment, "Choices") or [])
            if (count := _audio_channel_combiner_channel_count(choice, visited)) is not None
        ]
        selected = _audio_channel_combiner_channel_count(
            _safe_get_value(segment, "Selected"),
            visited,
        )
        if selected is not None:
            counts.append(selected)
        return max(counts, default=None)

    selected = _safe_get_value(segment, "Selected")
    if selected is not None:
        return _audio_channel_combiner_channel_count(selected, visited)

    return None


def _is_audio_channel_combiner(segment: components.OperationGroup) -> bool:
    operation = _safe_get_value(segment, "Operation") or getattr(segment, "operation", None)
    operation_name = _safe_text(getattr(operation, "name", None)) or _safe_text(
        _safe_get_value(operation, "Name")
    )
    return operation_name.lower() == "audio channel combiner"


def _segment_contains_source_clip(segment: object, visited: set[int] | None = None) -> bool:
    if segment is None:
        return False

    visited = visited or set()
    identity = id(segment)
    if identity in visited:
        return False
    visited.add(identity)

    if isinstance(segment, components.SourceClip):
        return True

    if isinstance(segment, components.Sequence):
        return any(
            _segment_contains_source_clip(component, visited)
            for component in _safe_iter(segment.components)
        )

    if isinstance(segment, components.OperationGroup):
        return any(
            _segment_contains_source_clip(child, visited)
            for child in _safe_iter(getattr(segment, "segments", []))
        )

    if isinstance(segment, components.NestedScope):
        return any(
            _segment_contains_source_clip(getattr(nested_slot, "segment", None), visited)
            for nested_slot in _safe_iter(segment.slots)
        )

    if isinstance(segment, components.EssenceGroup):
        return any(
            _segment_contains_source_clip(choice, visited)
            for choice in _safe_iter(_safe_get_value(segment, "Choices") or [])
        ) or _segment_contains_source_clip(_safe_get_value(segment, "Selected"), visited)

    selected = _safe_get_value(segment, "Selected")
    return selected is not None and _segment_contains_source_clip(selected, visited)


def _iter_source_clips(
    segment: object,
    base_edit_units: int,
    visited: set[int] | None = None,
) -> Iterator[_PositionedClip]:
    if segment is None:
        return

    visited = visited or set()
    identity = id(segment)
    if identity in visited:
        return
    visited.add(identity)

    if isinstance(segment, components.SourceClip):
        yield _PositionedClip(segment, base_edit_units)
        return

    if isinstance(segment, components.Sequence):
        for _, position, component in segment.positions():
            yield from _iter_source_clips(component, base_edit_units + int(position), visited)
        return

    if isinstance(segment, components.OperationGroup):
        for child in _safe_iter(getattr(segment, "segments", [])):
            yield from _iter_source_clips(child, base_edit_units, visited)
        return

    if isinstance(segment, components.NestedScope):
        for slot in _safe_iter(segment.slots):
            yield from _iter_source_clips(getattr(slot, "segment", None), base_edit_units, visited)
        return

    if isinstance(segment, components.EssenceGroup):
        for choice in _safe_iter(_safe_get_value(segment, "Choices") or []):
            yield from _iter_source_clips(choice, base_edit_units, visited)
        return

    selected = _safe_get_value(segment, "Selected")
    if selected is not None:
        yield from _iter_source_clips(selected, base_edit_units, visited)


def _clip_entry(
    positioned: _PositionedClip,
    track_index: int,
    clip_index: int,
    edit_rate: object,
    timecode_info: _TimecodeInfo | None,
    warnings: list[ReportWarning],
) -> tuple[ClipEntry, int | None]:
    clip = positioned.clip
    source_mob = _resolve_source_mob(clip, warnings, f"track {track_index} clip {clip_index}")
    source_description = (
        _source_mob_entry(source_mob, set(), warnings)
        if source_mob is not None
        else None
    )
    source_mob_id = source_description.mob_id if source_description is not None else ""
    source_basename = _source_basename(source_description)
    duration = max(0, _safe_int(getattr(clip, "length", None)) or 0)
    start = max(0, positioned.start_edit_units)
    end = start + duration

    name = _safe_text(_safe_get_value(clip, "Name"), fallback=source_basename or f"Clip {clip_index}")

    return (
        ClipEntry(
            track_index=track_index,
            clip_index=clip_index,
            name=name,
            source_basename=source_basename,
            source_mob_id=source_mob_id,
            in_edit_units=start,
            out_edit_units=end,
            in_timecode=_timeline_position_timecode(start, edit_rate, timecode_info),
            out_timecode=_timeline_position_timecode(end, edit_rate, timecode_info),
            duration_timecode=duration_timecode(duration, edit_rate),
            fade_in_edit_units=_safe_int(_safe_get_value(clip, "FadeInLength")),
            fade_out_edit_units=_safe_int(_safe_get_value(clip, "FadeOutLength")),
            comment=_safe_optional_text(_safe_get_value(clip, "Comment")),
        ),
        source_description.channel_count if source_description is not None else None,
    )


def _resolve_source_mob(
    clip: components.SourceClip,
    warnings: list[ReportWarning],
    context: str,
) -> mobs.SourceMob | None:
    source_mobs: list[mobs.SourceMob] = []
    _append_source_mob(source_mobs, _safe_mob(clip))

    try:
        for referenced in clip.walk():
            if isinstance(referenced, components.SourceClip):
                _append_source_mob(source_mobs, _safe_mob(referenced))
    except Exception as exc:
        warnings.append(
            ReportWarning(
                code="source_resolution_incomplete",
                message=f"Source resolution incomplete for {context}: {exc}",
            )
        )

    return source_mobs[-1] if source_mobs else None


def _append_source_mob(source_mobs: list[mobs.SourceMob], mob: object | None) -> None:
    if isinstance(mob, mobs.SourceMob):
        source_mobs.append(mob)


def _safe_mob(clip: components.SourceClip) -> object | None:
    try:
        return clip.mob
    except Exception:
        return None


def _extract_source_mobs(
    content: object,
    embedded_mob_ids: set[str],
    warnings: list[ReportWarning],
) -> list[SourceMobEntry]:
    source_mobs: list[SourceMobEntry] = []
    for mob in _safe_iter(getattr(content, "mobs", [])):
        try:
            source_mobs.append(_source_mob_entry(mob, embedded_mob_ids, warnings))
        except Exception as exc:
            warnings.append(
                ReportWarning(
                    code="source_mob_failed",
                    message=f"Source mob could not be summarized: {exc}",
                )
            )
    return source_mobs


def _source_mob_entry(
    mob: object,
    embedded_mob_ids: set[str],
    warnings: list[ReportWarning],
) -> SourceMobEntry:
    role = _mob_role(mob, warnings)
    descriptor = _safe_get_value(mob, "EssenceDescription")
    descriptors = list(_descriptor_tree(descriptor))
    wav_summaries = [
        summary
        for summary in (_wav_summary(_safe_get_value(desc, "Summary")) for desc in descriptors)
        if summary
    ]
    slot_lengths = [
        _safe_int(getattr(slot, "length", None))
        for slot in _safe_iter(getattr(mob, "slots", []))
    ]
    slot_media_kinds = [
        _safe_text(getattr(slot, "media_kind", None))
        for slot in _safe_iter(getattr(mob, "slots", []))
    ]

    channel_counts = [
        count
        for count in (_safe_int(_safe_get_value(desc, "Channels")) for desc in descriptors)
        if count is not None
    ]
    if not channel_counts:
        channel_counts = [
            summary["channels"]
            for summary in wav_summaries
            if "channels" in summary
        ]
    linked_paths = sorted(
        {
            path
            for desc in descriptors
            for path in _descriptor_paths(desc)
            if path
        }
    )
    mob_id = str(getattr(mob, "mob_id", ""))

    return SourceMobEntry(
        mob_id=mob_id,
        name=_safe_text(getattr(mob, "name", None), fallback="Source mob"),
        role=role,
        kind=_source_mob_kind(descriptors, slot_media_kinds),
        is_embedded=mob_id in embedded_mob_ids,
        linked_paths=linked_paths,
        sample_rate=(
            _first_int_property(descriptors, ("AudioSamplingRate", "SampleRate"))
            or _first_summary_value(wav_summaries, "sample_rate")
        ),
        bit_depth=(
            _first_int_property(descriptors, ("QuantizationBits", "BitsPerSample"))
            or _first_summary_value(wav_summaries, "bit_depth")
        ),
        channel_count=sum(channel_counts) if len(channel_counts) > 1 else (channel_counts[0] if channel_counts else None),
        length_edit_units=(
            _first_int_property(descriptors, ("Length",))
            or max((length for length in slot_lengths if length is not None), default=None)
        ),
    )


def _mob_role(mob: object, warnings: list[ReportWarning]) -> str:
    if isinstance(mob, mobs.CompositionMob):
        return "composition"
    if isinstance(mob, mobs.MasterMob):
        return "master"
    if isinstance(mob, mobs.SourceMob):
        return "source"

    mob_id = _safe_text(getattr(mob, "mob_id", None), fallback="unknown mob id")
    warnings.append(
        ReportWarning(
            code="unknown_mob_role",
            message=f"Mob {mob_id} has unknown role {type(mob).__name__}.",
        )
    )
    return "unknown"


def _source_mob_kind(descriptors: Sequence[object], slot_media_kinds: Sequence[str]) -> str:
    media_kinds = {kind.lower() for kind in slot_media_kinds}
    if "sound" in media_kinds:
        return "audio"
    if "picture" in media_kinds:
        return "video"

    if any(isinstance(desc, essence.SoundDescriptor) for desc in descriptors):
        return "audio"
    if any(isinstance(desc, essence.DigitalImageDescriptor) for desc in descriptors):
        return "video"
    return "other"


def _descriptor_tree(descriptor: object | None) -> Iterator[object]:
    if descriptor is None:
        return

    yield descriptor
    for child in _safe_iter(_safe_get_value(descriptor, "FileDescriptors") or []):
        yield from _descriptor_tree(child)


def _descriptor_paths(descriptor: object) -> Iterator[str]:
    for locator in _safe_iter(_safe_get_value(descriptor, "Locator") or []):
        url = _safe_get_value(locator, "URLString")
        name = _safe_get_value(locator, "Name")
        path = _safe_optional_text(url) or _safe_optional_text(name)
        if path:
            yield path


def _source_basename(source_description: SourceMobEntry | None) -> str:
    if source_description is None:
        return ""
    if source_description.linked_paths:
        return display_basename(source_description.linked_paths[0])
    return source_description.name


def _clip_with_source_basename(
    clip: ClipEntry,
    source_mobs_by_id: dict[str, SourceMobEntry],
) -> ClipEntry:
    if clip.source_basename:
        return clip

    source = source_mobs_by_id.get(clip.source_mob_id)
    return clip.model_copy(update={"source_basename": _source_basename(source)})


def _extract_markers(
    slot: object,
    track_index: int | None,
    edit_rate: object,
    timecode_info: _TimecodeInfo | None,
    physical_to_track: dict[int, int],
    warnings: list[ReportWarning],
) -> list[MarkerEntry]:
    markers: list[MarkerEntry] = []
    try:
        for marker in _iter_markers(getattr(slot, "segment", None)):
            physical_number = _safe_int(_safe_get_value(slot, "PhysicalTrackNumber"))
            marker_track_index = track_index
            if marker_track_index is None and physical_number is not None:
                marker_track_index = physical_to_track.get(physical_number)

            position = max(0, _safe_int(_safe_get_value(marker, "Position")) or 0)
            comment = _safe_optional_text(_safe_get_value(marker, "Comment"))
            name = _safe_optional_text(_safe_get_value(marker, "Name")) or comment or "Marker"
            markers.append(
                MarkerEntry(
                    track_index=marker_track_index,
                    name=name,
                    comment=comment,
                    position_edit_units=position,
                    position_timecode=_timeline_position_timecode(
                        position,
                        edit_rate,
                        timecode_info,
                    ),
                    color=_safe_optional_text(_safe_get_value(marker, "CommentMarkerColor")),
                )
            )
    except Exception as exc:
        warnings.append(
            ReportWarning(
                code="marker_walk_failed",
                message=f"Markers could not be fully walked: {exc}",
            )
        )
    return markers


def _timeline_position_timecode(
    edit_units: int,
    edit_rate: object,
    timecode_info: _TimecodeInfo | None,
) -> str:
    if timecode_info is None:
        return edit_units_to_timecode(edit_units, edit_rate)

    frame_offset = _timeline_frame_offset(edit_units, edit_rate, timecode_info.edit_rate)
    return frames_to_timecode(
        timecode_info.start_frames + frame_offset,
        timecode_info.fps,
        drop=timecode_info.drop,
    )


def _timeline_frame_offset(edit_units: int, edit_rate: object, timecode_edit_rate: object) -> int:
    source_rate = edit_rate_fraction(edit_rate)
    target_rate = edit_rate_fraction(timecode_edit_rate)
    if source_rate <= 0 or target_rate <= 0:
        return 0

    return int(edit_units * target_rate / source_rate)


def _iter_markers(segment: object, visited: set[int] | None = None) -> Iterator[components.CommentMarker]:
    if segment is None:
        return

    visited = visited or set()
    identity = id(segment)
    if identity in visited:
        return
    visited.add(identity)

    if isinstance(segment, components.CommentMarker):
        yield segment
        return

    if isinstance(segment, components.Sequence):
        for component in _safe_iter(segment.components):
            yield from _iter_markers(component, visited)
        return

    if isinstance(segment, components.NestedScope):
        for nested_slot in _safe_iter(segment.slots):
            yield from _iter_markers(getattr(nested_slot, "segment", None), visited)
        return

    if isinstance(segment, components.OperationGroup):
        for child in _safe_iter(getattr(segment, "segments", [])):
            yield from _iter_markers(child, visited)


def _embedded_mob_ids(content: object) -> set[str]:
    ids: set[str] = set()
    for essence_data in _safe_iter(getattr(content, "essencedata", [])):
        mob_id = _safe_get_value(essence_data, "MobID")
        if mob_id is not None:
            ids.add(str(mob_id))
    return ids


def _first_int_property(descriptors: Sequence[object], names: Sequence[str]) -> int | None:
    for descriptor in descriptors:
        for name in names:
            value = _safe_int(_safe_get_value(descriptor, name))
            if value is not None:
                return value
    return None


def _first_summary_value(summaries: Sequence[dict[str, int]], key: str) -> int | None:
    for summary in summaries:
        value = summary.get(key)
        if value is not None:
            return value
    return None


def _wav_summary(value: object) -> dict[str, int]:
    if value is None:
        return {}

    try:
        data = bytes(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {}

    if len(data) < 36 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return {}

    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        chunk_size = int.from_bytes(data[offset + 4:offset + 8], "little")
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_id == b"fmt " and chunk_size >= 16 and chunk_end <= len(data):
            return {
                "channels": int.from_bytes(data[chunk_start + 2:chunk_start + 4], "little"),
                "sample_rate": int.from_bytes(data[chunk_start + 4:chunk_start + 8], "little"),
                "bit_depth": int.from_bytes(data[chunk_start + 14:chunk_start + 16], "little"),
            }
        offset = chunk_end + (chunk_size % 2)
    return {}


def _safe_int(value: object) -> int | None:
    if value is None:
        return None

    try:
        fraction = edit_rate_fraction(value)
    except (TypeError, ValueError, ZeroDivisionError):
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    if fraction.denominator == 1:
        return fraction.numerator
    return int(float(fraction))


def _safe_text(value: object, *, fallback: str = "") -> str:
    text = _safe_optional_text(value)
    return text if text is not None else fallback


def _safe_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _safe_get_value(obj: object, key: str) -> object | None:
    if obj is None:
        return None
    try:
        if hasattr(obj, "getvalue"):
            return obj.getvalue(key, None)
        if hasattr(obj, "get"):
            prop = obj.get(key, None)
            return getattr(prop, "value", None)
    except Exception:
        return None
    return None


def _safe_iter(values: Iterable[object] | None) -> Iterator[object]:
    if values is None:
        return iter(())
    try:
        return iter(values)
    except TypeError:
        return iter(())
