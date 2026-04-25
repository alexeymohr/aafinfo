from __future__ import annotations

from fractions import Fraction
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
