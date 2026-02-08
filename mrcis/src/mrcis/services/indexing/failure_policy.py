"""Failure policy for indexing operations.

Determines retry logic and failure status for failed file indexing.
"""

from mrcis.models.state import FileStatus


class IndexFailurePolicy:
    """Determines retry behavior for failed file indexing.

    Encapsulates the logic for deciding whether a failed file should be
    retried based on the number of previous failures and the configured
    retry threshold.
    """

    def __init__(self, max_retries: int = 3) -> None:
        """Initialize failure policy.

        Args:
            max_retries: Maximum number of retry attempts before permanent failure.
        """
        self.max_retries = max_retries

    def determine_action(self, failure_count: int) -> tuple[bool, FileStatus]:
        """Determine if a file should be retried after failure.

        Args:
            failure_count: Number of times the file has already failed.

        Returns:
            Tuple of (should_retry, status):
                - should_retry: True if the file should be retried
                - status: FileStatus.FAILED (retry) or FileStatus.PERMANENT_FAILURE (no retry)
        """
        # After incrementing, failure_count represents the new count after this failure
        # If we've already failed max_retries times, don't retry again
        if failure_count >= self.max_retries:
            return False, FileStatus.PERMANENT_FAILURE

        return True, FileStatus.FAILED
