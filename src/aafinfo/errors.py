from __future__ import annotations


class AAFInfoError(Exception):
    """Base class for user-facing AAFinfo errors."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class UnreadableFileError(AAFInfoError):
    """Raised when an input file cannot be opened or read."""


class UnsupportedAAFError(AAFInfoError):
    """Raised when pyaaf2 cannot parse the input AAF."""
