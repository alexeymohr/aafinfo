from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

from aafinfo import build_report


def _load_generator() -> ModuleType:
    generator_path = Path(__file__).resolve().parents[2] / "examples" / "_generate.py"
    spec = importlib.util.spec_from_file_location("aafinfo_fixture_generator", generator_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_GENERATOR = _load_generator()
FIXTURE_NAMES = _GENERATOR.FIXTURE_NAMES
generate_all = _GENERATOR.generate_all


def test_generated_fixture_set_is_complete(tmp_path: Path) -> None:
    fixtures = generate_all(tmp_path)

    assert tuple(fixtures) == FIXTURE_NAMES
    assert all(path.exists() for path in fixtures.values())


def test_simple_stereo_fixture_report(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path)["simple_stereo"])

    assert report.composition.name == "simple_stereo"
    assert report.composition.track_count == 1
    assert report.tracks[0].name == "A1-2 Stereo"
    assert report.tracks[0].channel_format == "stereo"
    assert report.tracks[0].clip_count == 4
    assert report.source_properties.name == "simple_stereo"
    assert report.source_properties.file_type == "AAF File"
    assert report.source_properties.audio_bit_depths == [24]
    assert report.source_properties.audio_sample_rates == [48000]
    assert report.source_properties.audio_file_types == ["Linked"]
    assert report.source_properties.video_frame_rate == "25 fps"
    assert [clip.duration_timecode for clip in report.clips] == [
        "00:00:01:00",
        "00:00:02:00",
        "00:00:03:00",
        "00:00:04:00",
    ]


def test_multi_track_fixture_report(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path)["multi_track"])

    assert report.composition.track_count == 4
    assert [track.name for track in report.tracks] == ["DX 1", "DX 2", "MX 1-2", "SFX 1-2"]
    assert [track.channel_count for track in report.tracks] == [1, 1, 2, 2]
    assert [track.clip_count for track in report.tracks] == [2, 3, 1, 4]
    assert report.clips[0].fade_in_edit_units == 2
    assert report.clips[1].fade_out_edit_units == 3
    assert report.clips[5].fade_in_edit_units == 5
    assert report.clips[5].fade_out_edit_units == 5


def test_marker_fixture_report(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path)["with_markers"])

    assert report.composition.marker_count == 5
    assert [marker.position_edit_units for marker in report.markers] == [0, 25, 75, 125, 200]
    assert [marker.position_timecode for marker in report.markers] == [
        "00:00:00:00",
        "00:00:01:00",
        "00:00:03:00",
        "00:00:05:00",
        "00:00:08:00",
    ]
    assert {marker.track_index for marker in report.markers} == {1}
    assert any(marker.color is not None for marker in report.markers)


def test_embedded_essence_fixture_report(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path)["embedded_essence"])

    assert report.composition.track_count == 1
    assert report.tracks[0].clip_count == 1
    source_file_mobs = [source for source in report.source_mobs if source.role == "source"]
    assert len(source_file_mobs) == 1
    assert source_file_mobs[0].is_embedded is True
    assert source_file_mobs[0].linked_paths == []
    assert report.summary.source_files.count == 1
    assert report.summary.source_files.embedded == 1
    assert report.summary.source_files.linked == 0
    assert report.source_properties.audio_file_types == ["Embedded"]


def test_non_integer_rate_fixture_report(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path)["non_integer_rate"])

    assert report.composition.edit_rate == "24000/1001"
    assert report.tracks[0].length_edit_units == 24000
    assert report.tracks[0].length_timecode == "00:16:41:00"
    assert report.clips[0].duration_timecode == "00:16:41:00"
