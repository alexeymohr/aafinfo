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
    assert report.clips[0].source_file_name == "source.wav"
    assert report.clips[0].duration_timecode == "00:00:04:00"
    source_entry = next(source for source in report.source_mobs if source.role == "source")
    assert source_entry.name == "source.wav"
    assert source_entry.name_source == "locator"
    assert source_entry.sample_rate == 48000
    assert source_entry.bit_depth == 24
    assert source_entry.linked_paths == ["/Volumes/Show/source.wav"]
    assert source_entry.container == "WAV"
    assert source_entry.data_size_bytes is None
    assert source_entry.has_essence is True
    assert source_entry.format_summary == "WAV 24/48"
    assert report.warnings == []


def test_audio_track_without_source_channel_metadata_reports_mono(tmp_path: Path) -> None:
    aaf_path = tmp_path / "missing-channel-count.aaf"
    _write_missing_channel_count_aaf(aaf_path)

    report = build_report(aaf_path)

    assert report.tracks[0].kind == "audio"
    assert report.tracks[0].channel_count == 1
    assert report.tracks[0].channel_format == "mono"
    assert report.summary.source_files.count == 0
    assert report.summary.source_files.embedded == 0
    assert report.summary.source_files.linked == 0


def test_audio_channel_combiner_reports_combined_channel_count(tmp_path: Path) -> None:
    aaf_path = tmp_path / "audio-channel-combiner.aaf"
    _write_channel_combiner_aaf(aaf_path)

    report = build_report(aaf_path)

    assert report.tracks[0].kind == "audio"
    assert report.tracks[0].channel_count == 2
    assert report.tracks[0].channel_format == "stereo"


def test_non_importable_top_level_slots_are_not_reported_as_tracks(tmp_path: Path) -> None:
    aaf_path = tmp_path / "non-importable-slots.aaf"
    _write_non_importable_slots_aaf(aaf_path)

    report = build_report(aaf_path)

    assert report.composition.track_count == 1
    assert len(report.tracks) == 1
    assert report.tracks[0].index == 1
    assert report.tracks[0].name == "A19"
    assert report.tracks[0].kind == "audio"
    assert report.clips[0].track_index == 1


def test_clip_and_marker_timecodes_include_timeline_start_and_drop_frame(tmp_path: Path) -> None:
    aaf_path = tmp_path / "timeline-start.aaf"
    _write_timeline_start_aaf(aaf_path)

    report = build_report(aaf_path)

    assert report.source_properties.start_timecode == "00:59:50;00"
    assert report.source_properties.timecode_format == "29.97 fps drop"
    assert report.clips[0].in_timecode == "00:59:50;00"
    assert report.clips[0].out_timecode == "00:59:51;00"
    assert report.markers[0].position_timecode == "01:00:00;00"


def test_mixed_embedded_and_linked_audio_file_types_are_both_reported(tmp_path: Path) -> None:
    aaf_path = tmp_path / "mixed-audio-file-types.aaf"
    _write_mixed_audio_file_types_aaf(aaf_path)

    report = build_report(aaf_path)

    assert report.source_properties.audio_file_types == ["Embedded", "Linked"]
    source_file_mobs = [source for source in report.source_mobs if source.role == "source"]
    assert {source.is_embedded for source in source_file_mobs} == {False, True}
    linked_source = next(source for source in source_file_mobs if source.name == "linked.wav")
    embedded_source = next(source for source in source_file_mobs if source.name == "embedded.wav")
    assert linked_source.data_size_bytes is None
    assert embedded_source.data_size_bytes == len(b"embedded fixture data\n")
    assert report.summary.source_files.count == 2
    assert report.summary.source_files.embedded == 1
    assert report.summary.source_files.linked == 1
    assert any(source.linked_paths == ["/Volumes/Show/linked.wav"] for source in report.source_mobs)


def test_source_mob_roles_include_composition_master_and_source(tmp_path: Path) -> None:
    aaf_path = tmp_path / "mob-roles.aaf"
    _write_mob_roles_aaf(aaf_path)

    report = build_report(aaf_path)

    assert {entry.role for entry in report.source_mobs} == {"composition", "master", "source"}
    assert report.summary.source_files.count == 1
    assert report.summary.source_files.embedded == 0
    assert report.summary.source_files.linked == 1


def test_source_mob_container_has_essence_and_format_summary_fields(tmp_path: Path) -> None:
    aaf_path = tmp_path / "container-formats.aaf"
    _write_container_formats_aaf(aaf_path)

    report = build_report(aaf_path)

    source_mobs = {source.name: source for source in report.source_mobs if source.role == "source"}
    assert source_mobs["pcm.wav"].container == "WAV"
    assert source_mobs["pcm.wav"].has_essence is True
    assert source_mobs["pcm.wav"].format_summary == "WAV 24/48"

    assert source_mobs["broadcast.wav"].container == "BWF"
    assert source_mobs["broadcast.wav"].has_essence is True
    assert source_mobs["broadcast.wav"].format_summary == "BWF 16/44.1"

    assert source_mobs["music.aiff"].container == "AIFF"
    assert source_mobs["music.aiff"].has_essence is True
    assert source_mobs["music.aiff"].format_summary == "AIFF 24/96"


def test_clip_source_file_name_uses_locator_through_master_chain(tmp_path: Path) -> None:
    aaf_path = tmp_path / "avid-locator-chain.aaf"
    _write_avid_locator_chain_aaf(aaf_path)

    report = build_report(aaf_path)

    clip = report.clips[0]
    assert clip.name == "HOST takes 1-3"
    assert clip.source_file_name == "ISO1_B_01_take03.wav"
    assert clip.source_basename == "ISO1_B_01_take03.wav"

    source = next(source for source in report.source_mobs if source.role == "source")
    assert source.name == "ISO1_B_01_take03.wav"
    assert source.name_source == "locator"


def test_source_mob_name_uses_bext_originator_reference(tmp_path: Path) -> None:
    aaf_path = tmp_path / "bext-name.aaf"
    _write_bext_name_aaf(aaf_path)

    report = build_report(aaf_path)

    clip = report.clips[0]
    assert clip.source_file_name == "BWF_ORIG_REF_001.wav"
    source = next(source for source in report.source_mobs if source.role == "source")
    assert source.name == "BWF_ORIG_REF_001.wav"
    assert source.name_source == "bext"
    assert source.container == "BWF"


def test_source_mob_name_uses_bext_audio_file_source_path(tmp_path: Path) -> None:
    aaf_path = tmp_path / "bext-audio-file-source-name.aaf"
    _write_bext_audio_file_source_name_aaf(aaf_path)

    report = build_report(aaf_path)

    clip = report.clips[0]
    assert clip.source_file_name == "AUDIO_FILE_SOURCE.wav"
    source = next(source for source in report.source_mobs if source.role == "source")
    assert source.name == "AUDIO_FILE_SOURCE.wav"
    assert source.name_source == "bext"


def test_source_mob_name_uses_master_name_after_placeholder_source_name(tmp_path: Path) -> None:
    aaf_path = tmp_path / "master-name-fallback.aaf"
    _write_master_name_fallback_aaf(aaf_path)

    report = build_report(aaf_path)

    clip = report.clips[0]
    assert clip.source_file_name == "Recovered_Master_File.wav"
    source = next(source for source in report.source_mobs if source.role == "source")
    assert source.name == "Recovered_Master_File.wav"
    assert source.name_source == "mastermob_name"


def test_placeholder_source_names_do_not_become_clip_source_file_name(tmp_path: Path) -> None:
    aaf_path = tmp_path / "placeholder-source-name.aaf"
    _write_placeholder_source_name_aaf(aaf_path)

    report = build_report(aaf_path)

    clip = report.clips[0]
    assert clip.source_file_name is None
    source = next(source for source in report.source_mobs if source.role == "source")
    assert source.name == "Source mob"
    assert source.name_source == "placeholder"


def test_reference_only_source_mob_has_no_essence(tmp_path: Path) -> None:
    aaf_path = tmp_path / "reference-only.aaf"
    _write_missing_channel_count_aaf(aaf_path)

    report = build_report(aaf_path)

    source = next(source for source in report.source_mobs if source.role == "source")
    assert source.has_essence is False
    assert source.name_source == "sourcemob_name"
    assert source.container is None
    assert source.data_size_bytes is None
    assert source.format_summary is None


def test_source_files_summary_filters_reference_only_source_mobs(tmp_path: Path) -> None:
    aaf_path = tmp_path / "mixed-reference-and-essence.aaf"
    _write_mixed_reference_and_essence_aaf(aaf_path)

    report = build_report(aaf_path)

    source_mobs = [source for source in report.source_mobs if source.role == "source"]
    displayed_source_files = [
        source
        for source in source_mobs
        if source.has_essence
    ]

    assert len(source_mobs) == 2
    assert [source.name for source in displayed_source_files] == ["audio.wav"]
    assert report.summary.source_files.count == 1
    assert report.summary.source_files.embedded == 0
    assert report.summary.source_files.linked == 1


def _write_avid_locator_chain_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_mono_source(
            aaf_file,
            "Source mob",
            linked_path="file:///Volumes/Show/ISO1_B_01_take03.wav",
        )
        master_mob = _add_master_mob(aaf_file, "HOST source master", source_mob)

        composition = aaf_file.create.CompositionMob("Avid Locator Chain")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "A1"
        slot["PhysicalTrackNumber"].value = 1
        clip = master_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
        clip["UserComments"].append(aaf_file.create.TaggedValue("Name", "HOST takes 1-3"))
        slot.segment.components.append(clip)
        aaf_file.content.mobs.append(composition)


def _write_bext_name_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_summary_source(
            aaf_file,
            "SourceMob",
            descriptor_name="WAVEDescriptor",
            summary=_wav_summary_bytes(
                channels=1,
                sample_rate=48000,
                bit_depth=24,
                bext=True,
                bext_originator_reference="BWF_ORIG_REF_001.wav",
            ),
            linked_path=None,
        )

        composition = aaf_file.create.CompositionMob("Bext Name")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "A1"
        slot["PhysicalTrackNumber"].value = 1
        slot.segment.components.append(
            source_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
        )
        aaf_file.content.mobs.append(composition)


def _write_bext_audio_file_source_name_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_summary_source(
            aaf_file,
            "Source mob",
            descriptor_name="WAVEDescriptor",
            summary=_wav_summary_bytes(
                channels=1,
                sample_rate=48000,
                bit_depth=24,
                bext=True,
                bext_audio_file_source="/Volumes/Show/AUDIO_FILE_SOURCE.wav",
            ),
            linked_path=None,
        )

        composition = aaf_file.create.CompositionMob("Bext AudioFileSource Name")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "A1"
        slot["PhysicalTrackNumber"].value = 1
        slot.segment.components.append(
            source_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
        )
        aaf_file.content.mobs.append(composition)


def _write_master_name_fallback_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_mono_source(aaf_file, "Source mob")
        master_mob = _add_master_mob(aaf_file, "Recovered_Master_File.wav", source_mob)

        composition = aaf_file.create.CompositionMob("Master Name Fallback")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "A1"
        slot["PhysicalTrackNumber"].value = 1
        slot.segment.components.append(
            master_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
        )
        aaf_file.content.mobs.append(composition)


def _write_placeholder_source_name_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_reference_only_source(aaf_file, "SourceMob")

        composition = aaf_file.create.CompositionMob("Placeholder Source Name")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "A1"
        slot["PhysicalTrackNumber"].value = 1
        slot.segment.components.append(
            source_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
        )
        aaf_file.content.mobs.append(composition)


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


def _write_timeline_start_aaf(path: Path) -> None:
    edit_rate = "30000/1001"
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_mono_source(aaf_file, "drop-frame-source.wav", edit_rate=edit_rate, length=300)

        composition = aaf_file.create.CompositionMob("Timeline Start")
        composition.usage = "Usage_TopLevel"

        timecode_slot = composition.create_timeline_slot(edit_rate=edit_rate)
        timecode_slot["PhysicalTrackNumber"].value = 1
        timecode = aaf_file.create.Timecode(fps=30, drop=True)
        timecode.start = 107592
        timecode.length = 300
        timecode_slot.segment = timecode

        audio_slot = composition.create_sound_slot(edit_rate=edit_rate)
        audio_slot.name = "A1"
        audio_slot["PhysicalTrackNumber"].value = 1
        audio_slot.segment.components.append(
            source_mob.create_source_clip(slot_id=1, start=0, length=30, media_kind="sound")
        )

        event_slot = aaf_file.create.EventMobSlot()
        event_slot["EditRate"].value = edit_rate
        event_slot["SlotID"].value = 1000
        event_slot["PhysicalTrackNumber"].value = 1
        sequence = aaf_file.create.Sequence("DescriptiveMetadata")
        marker = aaf_file.create.DescriptiveMarker()
        marker["DescribedSlots"].value = {1}
        marker["Position"].value = 300
        marker["Comment"].value = "one minute"
        sequence.components.append(marker)
        event_slot.segment = sequence
        composition.slots.append(event_slot)

        aaf_file.content.mobs.append(composition)


def _write_mixed_audio_file_types_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        linked = _add_mono_source(
            aaf_file,
            "linked.wav",
            linked_path="/Volumes/Show/linked.wav",
        )
        embedded = _add_mono_source(aaf_file, "embedded.wav", embedded=True)

        composition = aaf_file.create.CompositionMob("Mixed Audio File Types")
        composition.usage = "Usage_TopLevel"
        for physical_track_number, source_mob in enumerate((linked, embedded), 1):
            slot = composition.create_sound_slot(edit_rate=25)
            slot.name = f"A{physical_track_number}"
            slot["PhysicalTrackNumber"].value = physical_track_number
            slot.segment.components.append(
                source_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
            )

        aaf_file.content.mobs.append(composition)


def _write_mob_roles_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_mono_source(
            aaf_file,
            "role-source.wav",
            linked_path="/Volumes/Show/role-source.wav",
        )
        master_mob = aaf_file.create.MasterMob("Role Master")
        aaf_file.content.mobs.append(master_mob)

        composition = aaf_file.create.CompositionMob("Role Composition")
        composition.usage = "Usage_TopLevel"
        slot = composition.create_sound_slot(edit_rate=25)
        slot.name = "A1"
        slot["PhysicalTrackNumber"].value = 1
        slot.segment.components.append(
            source_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
        )
        aaf_file.content.mobs.append(composition)


def _write_container_formats_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        sources = [
            _add_mono_source(
                aaf_file,
                "pcm.wav",
                linked_path="/Volumes/Show/pcm.wav",
            ),
            _add_summary_source(
                aaf_file,
                "broadcast.wav",
                descriptor_name="WAVEDescriptor",
                summary=_wav_summary_bytes(channels=1, sample_rate=44100, bit_depth=16, bext=True),
                linked_path="/Volumes/Show/broadcast.wav",
            ),
            _add_summary_source(
                aaf_file,
                "music.aiff",
                descriptor_name="AIFCDescriptor",
                summary=_aiff_summary_bytes(channels=2, sample_rate=96000, bit_depth=24),
                linked_path="/Volumes/Show/music.aiff",
            ),
        ]

        composition = aaf_file.create.CompositionMob("Container Formats")
        composition.usage = "Usage_TopLevel"
        for physical_track_number, source_mob in enumerate(sources, 1):
            slot = composition.create_sound_slot(edit_rate=25)
            slot.name = f"A{physical_track_number}"
            slot["PhysicalTrackNumber"].value = physical_track_number
            slot.segment.components.append(
                source_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
            )
        aaf_file.content.mobs.append(composition)


def _write_mixed_reference_and_essence_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        audio_source = _add_mono_source(
            aaf_file,
            "audio.wav",
            linked_path="/Volumes/Show/audio.wav",
        )
        reference_source = _add_reference_only_source(aaf_file, "session.ptx")

        composition = aaf_file.create.CompositionMob("Mixed Reference And Essence")
        composition.usage = "Usage_TopLevel"
        for physical_track_number, source_mob in enumerate((audio_source, reference_source), 1):
            slot = composition.create_sound_slot(edit_rate=25)
            slot.name = f"A{physical_track_number}"
            slot["PhysicalTrackNumber"].value = physical_track_number
            slot.segment.components.append(
                source_mob.create_source_clip(slot_id=1, start=0, length=25, media_kind="sound")
            )
        aaf_file.content.mobs.append(composition)


def _write_missing_channel_count_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_reference_only_source(aaf_file, "mono-without-channel-count.wav")

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


def _write_non_importable_slots_aaf(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source_mob = _add_mono_source(aaf_file, "source.wav")

        composition = aaf_file.create.CompositionMob("Non-importable Slots")
        composition.usage = "Usage_TopLevel"

        timecode_slot = composition.create_timeline_slot(edit_rate=25)
        timecode_slot["PhysicalTrackNumber"].value = 1
        timecode = aaf_file.create.Timecode(fps=25, drop=False)
        timecode.start = 0
        timecode.length = 100
        timecode_slot.segment = timecode

        audio_slot = composition.create_sound_slot(edit_rate=25)
        audio_slot["PhysicalTrackNumber"].value = 19
        clip = source_mob.create_source_clip(slot_id=1, start=0, length=100, media_kind="sound")
        audio_slot.segment.components.append(clip)

        sound_master_datadef = aaf_file.create.DataDef(
            aaf2.auid.AUID("4c5f53dd-8f49-4522-a814-8f457ea0c999"),
            "SoundMasterTrack",
            "",
        )
        aaf_file.dictionary.register_def(sound_master_datadef)

        sound_master_slot = composition.create_timeline_slot(edit_rate=25)
        sound_master_slot["PhysicalTrackNumber"].value = 1
        sound_master_sequence = aaf_file.create.Sequence("SoundMasterTrack")
        sound_master_sequence.length = 100
        sound_master_sequence.components.append(
            aaf_file.create.Filler(media_kind="SoundMasterTrack", length=100)
        )
        sound_master_slot.segment = sound_master_sequence

        aaf_file.content.mobs.append(composition)


def _add_mono_source(
    aaf_file: object,
    name: str,
    *,
    edit_rate: object = 25,
    length: int = 100,
    linked_path: str | None = None,
    embedded: bool = False,
) -> object:
    source_mob = aaf_file.create.SourceMob(name)
    descriptor = aaf_file.create.PCMDescriptor()
    descriptor["AudioSamplingRate"].value = "48000/1"
    descriptor["SampleRate"].value = edit_rate
    descriptor["Length"].value = length
    descriptor["Channels"].value = 1
    descriptor["QuantizationBits"].value = 24
    descriptor["BlockAlign"].value = 3
    descriptor["AverageBPS"].value = 144000
    if linked_path is not None:
        locator = aaf_file.create.NetworkLocator()
        locator["URLString"].value = linked_path
        descriptor["Locator"].append(locator)
    source_mob.descriptor = descriptor
    source_slot = source_mob.create_empty_slot(edit_rate=edit_rate, media_kind="sound", slot_id=1)
    source_slot.segment.length = length
    aaf_file.content.mobs.append(source_mob)
    if embedded:
        essence_data = aaf_file.create.EssenceData()
        essence_data.mob = source_mob
        aaf_file.content.essencedata.append(essence_data)
        stream = essence_data.open("w")
        stream.write(b"embedded fixture data\n")
    return source_mob


def _add_reference_only_source(
    aaf_file: object,
    name: str,
    *,
    edit_rate: object = 25,
    length: int = 100,
) -> object:
    source_mob = aaf_file.create.SourceMob(name)
    source_mob.descriptor = aaf_file.create.ImportDescriptor()
    source_slot = source_mob.create_empty_slot(edit_rate=edit_rate, media_kind="sound", slot_id=1)
    source_slot.segment.length = length
    aaf_file.content.mobs.append(source_mob)
    return source_mob


def _add_master_mob(
    aaf_file: object,
    name: str,
    source_mob: object,
    *,
    edit_rate: object = 25,
    length: int = 100,
) -> object:
    master_mob = aaf_file.create.MasterMob(name)
    master_slot = master_mob.create_sound_slot(edit_rate=edit_rate)
    master_slot.name = name
    master_slot["PhysicalTrackNumber"].value = 1
    master_slot.segment.length = length
    master_slot.segment.components.append(
        source_mob.create_source_clip(slot_id=1, start=0, length=length, media_kind="sound")
    )
    aaf_file.content.mobs.append(master_mob)
    return master_mob


def _add_summary_source(
    aaf_file: object,
    name: str,
    *,
    descriptor_name: str,
    summary: bytes,
    linked_path: str | None,
    edit_rate: object = 25,
    length: int = 100,
) -> object:
    source_mob = aaf_file.create.SourceMob(name)
    descriptor = getattr(aaf_file.create, descriptor_name)()
    descriptor["SampleRate"].value = edit_rate
    descriptor["Length"].value = length
    descriptor["Summary"].value = summary
    if linked_path is not None:
        locator = aaf_file.create.NetworkLocator()
        locator["URLString"].value = linked_path
        descriptor["Locator"].append(locator)
    source_mob.descriptor = descriptor
    source_slot = source_mob.create_empty_slot(edit_rate=edit_rate, media_kind="sound", slot_id=1)
    source_slot.segment.length = length
    aaf_file.content.mobs.append(source_mob)
    return source_mob


def _wav_summary_bytes(
    *,
    channels: int,
    sample_rate: int,
    bit_depth: int,
    bext: bool = False,
    bext_originator_reference: str | None = None,
    bext_audio_file_source: str | None = None,
) -> bytes:
    block_align = channels * max(1, bit_depth // 8)
    byte_rate = sample_rate * block_align
    fmt_payload = b"".join(
        (
            (1).to_bytes(2, "little"),
            channels.to_bytes(2, "little"),
            sample_rate.to_bytes(4, "little"),
            byte_rate.to_bytes(4, "little"),
            block_align.to_bytes(2, "little"),
            bit_depth.to_bytes(2, "little"),
        )
    )
    chunks = [_riff_chunk(b"fmt ", fmt_payload)]
    if bext:
        chunks.append(
            _riff_chunk(
                b"bext",
                _bext_summary_payload(
                    originator_reference=bext_originator_reference,
                    audio_file_source=bext_audio_file_source,
                ),
            )
        )
    payload = b"WAVE" + b"".join(chunks)
    return b"RIFF" + len(payload).to_bytes(4, "little") + payload


def _riff_chunk(chunk_id: bytes, payload: bytes) -> bytes:
    padding = b"\x00" if len(payload) % 2 else b""
    return chunk_id + len(payload).to_bytes(4, "little") + payload + padding


def _bext_summary_payload(
    *,
    originator_reference: str | None = None,
    audio_file_source: str | None = None,
) -> bytes:
    payload = b"".join(
        (
            _fixed_bext_field("", 256),
            _fixed_bext_field("", 32),
            _fixed_bext_field(originator_reference or "", 32),
            _fixed_bext_field("2026-05-03", 10),
            _fixed_bext_field("120000", 8),
            b"\x00" * 8,
            b"\x00" * 2,
            b"\x00" * 64,
            b"\x00" * 190,
        )
    )
    if audio_file_source is not None:
        payload += f"AudioFileSource={audio_file_source}\n".encode("utf-8")
    return payload


def _fixed_bext_field(value: str, size: int) -> bytes:
    encoded = value.encode("utf-8")[:size]
    return encoded + (b"\x00" * (size - len(encoded)))


def _aiff_summary_bytes(*, channels: int, sample_rate: int, bit_depth: int) -> bytes:
    comm_payload = b"".join(
        (
            channels.to_bytes(2, "big"),
            (100).to_bytes(4, "big"),
            bit_depth.to_bytes(2, "big"),
            _extended80(sample_rate),
        )
    )
    payload = b"AIFF" + _aiff_chunk(b"COMM", comm_payload)
    return b"FORM" + len(payload).to_bytes(4, "big") + payload


def _aiff_chunk(chunk_id: bytes, payload: bytes) -> bytes:
    padding = b"\x00" if len(payload) % 2 else b""
    return chunk_id + len(payload).to_bytes(4, "big") + payload + padding


def _extended80(value: int) -> bytes:
    floor_log2 = value.bit_length() - 1
    exponent = 16383 + floor_log2
    mantissa = value << (63 - floor_log2)
    return exponent.to_bytes(2, "big") + mantissa.to_bytes(8, "big")
