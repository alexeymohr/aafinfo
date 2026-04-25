from __future__ import annotations

from pathlib import Path


def basename(path: Path) -> str:
    return path.name


def byte_size(size_bytes: int) -> str:
    return f"{size_bytes} bytes"


def channel_format(channel_count: int | None) -> str:
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
