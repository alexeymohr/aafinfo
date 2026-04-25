from __future__ import annotations

from pathlib import Path

import aaf2

from aafinfo import build_report
from aafinfo.models import ReportModel


def test_build_report_returns_populated_model_for_minimal_aaf(tmp_path: Path) -> None:
    aaf_path = tmp_path / "minimal.aaf"
    _write_minimal_aaf(aaf_path)

    report = build_report(aaf_path)

    assert isinstance(report, ReportModel)
    assert report.input.basename == "minimal.aaf"
    assert report.composition.name == "Minimal Composition"
    assert report.composition.edit_rate == "25/1"
    assert report.composition.track_count == 1
    assert report.tracks[0].name == "A1"
    assert report.tracks[0].kind == "audio"
    assert report.tracks[0].channel_count == 2
    assert report.clips[0].source_basename == "source.wav"
    assert report.clips[0].duration_timecode == "00:00:04:00"
    assert report.source_mobs[0].sample_rate == 48000
    assert report.source_mobs[0].bit_depth == 24
    assert report.source_mobs[0].linked_paths == ["/Volumes/Show/source.wav"]
    assert report.warnings == []


def test_audio_track_without_source_channel_metadata_reports_mono(tmp_path: Path) -> None:
    aaf_path = tmp_path / "missing-channel-count.aaf"
    _write_missing_channel_count_aaf(aaf_path)

    report = build_report(aaf_path)

    assert report.tracks[0].kind == "audio"
    assert report.tracks[0].channel_count == 1
    assert report.tracks[0].channel_format == "mono"


def test_audio_channel_combiner_reports_combined_channel_count(tmp_path: Path) -> None:
    aaf_path = tmp_path / "audio-channel-combiner.aaf"
    _write_channel_combiner_aaf(aaf_path)

    report = build_report(aaf_path)

    assert report.tracks[0].kind == "audio"
    assert report.tracks[0].channel_count == 2
    assert report.tracks[0].channel_format == "stereo"


def _write_minimal_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = aaf_file.create.SourceMob("source.wav")
        descriptor = aaf_file.create.PCMDescriptor()
        descriptor["AudioSamplingRate"].value = "48000/1"
        descriptor["SampleRate"].value = "25/1"
        descriptor["Length"].value = 100
        descriptor["Channels"].value = 2
        descriptor["QuantizationBits"].value = 24
        descriptor["BlockAlign"].value = 6
        descriptor["AverageBPS"].value = 288000
        locator = aaf_file.create.NetworkLocator()
        locator["URLString"].value = "/Volumes/Show/source.wav"
        descriptor["Locator"].append(locator)
        source_mob.descriptor = descriptor
        source_slot = source_mob.create_empty_slot(edit_rate=25, media_kind="sound", slot_id=1)
        source_slot.segment.length = 100
        aaf_file.content.mobs.append(source_mob)

        composition = aaf_file.create.CompositionMob("Minimal Composition")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "A1"
        slot["PhysicalTrackNumber"].value = 1
        clip = source_mob.create_source_clip(slot_id=1, start=0, length=100, media_kind="sound")
        slot.segment.components.append(clip)
        aaf_file.content.mobs.append(composition)


def _write_missing_channel_count_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = aaf_file.create.SourceMob("mono-without-channel-count.wav")
        source_mob.descriptor = aaf_file.create.ImportDescriptor()
        source_slot = source_mob.create_empty_slot(edit_rate=25, media_kind="sound", slot_id=1)
        source_slot.segment.length = 100
        aaf_file.content.mobs.append(source_mob)

        composition = aaf_file.create.CompositionMob("Missing Channel Count")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "Mono A1"
        slot["PhysicalTrackNumber"].value = 1
        clip = source_mob.create_source_clip(slot_id=1, start=0, length=100, media_kind="sound")
        slot.segment.components.append(clip)
        aaf_file.content.mobs.append(composition)


def _write_channel_combiner_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        left = _add_mono_source(aaf_file, "left.wav")
        right = _add_mono_source(aaf_file, "right.wav")

        op_def = aaf_file.create.OperationDef()
        op_def.auid = aaf2.auid.AUID("6b46dd7a-132d-4856-ab21-8b751d8462ec")
        op_def["Name"].value = "Audio Channel Combiner"
        op_def.media_kind = "sound"
        op_def["NumberInputs"].value = 1
        op_def["IsTimeWarp"].value = False
        op_def["Bypass"].value = 0
        op_def["OperationCategory"].value = "OperationCategory_Effect"
        aaf_file.dictionary.register_def(op_def)

        composition = aaf_file.create.CompositionMob("Audio Channel Combiner")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "Stereo A1-2"
        slot["PhysicalTrackNumber"].value = 1

        op_group = aaf_file.create.OperationGroup(op_def, length=100, media_kind="sound")
        for source_mob in (left, right):
            op_group.segments.append(
                source_mob.create_source_clip(slot_id=1, start=0, length=100, media_kind="sound")
            )

        slot.segment.components.append(op_group)
        aaf_file.content.mobs.append(composition)


def _add_mono_source(aaf_file: object, name: str) -> object:
    source_mob = aaf_file.create.SourceMob(name)
    descriptor = aaf_file.create.PCMDescriptor()
    descriptor["AudioSamplingRate"].value = "48000/1"
    descriptor["SampleRate"].value = "25/1"
    descriptor["Length"].value = 100
    descriptor["Channels"].value = 1
    descriptor["QuantizationBits"].value = 24
    descriptor["BlockAlign"].value = 3
    descriptor["AverageBPS"].value = 144000
    source_mob.descriptor = descriptor
    source_slot = source_mob.create_empty_slot(edit_rate=25, media_kind="sound", slot_id=1)
    source_slot.segment.length = 100
    aaf_file.content.mobs.append(source_mob)
    return source_mob
