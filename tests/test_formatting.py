from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from aafinfo.formatting import (
    byte_size,
    channel_format,
    display_basename,
    duration_timecode,
    edit_rate_decimal,
    edit_rate_fraction,
    edit_units_to_timecode,
    format_edit_rate,
)


def test_edit_rate_helpers_preserve_fractional_rates() -> None:
    rate = edit_rate_fraction("24000/1001")

    assert rate == Fraction(24000, 1001)
    assert format_edit_rate(rate) == "24000/1001"
    assert edit_rate_decimal(rate) == float(Fraction(24000, 1001))


def test_timecode_uses_exact_rational_arithmetic() -> None:
    assert edit_units_to_timecode(1234, 25) == "00:00:49:09"
    assert duration_timecode(24000, "24000/1001") == "00:16:41:00"


def test_display_helpers() -> None:
    assert display_basename(Path("/tmp/source.wav")) == "source.wav"
    assert display_basename("file:///Volumes/Show/source%20A.wav") == "source A.wav"
    assert display_basename(r"C:\Show\source B.wav") == "source B.wav"
    assert byte_size(1) == "1 byte"
    assert byte_size(2048) == "2.0 KiB"


def test_channel_format_inference() -> None:
    assert channel_format(1) == "mono"
    assert channel_format(2) == "stereo"
    assert channel_format(6) == "5.1"
    assert channel_format(None) == "multi"
