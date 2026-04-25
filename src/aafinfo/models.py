from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TrackKind = Literal["audio", "video", "timecode", "other"]
ChannelFormat = Literal["mono", "stereo", "5.0", "5.1", "7.1", "multi"]
SourceMobKind = Literal["audio", "video", "other"]


class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InputInfo(SchemaModel):
    path: str
    basename: str
    size_bytes: int = Field(ge=0)
    sha256: str


class CompositionSummary(SchemaModel):
    name: str
    edit_rate: str
    edit_rate_decimal: float = Field(ge=0)
    length_edit_units: int = Field(ge=0)
    length_timecode: str
    track_count: int = Field(ge=0)
    marker_count: int = Field(ge=0)


class TrackEntry(SchemaModel):
    index: int = Field(ge=1)
    name: str
    kind: TrackKind
    channel_format: ChannelFormat
    channel_count: int = Field(ge=0)
    length_edit_units: int = Field(ge=0)
    length_timecode: str
    clip_count: int = Field(ge=0)


class ClipEntry(SchemaModel):
    track_index: int = Field(ge=1)
    clip_index: int = Field(ge=0)
    name: str
    source_basename: str
    source_mob_id: str
    in_edit_units: int = Field(ge=0)
    out_edit_units: int = Field(ge=0)
    in_timecode: str
    out_timecode: str
    duration_timecode: str
    fade_in_edit_units: int | None = Field(default=None, ge=0)
    fade_out_edit_units: int | None = Field(default=None, ge=0)
    comment: str | None


class SourceMobEntry(SchemaModel):
    mob_id: str
    name: str
    kind: SourceMobKind
    is_embedded: bool
    linked_paths: list[str]
    sample_rate: int | None = Field(default=None, ge=0)
    bit_depth: int | None = Field(default=None, ge=0)
    channel_count: int | None = Field(default=None, ge=0)
    length_edit_units: int | None = Field(default=None, ge=0)


class MarkerEntry(SchemaModel):
    track_index: int | None = Field(default=None, ge=1)
    name: str
    comment: str | None
    position_edit_units: int = Field(ge=0)
    position_timecode: str
    color: str | None


class Warning(SchemaModel):
    code: str
    message: str


class ReportModel(SchemaModel):
    schema_version: Literal[1] = 1
    aafinfo_version: str
    run_id: str
    run_started_at: str
    input: InputInfo
    composition: CompositionSummary
    tracks: list[TrackEntry]
    clips: list[ClipEntry]
    source_mobs: list[SourceMobEntry]
    markers: list[MarkerEntry]
    warnings: list[Warning]
