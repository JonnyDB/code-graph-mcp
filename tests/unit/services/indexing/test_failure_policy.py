"""Tests for IndexFailurePolicy."""

from mrcis.models.state import FileStatus
from mrcis.services.indexing.failure_policy import IndexFailurePolicy


class TestIndexFailurePolicy:
    """Tests for IndexFailurePolicy class."""

    def test_should_retry_below_threshold(self):
        """Policy should allow retry when failure count is below max."""
        policy = IndexFailurePolicy(max_retries=3)

        # failure_count=0 means this is the first failure
        should_retry, status = policy.determine_action(failure_count=0)
        assert should_retry is True
        assert status == FileStatus.FAILED

        # failure_count=2 means this will be the 3rd attempt (still below max)
        should_retry, status = policy.determine_action(failure_count=2)
        assert should_retry is True
        assert status == FileStatus.FAILED

    def test_should_not_retry_at_threshold(self):
        """Policy should not retry when failure count reaches max."""
        policy = IndexFailurePolicy(max_retries=3)

        # failure_count=3 means we've already failed 3 times (hit max)
        should_retry, status = policy.determine_action(failure_count=3)
        assert should_retry is False
        assert status == FileStatus.PERMANENT_FAILURE

    def test_should_not_retry_above_threshold(self):
        """Policy should not retry when failure count exceeds max."""
        policy = IndexFailurePolicy(max_retries=3)

        # failure_count=5 means we're well past the max
        should_retry, status = policy.determine_action(failure_count=5)
        assert should_retry is False
        assert status == FileStatus.PERMANENT_FAILURE

    def test_max_retries_zero(self):
        """Policy with max_retries=0 should never retry."""
        policy = IndexFailurePolicy(max_retries=0)

        should_retry, status = policy.determine_action(failure_count=0)
        assert should_retry is False
        assert status == FileStatus.PERMANENT_FAILURE

    def test_max_retries_one(self):
        """Policy with max_retries=1 should allow one retry only."""
        policy = IndexFailurePolicy(max_retries=1)

        # First failure - allow retry
        should_retry, status = policy.determine_action(failure_count=0)
        assert should_retry is True
        assert status == FileStatus.FAILED

        # Second failure - no more retries
        should_retry, status = policy.determine_action(failure_count=1)
        assert should_retry is False
        assert status == FileStatus.PERMANENT_FAILURE

    def test_default_max_retries(self):
        """Policy should use default max_retries if not specified."""
        policy = IndexFailurePolicy()

        # Default is 3 according to IndexingConfig
        should_retry, status = policy.determine_action(failure_count=2)
        assert should_retry is True
        assert status == FileStatus.FAILED

        should_retry, status = policy.determine_action(failure_count=3)
        assert should_retry is False
        assert status == FileStatus.PERMANENT_FAILURE
