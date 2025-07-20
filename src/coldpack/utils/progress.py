"""Rich progress display system and progress tracking utilities."""

import time
from typing import Any, Callable, Optional

from loguru import logger
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from ..config.constants import PROGRESS_UPDATE_INTERVAL


class ProgressInfo:
    """Information about operation progress."""

    def __init__(
        self,
        operation: str,
        percentage: float = 0.0,
        current_file: str = "",
        processed_files: int = 0,
        total_files: int = 0,
        processed_size: int = 0,
        total_size: int = 0,
        speed: float = 0.0,
        eta: float = 0.0,
    ):
        """Initialize progress information.

        Args:
            operation: Current operation name
            percentage: Completion percentage (0.0-100.0)
            current_file: Currently processed file
            processed_files: Number of files processed
            total_files: Total number of files
            processed_size: Bytes processed
            total_size: Total bytes to process
            speed: Processing speed in bytes/second
            eta: Estimated time to completion in seconds
        """
        self.operation = operation
        self.percentage = percentage
        self.current_file = current_file
        self.processed_files = processed_files
        self.total_files = total_files
        self.processed_size = processed_size
        self.total_size = total_size
        self.speed = speed
        self.eta = eta


class ProgressTracker:
    """Advanced progress tracker with Rich console display."""

    def __init__(
        self,
        console: Optional[Console] = None,
        show_speed: bool = True,
        show_eta: bool = True,
    ):
        """Initialize progress tracker.

        Args:
            console: Rich console instance (creates new if None)
            show_speed: Whether to show processing speed
            show_eta: Whether to show estimated time remaining
        """
        self.console = console or Console()
        self.show_speed = show_speed
        self.show_eta = show_eta
        self._progress: Optional[Progress] = None
        self._tasks: dict[str, TaskID] = {}
        self._start_times: dict[str, float] = {}
        self._last_update: dict[str, float] = {}

    def __enter__(self) -> "ProgressTracker":
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.stop()

    def start(self) -> None:
        """Start the progress display."""
        if self._progress is None:
            columns = [
                SpinnerColumn(),
                TextColumn("[bold blue]{task.fields[operation]}", justify="left"),
                BarColumn(bar_width=None),
                TaskProgressColumn(),
                MofNCompleteColumn(),
                TextColumn("[green]{task.fields[current_file]}", justify="left"),
            ]

            if self.show_speed:
                columns.append(TextColumn("[yellow]{task.fields[speed]}"))

            if self.show_eta:
                columns.extend(
                    [
                        TimeElapsedColumn(),
                        TimeRemainingColumn(),
                    ]
                )

            self._progress = Progress(*columns, console=self.console)
            self._progress.start()

    def stop(self) -> None:
        """Stop the progress display."""
        if self._progress:
            self._progress.stop()
            self._progress = None
            self._tasks.clear()
            self._start_times.clear()
            self._last_update.clear()

    def add_task(self, operation: str, total: int = 100, **kwargs: Any) -> str:
        """Add a new progress task.

        Args:
            operation: Operation name
            total: Total units for this task
            **kwargs: Additional task fields

        Returns:
            Task identifier string
        """
        if not self._progress:
            self.start()

        task_fields = {
            "operation": operation,
            "current_file": "",
            "speed": "",
            **kwargs,
        }

        # _progress is guaranteed to be not None after start()
        assert self._progress is not None
        task_id = self._progress.add_task(operation, total=total, **task_fields)

        task_key = f"{operation}_{id(task_id)}"
        self._tasks[task_key] = task_id
        self._start_times[task_key] = time.time()
        self._last_update[task_key] = time.time()

        logger.debug(f"Added progress task: {operation} (total: {total})")
        return task_key

    def update_task(
        self,
        task_key: str,
        advance: int = 0,
        completed: Optional[int] = None,
        current_file: str = "",
        **kwargs: Any,
    ) -> None:
        """Update a progress task.

        Args:
            task_key: Task identifier
            advance: Amount to advance progress
            completed: Set absolute completion amount
            current_file: Currently processing file
            **kwargs: Additional fields to update
        """
        if task_key not in self._tasks or not self._progress:
            return

        assert self._progress is not None
        task_id = self._tasks[task_key]
        current_time = time.time()

        # Throttle updates to avoid too frequent refreshes
        if (
            current_time - self._last_update.get(task_key, 0)
        ) < PROGRESS_UPDATE_INTERVAL:
            return

        # Calculate speed if we have timing data
        speed_text = ""
        if self.show_speed and advance > 0:
            elapsed = current_time - self._start_times[task_key]
            if elapsed > 0:
                total_completed = self._progress.tasks[task_id].completed + advance
                speed = total_completed / elapsed
                if speed > 1024 * 1024:  # MB/s
                    speed_text = f"{speed / (1024 * 1024):.1f} MB/s"
                elif speed > 1024:  # KB/s
                    speed_text = f"{speed / 1024:.1f} KB/s"
                else:  # B/s
                    speed_text = f"{speed:.0f} B/s"

        # Update task
        update_kwargs = {
            "current_file": current_file or "",
            "speed": speed_text,
            **kwargs,
        }

        if completed is not None:
            self._progress.update(task_id, completed=completed, **update_kwargs)
        else:
            self._progress.update(task_id, advance=advance, **update_kwargs)

        self._last_update[task_key] = current_time

    def complete_task(self, task_key: str, message: str = "") -> None:
        """Complete a progress task.

        Args:
            task_key: Task identifier
            message: Completion message
        """
        if task_key not in self._tasks or not self._progress:
            return

        assert self._progress is not None
        task_id = self._tasks[task_key]
        self._progress.update(
            task_id,
            completed=self._progress.tasks[task_id].total,
            current_file=message or "Completed",
        )

        logger.debug(f"Completed progress task: {task_key}")

    def remove_task(self, task_key: str) -> None:
        """Remove a progress task.

        Args:
            task_key: Task identifier
        """
        if task_key not in self._tasks or not self._progress:
            return

        assert self._progress is not None
        task_id = self._tasks[task_key]
        self._progress.remove_task(task_id)

        del self._tasks[task_key]
        del self._start_times[task_key]
        if task_key in self._last_update:
            del self._last_update[task_key]

        logger.debug(f"Removed progress task: {task_key}")


def create_progress_callback(
    progress_tracker: ProgressTracker, task_key: str, operation: str = ""
) -> Callable:
    """Create a progress callback function for use with other modules.

    Args:
        progress_tracker: Progress tracker instance
        task_key: Task identifier
        operation: Operation name for logging

    Returns:
        Progress callback function
    """

    def progress_callback(
        percentage: float = 0.0,
        current: int = 0,
        total: int = 0,
        current_file: str = "",
        **kwargs: Any,
    ) -> None:
        """Progress callback function.

        Args:
            percentage: Completion percentage (0.0-100.0)
            current: Current progress value
            total: Total progress value
            current_file: Currently processing file
            **kwargs: Additional update parameters
        """
        if total > 0:
            progress_tracker.update_task(
                task_key, completed=current, current_file=current_file, **kwargs
            )
        else:
            # If no total, advance by some amount
            progress_tracker.update_task(
                task_key, advance=1, current_file=current_file, **kwargs
            )

    return progress_callback


class SimpleProgressBar:
    """Simple console progress bar for non-Rich environments."""

    def __init__(self, total: int, description: str = "", width: int = 50):
        """Initialize simple progress bar.

        Args:
            total: Total units
            description: Description text
            width: Progress bar width in characters
        """
        self.total = total
        self.description = description
        self.width = width
        self.current = 0
        self.start_time = time.time()

    def update(self, advance: int = 1) -> None:
        """Update progress bar.

        Args:
            advance: Amount to advance
        """
        self.current = min(self.current + advance, self.total)
        self._display()

    def set_progress(self, value: int) -> None:
        """Set absolute progress value.

        Args:
            value: Progress value
        """
        self.current = min(value, self.total)
        self._display()

    def _display(self) -> None:
        """Display the progress bar."""
        if self.total == 0:
            return

        percentage = (self.current / self.total) * 100
        filled_width = int((self.current / self.total) * self.width)
        bar = "█" * filled_width + "░" * (self.width - filled_width)

        elapsed = time.time() - self.start_time
        if self.current > 0 and elapsed > 0:
            speed = self.current / elapsed
            eta = (self.total - self.current) / speed if speed > 0 else 0
            eta_str = f"ETA: {eta:.0f}s" if eta > 0 else ""
        else:
            eta_str = ""

        print(
            f"\r{self.description} [{bar}] {percentage:.1f}% ({self.current}/{self.total}) {eta_str}",
            end="",
            flush=True,
        )

        if self.current >= self.total:
            print()  # New line when complete


def display_operation_summary(
    operations: dict[str, Any], console: Optional[Console] = None
) -> None:
    """Display a summary of completed operations.

    Args:
        operations: Dictionary of operation names to results
        console: Rich console instance
    """
    if console is None:
        console = Console()

    table = Table(
        title="Operation Summary", show_header=True, header_style="bold magenta"
    )
    table.add_column("Operation", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Files Processed", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Duration", justify="right")

    for operation_name, result in operations.items():
        status = "✓ Success" if result.get("success", False) else "✗ Failed"
        status_style = "green" if result.get("success", False) else "red"

        table.add_row(
            operation_name,
            f"[{status_style}]{status}[/{status_style}]",
            str(result.get("files_processed", 0)),
            format_bytes(result.get("bytes_processed", 0)),
            f"{result.get('duration', 0):.1f}s",
        )

    console.print(table)


def format_bytes(bytes_value: int) -> str:
    """Format bytes in human-readable format.

    Args:
        bytes_value: Size in bytes

    Returns:
        Formatted size string
    """
    if bytes_value >= 1024**3:
        return f"{bytes_value / (1024**3):.1f} GB"
    elif bytes_value >= 1024**2:
        return f"{bytes_value / (1024**2):.1f} MB"
    elif bytes_value >= 1024:
        return f"{bytes_value / 1024:.1f} KB"
    else:
        return f"{bytes_value} B"


def create_status_console() -> Console:
    """Create a console instance optimized for status display.

    Returns:
        Configured Rich console
    """
    return Console(force_terminal=True, width=120, legacy_windows=False)
