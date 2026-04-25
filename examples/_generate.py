from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import aaf2
from aaf2.mobid import MobID


GENERATED_DIR = Path(__file__).resolve().parent / "_generated"
FIXTURE_NAMES = (
    "simple_stereo",
    "multi_track",
    "with_markers",
    "embedded_essence",
    "non_integer_rate",
)


@dataclass(frozen=True)
class FadeSpec:
    fade_in: int | None = None
    fade_out: int | None = None


def generate_all(output_dir: Path = GENERATED_DIR) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    fixtures = {
        "simple_stereo": output_dir / "simple_stereo.aaf",
        "multi_track": output_dir / "multi_track.aaf",
        "with_markers": output_dir / "with_markers.aaf",
        "embedded_essence": output_dir / "embedded_essence.aaf",
        "non_integer_rate": output_dir / "non_integer_rate.aaf",
    }

    _write_simple_stereo(fixtures["simple_stereo"])
    _write_multi_track(fixtures["multi_track"])
    _write_with_markers(fixtures["with_markers"])
    _write_embedded_essence(fixtures["embedded_essence"])
    _write_non_integer_rate(fixtures["non_integer_rate"])

    return fixtures


def _write_simple_stereo(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source = _add_pcm_source(
            aaf_file,
            name="simple_stereo.wav",
            mob_id_value=1001,
            channels=2,
            length=400,
            linked_path="/Volumes/AAFinfo/simple_stereo.wav",
        )
        composition = _add_composition(aaf_file, "simple_stereo")
        _add_audio_track(
            composition,
            source,
            name="A1-2 Stereo",
            physical_track_number=1,
            clip_lengths=[25, 50, 75, 100],
        )


def _write_multi_track(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        composition = _add_composition(aaf_file, "multi_track")
        tracks = [
            ("DX 1", 1101, 1, 160, [40, 40], [FadeSpec(fade_in=2), FadeSpec(fade_out=3)]),
            ("DX 2", 1102, 1, 180, [30, 30, 60], [FadeSpec(), FadeSpec(1, 1), FadeSpec()]),
            ("MX 1-2", 1103, 2, 240, [120], [FadeSpec(fade_in=5, fade_out=5)]),
            ("SFX 1-2", 1104, 2, 220, [25, 25, 25, 25], [FadeSpec(), FadeSpec(), FadeSpec(2), FadeSpec(fade_out=2)]),
        ]

        for physical_track_number, (name, mob_id_value, channels, length, clip_lengths, fades) in enumerate(tracks, 1):
            source = _add_pcm_source(
                aaf_file,
                name=f"{name.lower().replace(' ', '_')}.wav",
                mob_id_value=mob_id_value,
                channels=channels,
                length=length,
                linked_path=f"/Volumes/AAFinfo/{name.lower().replace(' ', '_')}.wav",
            )
            _add_audio_track(
                composition,
                source,
                name=name,
                physical_track_number=physical_track_number,
                clip_lengths=clip_lengths,
                fades=fades,
            )


def _write_with_markers(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source = _add_pcm_source(
            aaf_file,
            name="with_markers.wav",
            mob_id_value=1201,
            channels=1,
            length=250,
            linked_path="/Volumes/AAFinfo/with_markers.wav",
        )
        composition = _add_composition(aaf_file, "with_markers")
        _add_audio_track(
            composition,
            source,
            name="A1 Markers",
            physical_track_number=1,
            clip_lengths=[250],
        )
        _add_marker_track(
            aaf_file,
            composition,
            edit_rate=25,
            physical_track_number=1,
            markers=[
                (0, "start", None),
                (25, "scene 1", None),
                (75, "pickup", {"red": 65535, "green": 0, "blue": 0}),
                (125, "alternate", None),
                (200, "tail", None),
            ],
        )


def _write_embedded_essence(path: Path) -> None:
    with aaf2.open(str(path), "w") as aaf_file:
        source = _add_pcm_source(
            aaf_file,
            name="embedded_tone.wav",
            mob_id_value=1301,
            channels=1,
            length=120,
            linked_path=None,
            embedded=True,
        )
        composition = _add_composition(aaf_file, "embedded_essence")
        _add_audio_track(
            composition,
            source,
            name="A1 Embedded",
            physical_track_number=1,
            clip_lengths=[120],
        )


def _write_non_integer_rate(path: Path) -> None:
    edit_rate = "24000/1001"
    with aaf2.open(str(path), "w") as aaf_file:
        source = _add_pcm_source(
            aaf_file,
            name="non_integer_rate.wav",
            mob_id_value=1401,
            channels=1,
            length=24000,
            linked_path="/Volumes/AAFinfo/non_integer_rate.wav",
            edit_rate=edit_rate,
        )
        composition = _add_composition(aaf_file, "non_integer_rate")
        _add_audio_track(
            composition,
            source,
            name="A1 23.976",
            physical_track_number=1,
            clip_lengths=[24000],
            edit_rate=edit_rate,
        )


def _add_composition(aaf_file: object, name: str) -> object:
    composition = aaf_file.create.CompositionMob(name)
    composition.usage = "Usage_TopLevel"
    aaf_file.content.mobs.append(composition)
    return composition


def _add_pcm_source(
    aaf_file: object,
    *,
    name: str,
    mob_id_value: int,
    channels: int,
    length: int,
    linked_path: str | None,
    edit_rate: object = 25,
    sample_rate: int = 48000,
    bit_depth: int = 24,
    embedded: bool = False,
) -> object:
    source = aaf_file.create.SourceMob(name)
    mob_id = MobID()
    mob_id.int = mob_id_value
    source.mob_id = mob_id

    descriptor = aaf_file.create.PCMDescriptor()
    descriptor["AudioSamplingRate"].value = f"{sample_rate}/1"
    descriptor["SampleRate"].value = edit_rate
    descriptor["Length"].value = length
    descriptor["Channels"].value = channels
    descriptor["QuantizationBits"].value = bit_depth

    block_align = channels * max(1, bit_depth // 8)
    descriptor["BlockAlign"].value = block_align
    descriptor["AverageBPS"].value = sample_rate * block_align

    if linked_path is not None:
        locator = aaf_file.create.NetworkLocator()
        locator["URLString"].value = linked_path
        descriptor["Locator"].append(locator)

    source.descriptor = descriptor
    source_slot = source.create_empty_slot(edit_rate=edit_rate, media_kind="sound", slot_id=1)
    source_slot.segment.length = length
    aaf_file.content.mobs.append(source)

    if embedded:
        essence_data = aaf_file.create.EssenceData()
        essence_data.mob = source
        aaf_file.content.essencedata.append(essence_data)
        stream = essence_data.open("w")
        stream.write(b"AAFinfo embedded fixture data\n")

    return source


def _add_audio_track(
    composition: object,
    source: object,
    *,
    name: str,
    physical_track_number: int,
    clip_lengths: Sequence[int],
    edit_rate: object = 25,
    fades: Sequence[FadeSpec] | None = None,
) -> None:
    slot = composition.create_sound_slot(edit_rate=edit_rate)
    slot.name = name
    slot["PhysicalTrackNumber"].value = physical_track_number

    source_start = 0
    for index, length in enumerate(clip_lengths):
        clip = source.create_source_clip(slot_id=1, start=source_start, length=length, media_kind="sound")
        if fades is not None and index < len(fades):
            fade = fades[index]
            if fade.fade_in is not None:
                clip["FadeInLength"].value = fade.fade_in
            if fade.fade_out is not None:
                clip["FadeOutLength"].value = fade.fade_out
        slot.segment.components.append(clip)
        source_start += length


def _add_marker_track(
    aaf_file: object,
    composition: object,
    *,
    edit_rate: object,
    physical_track_number: int,
    markers: Sequence[tuple[int, str, dict[str, int] | None]],
) -> None:
    event_slot = aaf_file.create.EventMobSlot()
    event_slot["EditRate"].value = edit_rate
    event_slot["SlotID"].value = 1000
    event_slot["PhysicalTrackNumber"].value = physical_track_number

    sequence = aaf_file.create.Sequence("DescriptiveMetadata")
    for position, comment, color in markers:
        marker = aaf_file.create.DescriptiveMarker()
        marker["DescribedSlots"].value = {physical_track_number}
        marker["Position"].value = position
        marker["Comment"].value = comment
        if color is not None:
            marker["CommentMarkerColor"].value = color
        sequence.components.append(marker)

    event_slot.segment = sequence
    composition.slots.append(event_slot)


def main() -> None:
    fixtures = generate_all()
    for name in FIXTURE_NAMES:
        print(fixtures[name])


if __name__ == "__main__":
    main()
