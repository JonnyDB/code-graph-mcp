"""File-based lock for coordinating multiple server instances.

Enables one writer instance (indexing, watching, resolving) with
multiple read-only instances sharing the same storage directory.
"""

import os
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

_LOCK_FILENAME = "mrcis.lock"
_LOCK_TMP_FILENAME = "mrcis.lock.tmp"


class InstanceLock:
    """PID+timestamp file lock for single-writer coordination.

    The lock file contains the writer's PID and a UTC timestamp on
    separate lines. Staleness is determined by checking whether the
    PID is still alive and whether the timestamp has expired.

    Acquisition uses ``O_CREAT | O_EXCL`` for atomicity. Replacement
    of a stale lock uses a temp file + ``os.replace()`` for safety.
    """

    def __init__(
        self,
        data_directory: Path,
        heartbeat_seconds: int = 30,
        stale_seconds: int = 90,
    ) -> None:
        self._lock_path = data_directory / _LOCK_FILENAME
        self._tmp_path = data_directory / _LOCK_TMP_FILENAME
        self.heartbeat_seconds = heartbeat_seconds
        self.stale_seconds = stale_seconds
        self._held = False

    @property
    def lock_path(self) -> Path:
        """Return the lock file path (useful for tests)."""
        return self._lock_path

    def try_acquire(self) -> bool:
        """Try to acquire the writer lock.

        Returns:
            True if this instance now holds the lock.
        """
        if self._held:
            return True

        # Attempt atomic creation
        try:
            fd = os.open(
                str(self._lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
            try:
                self._write_lock_content(fd)
            finally:
                os.close(fd)
            self._held = True
            logger.debug("Lock acquired (new file)")
            return True
        except FileExistsError:
            pass

        # Lock file exists — check if it's stale
        lock_info = self._read_lock(self._lock_path)
        if lock_info is None:
            # Malformed lock file — treat as stale
            return self._replace_stale_lock()

        pid, timestamp = lock_info
        if self._is_stale(pid, timestamp):
            return self._replace_stale_lock()

        return False

    def release(self) -> None:
        """Release the lock by deleting the file. No-op if not held."""
        if not self._held:
            return
        try:
            self._lock_path.unlink()
            logger.debug("Lock released")
        except FileNotFoundError:
            pass
        self._held = False

    def is_held(self) -> bool:
        """Check if this instance holds the lock."""
        return self._held

    def heartbeat(self) -> None:
        """Update the lock file timestamp. No-op if not held."""
        if not self._held:
            return
        self._write_lock_atomic()
        logger.trace("Lock heartbeat updated")

    def check_and_promote(self) -> bool:
        """Check if the current lock is stale and try to take over.

        Returns:
            True if this instance promoted itself to writer.
        """
        if self._held:
            return False

        lock_info = self._read_lock(self._lock_path)
        if lock_info is None:
            # Lock disappeared or is malformed — try to acquire fresh
            return self.try_acquire()

        pid, timestamp = lock_info
        if self._is_stale(pid, timestamp):
            return self._replace_stale_lock()

        return False

    def _is_stale(self, pid: int, timestamp: datetime) -> bool:
        """Determine if a lock is stale based on PID liveness and timestamp age."""
        if not self._is_process_alive(pid):
            logger.debug("Lock holder PID {} is dead — lock is stale", pid)
            return True

        age = (datetime.now(UTC) - timestamp).total_seconds()
        if age > self.stale_seconds:
            logger.debug(
                "Lock timestamp is {}s old (threshold {}s) — lock is stale",
                int(age),
                self.stale_seconds,
            )
            return True

        return False

    def _replace_stale_lock(self) -> bool:
        """Replace a stale lock file atomically.

        Returns:
            True if replacement succeeded and lock is now held.
        """
        try:
            self._write_lock_atomic()
            self._held = True
            logger.debug("Replaced stale lock")
            return True
        except OSError:
            logger.warning("Failed to replace stale lock", exc_info=True)
            return False

    def _write_lock_content(self, fd: int) -> None:
        """Write PID and timestamp to an open file descriptor."""
        content = f"{os.getpid()}\n{datetime.now(UTC).isoformat()}\n"
        os.write(fd, content.encode())

    def _write_lock_atomic(self) -> None:
        """Write lock content to a temp file and atomically replace."""
        content = f"{os.getpid()}\n{datetime.now(UTC).isoformat()}\n"
        tmp = str(self._tmp_path)
        fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
        try:
            os.write(fd, content.encode())
        finally:
            os.close(fd)
        Path(tmp).replace(self._lock_path)

    @staticmethod
    def _read_lock(path: Path) -> tuple[int, datetime] | None:
        """Read PID and timestamp from a lock file.

        Returns:
            (pid, timestamp) tuple, or None if the file is missing or malformed.
        """
        try:
            text = path.read_text().strip()
        except (FileNotFoundError, PermissionError):
            return None

        lines = text.splitlines()
        if len(lines) < 2:
            return None

        try:
            pid = int(lines[0])
            timestamp = datetime.fromisoformat(lines[1])
            # Ensure timezone-aware
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return pid, timestamp
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _is_process_alive(pid: int) -> bool:
        """Check whether a process with the given PID is running.

        Uses ``os.kill(pid, 0)`` which sends no signal but checks existence.
        """
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but belongs to another user
            return True
        except (OSError, OverflowError):
            return False
