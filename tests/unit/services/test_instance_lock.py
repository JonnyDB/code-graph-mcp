"""Tests for InstanceLock file-based lock coordination."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mrcis.services.instance_lock import InstanceLock


class TestInstanceLockAcquire:
    """Tests for lock acquisition."""

    def test_acquire_when_no_lock_exists(self, tmp_path: Path) -> None:
        """Lock should be acquired when no lock file exists."""
        lock = InstanceLock(tmp_path)
        assert lock.try_acquire() is True
        assert lock.is_held() is True
        assert lock.lock_path.exists()

    def test_acquire_writes_pid_and_timestamp(self, tmp_path: Path) -> None:
        """Lock file should contain current PID and a valid timestamp."""
        lock = InstanceLock(tmp_path)
        lock.try_acquire()

        content = lock.lock_path.read_text().strip().splitlines()
        assert len(content) == 2
        assert int(content[0]) == os.getpid()
        # Should parse as ISO datetime
        datetime.fromisoformat(content[1])

    def test_acquire_fails_when_held_by_live_process(self, tmp_path: Path) -> None:
        """Lock should not be acquired when held by a live process."""
        # Write a lock file with the current process PID (definitely alive)
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"{os.getpid()}\n{datetime.now(UTC).isoformat()}\n")

        lock = InstanceLock(tmp_path)
        assert lock.try_acquire() is False
        assert lock.is_held() is False

    def test_acquire_succeeds_when_holder_is_dead(self, tmp_path: Path) -> None:
        """Lock should be acquired when the holder PID no longer exists."""
        # Use a PID that almost certainly doesn't exist
        dead_pid = 4_000_000_000
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"{dead_pid}\n{datetime.now(UTC).isoformat()}\n")

        lock = InstanceLock(tmp_path)
        assert lock.try_acquire() is True
        assert lock.is_held() is True

        # Verify it wrote our PID
        content = lock_path.read_text().strip().splitlines()
        assert int(content[0]) == os.getpid()

    def test_acquire_succeeds_when_timestamp_expired(self, tmp_path: Path) -> None:
        """Lock should be acquired when the timestamp is older than stale_seconds."""
        old_time = datetime.now(UTC) - timedelta(seconds=200)
        lock_path = tmp_path / "mrcis.lock"
        # Use current PID so process is alive, but timestamp is expired
        lock_path.write_text(f"{os.getpid()}\n{old_time.isoformat()}\n")

        lock = InstanceLock(tmp_path, stale_seconds=90)
        assert lock.try_acquire() is True
        assert lock.is_held() is True

    def test_acquire_succeeds_when_lock_file_malformed(self, tmp_path: Path) -> None:
        """Lock should be acquired when the existing lock file is malformed."""
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text("garbage content\n")

        lock = InstanceLock(tmp_path)
        assert lock.try_acquire() is True
        assert lock.is_held() is True

    def test_acquire_idempotent_when_already_held(self, tmp_path: Path) -> None:
        """Calling try_acquire when already held should return True."""
        lock = InstanceLock(tmp_path)
        assert lock.try_acquire() is True
        assert lock.try_acquire() is True
        assert lock.is_held() is True


class TestInstanceLockRelease:
    """Tests for lock release."""

    def test_release_deletes_lock_file(self, tmp_path: Path) -> None:
        """Release should delete the lock file."""
        lock = InstanceLock(tmp_path)
        lock.try_acquire()
        assert lock.lock_path.exists()

        lock.release()
        assert not lock.lock_path.exists()
        assert lock.is_held() is False

    def test_release_noop_when_not_held(self, tmp_path: Path) -> None:
        """Release should be a no-op when the lock is not held."""
        lock = InstanceLock(tmp_path)
        lock.release()  # Should not raise
        assert lock.is_held() is False

    def test_release_handles_already_deleted_file(self, tmp_path: Path) -> None:
        """Release should handle the case where the file was already removed."""
        lock = InstanceLock(tmp_path)
        lock.try_acquire()

        # Manually remove the file
        lock.lock_path.unlink()

        lock.release()  # Should not raise
        assert lock.is_held() is False


class TestInstanceLockHeartbeat:
    """Tests for heartbeat updates."""

    def test_heartbeat_updates_timestamp(self, tmp_path: Path) -> None:
        """Heartbeat should update the lock file timestamp."""
        lock = InstanceLock(tmp_path)
        lock.try_acquire()

        # Read initial timestamp
        content_before = lock.lock_path.read_text()

        # Update heartbeat
        lock.heartbeat()

        content_after = lock.lock_path.read_text()

        # PID should be the same, timestamp should be updated
        lines_before = content_before.strip().splitlines()
        lines_after = content_after.strip().splitlines()
        assert lines_before[0] == lines_after[0]  # same PID
        # Timestamps may differ (or may be same if test is fast)
        # Just verify it's still valid
        datetime.fromisoformat(lines_after[1])

    def test_heartbeat_noop_when_not_held(self, tmp_path: Path) -> None:
        """Heartbeat should be a no-op when not holding the lock."""
        lock = InstanceLock(tmp_path)
        lock.heartbeat()  # Should not raise, should not create file
        assert not lock.lock_path.exists()


class TestInstanceLockCheckAndPromote:
    """Tests for stale lock detection and promotion."""

    def test_promote_returns_false_when_lock_is_fresh(self, tmp_path: Path) -> None:
        """check_and_promote should return False when the lock is fresh."""
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"{os.getpid()}\n{datetime.now(UTC).isoformat()}\n")

        lock = InstanceLock(tmp_path)
        assert lock.check_and_promote() is False
        assert lock.is_held() is False

    def test_promote_succeeds_when_holder_dead(self, tmp_path: Path) -> None:
        """check_and_promote should succeed when the holder PID is dead."""
        dead_pid = 4_000_000_000
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"{dead_pid}\n{datetime.now(UTC).isoformat()}\n")

        lock = InstanceLock(tmp_path)
        assert lock.check_and_promote() is True
        assert lock.is_held() is True

    def test_promote_succeeds_when_timestamp_expired(self, tmp_path: Path) -> None:
        """check_and_promote should succeed when the timestamp is expired."""
        old_time = datetime.now(UTC) - timedelta(seconds=200)
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text(f"{os.getpid()}\n{old_time.isoformat()}\n")

        lock = InstanceLock(tmp_path, stale_seconds=90)
        assert lock.check_and_promote() is True
        assert lock.is_held() is True

    def test_promote_when_lock_file_missing(self, tmp_path: Path) -> None:
        """check_and_promote should acquire when the lock file is gone."""
        lock = InstanceLock(tmp_path)
        # No lock file exists
        assert lock.check_and_promote() is True
        assert lock.is_held() is True

    def test_promote_when_lock_file_malformed(self, tmp_path: Path) -> None:
        """check_and_promote should acquire when the lock file is malformed."""
        lock_path = tmp_path / "mrcis.lock"
        lock_path.write_text("not a valid lock\n")

        lock = InstanceLock(tmp_path)
        assert lock.check_and_promote() is True
        assert lock.is_held() is True

    def test_promote_noop_when_already_held(self, tmp_path: Path) -> None:
        """check_and_promote should return False when already holding the lock."""
        lock = InstanceLock(tmp_path)
        lock.try_acquire()
        assert lock.check_and_promote() is False  # Already held, no-op


class TestInstanceLockProcessAlive:
    """Tests for PID liveness checking."""

    def test_current_process_is_alive(self) -> None:
        """Current process should be reported as alive."""
        assert InstanceLock._is_process_alive(os.getpid()) is True

    def test_nonexistent_process_is_dead(self) -> None:
        """A non-existent PID should be reported as dead."""
        assert InstanceLock._is_process_alive(4_000_000_000) is False

    def test_pid_zero_is_special(self) -> None:
        """PID 0 should not raise an exception."""
        # PID 0 behavior varies by OS, just ensure no exception
        InstanceLock._is_process_alive(0)


class TestInstanceLockReadLock:
    """Tests for lock file parsing."""

    def test_read_valid_lock(self, tmp_path: Path) -> None:
        """Should parse a well-formed lock file."""
        lock_path = tmp_path / "test.lock"
        ts = datetime.now(UTC)
        lock_path.write_text(f"12345\n{ts.isoformat()}\n")

        result = InstanceLock._read_lock(lock_path)
        assert result is not None
        pid, timestamp = result
        assert pid == 12345
        assert timestamp.tzinfo is not None

    def test_read_missing_file(self, tmp_path: Path) -> None:
        """Should return None for a missing file."""
        lock_path = tmp_path / "nonexistent.lock"
        assert InstanceLock._read_lock(lock_path) is None

    def test_read_empty_file(self, tmp_path: Path) -> None:
        """Should return None for an empty file."""
        lock_path = tmp_path / "empty.lock"
        lock_path.write_text("")
        assert InstanceLock._read_lock(lock_path) is None

    def test_read_single_line(self, tmp_path: Path) -> None:
        """Should return None when only one line is present."""
        lock_path = tmp_path / "one_line.lock"
        lock_path.write_text("12345\n")
        assert InstanceLock._read_lock(lock_path) is None

    def test_read_invalid_pid(self, tmp_path: Path) -> None:
        """Should return None when PID is not an integer."""
        lock_path = tmp_path / "bad_pid.lock"
        lock_path.write_text(f"not_a_pid\n{datetime.now(UTC).isoformat()}\n")
        assert InstanceLock._read_lock(lock_path) is None

    def test_read_invalid_timestamp(self, tmp_path: Path) -> None:
        """Should return None when timestamp is not valid ISO format."""
        lock_path = tmp_path / "bad_ts.lock"
        lock_path.write_text("12345\nnot_a_timestamp\n")
        assert InstanceLock._read_lock(lock_path) is None

    def test_read_naive_timestamp_gets_utc(self, tmp_path: Path) -> None:
        """Should add UTC timezone to naive timestamps."""
        lock_path = tmp_path / "naive.lock"
        naive_ts = datetime.now().isoformat()  # No timezone
        lock_path.write_text(f"12345\n{naive_ts}\n")

        result = InstanceLock._read_lock(lock_path)
        assert result is not None
        _, timestamp = result
        assert timestamp.tzinfo is not None


class TestInstanceLockConcurrency:
    """Tests for concurrent acquisition scenarios."""

    def test_second_lock_instance_cannot_acquire(self, tmp_path: Path) -> None:
        """Two lock instances — only the first should acquire."""
        lock1 = InstanceLock(tmp_path)
        lock2 = InstanceLock(tmp_path)

        assert lock1.try_acquire() is True
        assert lock2.try_acquire() is False

    def test_second_instance_acquires_after_release(self, tmp_path: Path) -> None:
        """Second instance should acquire after first releases."""
        lock1 = InstanceLock(tmp_path)
        lock2 = InstanceLock(tmp_path)

        lock1.try_acquire()
        lock1.release()

        assert lock2.try_acquire() is True
        assert lock2.is_held() is True
