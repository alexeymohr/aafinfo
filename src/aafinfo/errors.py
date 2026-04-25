from __future__ import annotations


class AAFInfoError(Exception):
    """Base class for user-facing AAFinfo errors."""


class UnreadableFileError(AAFInfoError):
    """Raised when an input file cannot be opened or read."""


class UnsupportedAAFError(AAFInfoError):
    """Raised when pyaaf2 cannot parse the input AAF."""
