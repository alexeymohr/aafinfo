from __future__ import annotations

from fractions import Fraction
import math
from pathlib import Path, PureWindowsPath
from typing import Literal
from urllib.parse import unquote, urlparse

ChannelFormat = Literal["mono", "stereo", "5.0", "5.1", "7.1", "multi"]


def edit_rate_fraction(value: object) -> Fraction:
    """Return an exact edit-rate fraction from pyaaf2 or scalar values."""
    numerator = getattr(value, "numerator", None)
    denominator = getattr(value, "denominator", None)
    if numerator is not None and denominator is not None:
        return Fraction(int(numerator), int(denominator))

    if isinstance(value, tuple) and len(value) == 2:
        return Fraction(int(value[0]), int(value[1]))

    if isinstance(value, int):
        return Fraction(value, 1)

    if isinstance(value, str):
        return Fraction(value)

    if isinstance(value, float):
        return Fraction(value).limit_denominator(0x7FFFFFFF)

    raise TypeError(f"Unsupported edit-rate value: {value!r}")


def format_edit_rate(value: object) -> str:
    rate = edit_rate_fraction(value)
    return f"{rate.numerator}/{rate.denominator}"


def edit_rate_decimal(value: object) -> float:
    return float(edit_rate_fraction(value))


def frame_rate_label(value: object) -> str:
    rate = edit_rate_fraction(value)
    if rate.denominator == 1:
        return f"{rate.numerator} fps"

    decimal = float(rate)
    if rate == Fraction(30000, 1001) or rate == Fraction(60000, 1001):
        return f"{decimal:.2f} fps"
    value_text = f"{decimal:.3f}".rstrip("0").rstrip(".")
    return f"{value_text} fps"


def timecode_format_label(edit_rate: object, *, fps: int | None = None, drop: bool = False) -> str:
    if fps is not None and drop:
        rate = Fraction(fps * 1000, 1001)
        return f"{float(rate):.2f} fps drop"

    label = frame_rate_label(edit_rate)
    if fps is not None:
        suffix = "drop" if drop else "non-drop"
        return f"{label} {suffix}"
    return label


def edit_units_to_timecode(edit_units: int, edit_rate: object) -> str:
    """Format edit units as HH:MM:SS:FF using exact rational arithmetic."""
    rate = edit_rate_fraction(edit_rate)
    if rate <= 0:
        return "00:00:00:00"

    sign = "-" if edit_units < 0 else ""
    units = abs(int(edit_units))
    nominal_fps = max(1, (rate.numerator + rate.denominator - 1) // rate.denominator)
    total_frames = (units * nominal_fps * rate.denominator) // rate.numerator

    frames = total_frames % nominal_fps
    total_seconds = total_frames // nominal_fps
    seconds = total_seconds % 60
    total_minutes = total_seconds // 60
    minutes = total_minutes % 60
    hours = total_minutes // 60

    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


def frames_to_timecode(frames: int, fps: int, *, drop: bool = False) -> str:
    nominal_fps = max(1, int(fps))
    sign = "-" if frames < 0 else ""
    frame_number = abs(int(frames))

    if drop and nominal_fps in {30, 60}:
        frame_number = _drop_frame_timecode_number(frame_number, nominal_fps)

    ff = frame_number % nominal_fps
    total_seconds = frame_number // nominal_fps
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    sep = ";" if drop else ":"
    return f"{sign}{hh:02d}:{mm:02d}:{ss:02d}{sep}{ff:02d}"


def duration_timecode(edit_units: int, edit_rate: object) -> str:
    return edit_units_to_timecode(edit_units, edit_rate)


def basename(path: Path) -> str:
    return path.name


def display_basename(value: str | Path) -> str:
    text = str(value)
    if "\\" in text:
        return PureWindowsPath(text).name
    parsed = urlparse(text)
    if parsed.scheme and parsed.path:
        return Path(unquote(parsed.path)).name
    return Path(text).name


def byte_size(size_bytes: int) -> str:
    if size_bytes == 1:
        return "1 byte"

    size = float(size_bytes)
    units = ["bytes", "KiB", "MiB", "GiB", "TiB"]
    unit = units[0]
    for unit in units:
        if abs(size) < 1024 or unit == units[-1]:
            break
        size /= 1024

    if unit == "bytes":
        return f"{int(size)} bytes"
    return f"{size:.1f} {unit}"


def channel_format(channel_count: int | None) -> ChannelFormat:
    if channel_count == 1:
        return "mono"
    if channel_count == 2:
        return "stereo"
    if channel_count == 5:
        return "5.0"
    if channel_count == 6:
        return "5.1"
    if channel_count == 8:
        return "7.1"
    return "multi"


def _drop_frame_timecode_number(frames: int, fps: int) -> int:
    drop_frames = int(round(fps * 0.066666))
    frames_per_minute = fps * 60 - drop_frames
    frames_per_10_minutes = fps * 60 * 10 - drop_frames * 9

    ten_minute_chunks = frames // frames_per_10_minutes
    remaining_frames = frames % frames_per_10_minutes
    dropped = drop_frames * 9 * ten_minute_chunks
    if remaining_frames >= drop_frames:
        dropped += drop_frames * math.floor((remaining_frames - drop_frames) / frames_per_minute)

    return frames + dropped
