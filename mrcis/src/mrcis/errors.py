"""MRCIS error types.

All custom exceptions inherit from MRCISError to allow
catching any MRCIS-specific error.
"""


class MRCISError(Exception):
    """Base exception for all MRCIS errors."""

    pass


class ConfigurationError(MRCISError):
    """Invalid configuration."""

    pass


class StorageError(MRCISError):
    """Database or storage operation failed."""

    pass


class ExtractionError(MRCISError):
    """Code extraction failed."""

    def __init__(self, message: str, file_path: str, recoverable: bool = True) -> None:
        super().__init__(message)
        self.file_path = file_path
        self.recoverable = recoverable


class EmbeddingError(MRCISError):
    """Embedding generation failed."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class ResolutionError(MRCISError):
    """Symbol resolution failed."""

    pass


class ReadOnlyInstanceError(MRCISError):
    """Operation requires writer lock, but this instance is read-only."""

    pass
