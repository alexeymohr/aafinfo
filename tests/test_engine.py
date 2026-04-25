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
