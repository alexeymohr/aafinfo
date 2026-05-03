from __future__ import annotations

import pytest
from pydantic import ValidationError

from aafinfo.models import (
    ClipEntry,
    CompositionSummary,
    InputInfo,
    MarkerEntry,
    ReportModel,
    ReportSummary,
    SourceFilesSummary,
    SourceMobEntry,
    SourceProperties,
    TrackEntry,
    Warning,
)


def sample_report() -> ReportModel:
    return ReportModel(
        aafinfo_version="0.4.0",
        run_id="00000000-0000-0000-0000-000000000000",
        run_started_at="2026-04-24T00:00:00+00:00",
        input=InputInfo(
            path="/tmp/example.aaf",
            basename="example.aaf",
            size_bytes=12,
            sha256="0" * 64,
        ),
        source_properties=SourceProperties(
            name="Example",
            file_type="AAF File",
            start_timecode="00:59:50;00",
            timecode_format="29.97 fps drop",
            created_by="Avid Media Composer 24.12.1",
            audio_bit_depths=[24],
            audio_sample_rates=[48000],
            audio_file_types=["Embedded"],
            video_frame_rate="29.97 fps",
        ),
        composition=CompositionSummary(
            name="Example",
            edit_rate="25/1",
            edit_rate_decimal=25.0,
            length_edit_units=100,
            length_timecode="00:00:04:00",
            track_count=1,
            marker_count=1,
        ),
        summary=ReportSummary(
            source_files=SourceFilesSummary(
                count=1,
                embedded=0,
                linked=1,
            )
        ),
        tracks=[
            TrackEntry(
                index=1,
                name="A1",
                kind="audio",
                channel_format="mono",
                channel_count=1,
                length_edit_units=100,
                length_timecode="00:00:04:00",
                clip_count=1,
            )
        ],
        clips=[
            ClipEntry(
                track_index=1,
                clip_index=0,
                name="Clip",
                source_basename="source.wav",
                source_file_name="source.wav",
                source_mob_id="mob-id",
                in_edit_units=0,
                out_edit_units=100,
                in_timecode="00:00:00:00",
                out_timecode="00:00:04:00",
                duration_timecode="00:00:04:00",
                fade_in_edit_units=None,
                fade_out_edit_units=None,
                comment=None,
            )
        ],
        source_mobs=[
            SourceMobEntry(
                mob_id="mob-id",
                name="source.wav",
                name_source="locator",
                role="source",
                kind="audio",
                is_embedded=False,
                linked_paths=["/tmp/source.wav"],
                container="WAV",
                data_size_bytes=None,
                has_essence=True,
                format_summary="WAV 24/48",
                sample_rate=48000,
                bit_depth=24,
                channel_count=1,
                length_edit_units=480000,
            )
        ],
        markers=[
            MarkerEntry(
                track_index=1,
                name="Marker",
                comment="Marker",
                position_edit_units=25,
                position_timecode="00:00:01:00",
                color=None,
            )
        ],
        warnings=[Warning(code="example", message="Example warning")],
    )


def test_report_model_round_trips_through_dumped_shape() -> None:
    report = sample_report()

    reparsed = ReportModel.model_validate(report.model_dump())

    assert reparsed == report
    assert reparsed.schema_version == "2.3"


def test_models_forbid_extra_fields() -> None:
    payload = sample_report().model_dump()
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        ReportModel.model_validate(payload)
