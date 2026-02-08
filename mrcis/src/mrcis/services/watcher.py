"""File watcher service for detecting repository changes.

Uses watchdog for cross-platform file monitoring with
debouncing to handle rapid successive events.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from mrcis.config.models import RepositoryConfig
from mrcis.services.file_filter import FileInclusionPolicy


@dataclass
class FileEvent:
    """Represents a file system event."""

    type: str  # created, modified, deleted, moved
    path: Path
    repository: str


class FileChangeHandler(FileSystemEventHandler):
    """Handles file system events and queues them for processing."""

    def __init__(
        self,
        queue: "asyncio.Queue[FileEvent]",
        repo_config: RepositoryConfig,
    ) -> None:
        self.queue = queue
        self.repo = repo_config
        self.file_filter = FileInclusionPolicy(repo_config.path)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for async queue operations."""
        self._loop = loop

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event."""
        if event.is_directory:
            return

        src_path = event.src_path
        if isinstance(src_path, bytes):
            src_path = src_path.decode("utf-8")
        path = Path(src_path)

        # Check if file should be indexed
        if not self.file_filter.should_index(path):
            return

        # Skip SQLite temporary files (journal, WAL, shared memory)
        name = path.name
        if name.endswith(("-journal", "-wal", "-shm")):
            return

        # Queue the event
        if self._loop is not None:
            # Handle move/rename events by emitting delete + create
            if event.event_type == "moved" and hasattr(event, "dest_path"):
                dest_path = event.dest_path
                if isinstance(dest_path, bytes):
                    dest_path = dest_path.decode("utf-8")
                dest = Path(dest_path)

                # Queue delete for old path
                self._loop.call_soon_threadsafe(
                    self.queue.put_nowait,
                    FileEvent(
                        type="deleted",
                        path=path,
                        repository=self.repo.name,
                    ),
                )

                # Queue create for new path (if should be indexed)
                if self.file_filter.should_index(dest):
                    self._loop.call_soon_threadsafe(
                        self.queue.put_nowait,
                        FileEvent(
                            type="created",
                            path=dest,
                            repository=self.repo.name,
                        ),
                    )
            else:
                self._loop.call_soon_threadsafe(
                    self.queue.put_nowait,
                    FileEvent(
                        type=event.event_type,
                        path=path,
                        repository=self.repo.name,
                    ),
                )


class FileWatcher:
    """
    Watches repository directories for changes.

    Uses watchdog for cross-platform file monitoring
    with debouncing to handle rapid successive events.

    Configuration is injected from config file.
    """

    def __init__(
        self,
        repo_configs: dict[str, RepositoryConfig],
        debounce_ms: int = 500,
    ) -> None:
        self.repo_configs = repo_configs  # Config is authoritative
        self.debounce_ms = debounce_ms

        self._queue: asyncio.Queue[FileEvent] = asyncio.Queue()
        self._observers: list[Any] = []  # watchdog.observers.Observer instances
        self._pending: dict[str, FileEvent] = {}  # path -> latest event
        self._shutdown_event = asyncio.Event()
        self._callbacks: list[Callable[[FileEvent], Awaitable[None]]] = []

    def on_change(self, callback: Callable[[FileEvent], Awaitable[None]]) -> None:
        """Register callback for file changes."""
        self._callbacks.append(callback)

    async def start(self) -> None:
        """Start watching all repositories."""
        logger.info("File watcher starting: repos={}", list(self.repo_configs.keys()))

        loop = asyncio.get_event_loop()

        # Start watchdog observers
        for repo_config in self.repo_configs.values():
            observer = Observer()
            handler = FileChangeHandler(self._queue, repo_config)
            handler.set_loop(loop)
            observer.schedule(handler, str(repo_config.path), recursive=True)
            observer.start()
            self._observers.append(observer)

        # Start event processing loop
        await self._process_events()

    async def stop(self) -> None:
        """Stop all observers."""
        self._shutdown_event.set()

        for observer in self._observers:
            observer.stop()
            observer.join(timeout=5)

        logger.info("File watcher stopped")

    async def _process_events(self) -> None:
        """Process events with debouncing."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                # Store/update pending event for this path
                key = str(event.path)
                self._pending[key] = event

            except TimeoutError:
                pass

            # Process debounced events
            await self._flush_pending()

    async def _flush_pending(self) -> None:
        """Flush pending events that have been debounced long enough."""
        if not self._pending:
            return

        # In a real implementation, track timestamps per event
        # For simplicity, flush all pending after debounce period
        await asyncio.sleep(self.debounce_ms / 1000)

        events = list(self._pending.values())
        self._pending.clear()

        for event in events:
            for callback in self._callbacks:
                try:
                    await callback(event)
                except Exception as e:
                    logger.error("Watcher callback error: {}", e)
