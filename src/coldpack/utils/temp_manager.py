"""Enhanced temporary file and directory management with Windows-safe cleanup.

This module provides comprehensive temporary file management with:
- Automatic cleanup on process exit (atexit)
- Signal handling for graceful shutdown
- Windows-specific file lock handling
- Retry mechanisms for Windows cleanup issues
- Global tracking of all temporary resources
"""

import atexit
import gc
import os
import platform
import shutil
import signal
import tempfile
import threading
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Optional, Union

from loguru import logger

from ..config.constants import TEMP_DIR_PREFIX


class WindowsTempCleanupError(Exception):
    """Raised when temporary cleanup fails on Windows."""

    pass


class GlobalTempManager:
    """Global manager for temporary files and directories with safe cleanup.

    This singleton class tracks all temporary resources created by the application
    and ensures they are properly cleaned up even if the process is interrupted.
    """

    _instance: Optional["GlobalTempManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "GlobalTempManager":
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the global temp manager."""
        if hasattr(self, "_initialized") and getattr(self, "_initialized", False):
            return

        self._initialized: bool = False

        self._temp_dirs: set[Path] = set()
        self._temp_files: set[Path] = set()
        self._cleanup_registered = False
        self._is_windows = platform.system().lower() == "windows"
        self._shutdown_in_progress = False
        self._lock = threading.Lock()

        # Register cleanup handlers
        self._register_cleanup_handlers()
        self._initialized = True

        logger.debug("Global temporary file manager initialized")

    def _register_cleanup_handlers(self) -> None:
        """Register cleanup handlers for process exit and signals."""
        if self._cleanup_registered:
            return

        # Register atexit handler
        atexit.register(self._cleanup_all_temp_resources)

        # Register signal handlers for graceful shutdown
        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, self._signal_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, self._signal_handler)

        # Windows-specific signal handling
        if self._is_windows and hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self._signal_handler)

        self._cleanup_registered = True
        logger.debug("Cleanup handlers registered")

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle process signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, cleaning up temporary resources...")
        self._cleanup_all_temp_resources()

        # Re-raise the signal with default handler
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def create_temp_directory(
        self, suffix: str = "", prefix: str = TEMP_DIR_PREFIX, auto_cleanup: bool = True
    ) -> Path:
        """Create a temporary directory with automatic tracking.

        Args:
            suffix: Suffix for the directory name
            prefix: Prefix for the directory name
            auto_cleanup: Whether to automatically cleanup on exit

        Returns:
            Path to the created temporary directory

        Raises:
            OSError: If directory creation fails
        """
        try:
            temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
            temp_path = Path(temp_dir)

            # Set secure permissions (owner only)
            if not self._is_windows:
                os.chmod(temp_path, 0o700)
            else:
                # On Windows, rely on default NTFS permissions
                pass

            if auto_cleanup:
                with self._lock:
                    self._temp_dirs.add(temp_path)

            logger.debug(f"Created temporary directory: {temp_path}")
            return temp_path

        except OSError as e:
            logger.error(f"Failed to create temporary directory: {e}")
            raise

    def create_temp_file(
        self, suffix: str = "", prefix: str = TEMP_DIR_PREFIX, auto_cleanup: bool = True
    ) -> Path:
        """Create a temporary file with automatic tracking.

        Args:
            suffix: Suffix for the file name
            prefix: Prefix for the file name
            auto_cleanup: Whether to automatically cleanup on exit

        Returns:
            Path to the created temporary file

        Raises:
            OSError: If file creation fails
        """
        try:
            fd, temp_file = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            os.close(fd)  # Close file descriptor, keep the file
            temp_path = Path(temp_file)

            if auto_cleanup:
                with self._lock:
                    self._temp_files.add(temp_path)

            logger.debug(f"Created temporary file: {temp_path}")
            return temp_path

        except OSError as e:
            logger.error(f"Failed to create temporary file: {e}")
            raise

    def track_temp_directory(self, temp_dir: Union[str, Path]) -> None:
        """Track an existing temporary directory for cleanup.

        Args:
            temp_dir: Path to the temporary directory to track
        """
        temp_path = Path(temp_dir)
        with self._lock:
            self._temp_dirs.add(temp_path)
        logger.debug(f"Tracking temporary directory: {temp_path}")

    def track_temp_file(self, temp_file: Union[str, Path]) -> None:
        """Track an existing temporary file for cleanup.

        Args:
            temp_file: Path to the temporary file to track
        """
        temp_path = Path(temp_file)
        with self._lock:
            self._temp_files.add(temp_path)
        logger.debug(f"Tracking temporary file: {temp_path}")

    def cleanup_temp_directory(
        self, temp_dir: Union[str, Path], force: bool = True
    ) -> bool:
        """Clean up a specific temporary directory.

        Args:
            temp_dir: Path to the temporary directory
            force: If True, use aggressive cleanup for Windows

        Returns:
            True if cleanup was successful
        """
        temp_path = Path(temp_dir)

        if not temp_path.exists():
            logger.debug(f"Temporary directory already removed: {temp_path}")
            with self._lock:
                self._temp_dirs.discard(temp_path)
            return True

        success = self._remove_directory_safely(temp_path, force=force)

        if success:
            with self._lock:
                self._temp_dirs.discard(temp_path)

        return success

    def cleanup_temp_file(
        self, temp_file: Union[str, Path], force: bool = True
    ) -> bool:
        """Clean up a specific temporary file.

        Args:
            temp_file: Path to the temporary file
            force: If True, use aggressive cleanup for Windows

        Returns:
            True if cleanup was successful
        """
        temp_path = Path(temp_file)

        if not temp_path.exists():
            logger.debug(f"Temporary file already removed: {temp_path}")
            with self._lock:
                self._temp_files.discard(temp_path)
            return True

        success = self._remove_file_safely(temp_path, force=force)

        if success:
            with self._lock:
                self._temp_files.discard(temp_path)

        return success

    def _remove_file_safely(self, file_path: Path, force: bool = True) -> bool:
        """Safely remove a file with Windows-specific handling and disk space awareness.

        Args:
            file_path: Path to the file to remove
            force: If True, use aggressive cleanup methods

        Returns:
            True if removal was successful
        """
        if not file_path.exists():
            return True

        try:
            # Try normal removal first
            file_path.unlink()
            with suppress(Exception):
                logger.debug(f"Successfully removed temporary file: {file_path}")
            return True

        except OSError as e:
            # Check if error might be related to disk space
            is_disk_full_error = (
                "No space left on device" in str(e)
                or "There is not enough space on the disk" in str(e)
                or e.errno == 28  # ENOSPC: No space left on device
            )

            if not force:
                with suppress(Exception):
                    logger.warning(f"Failed to remove temporary file {file_path}: {e}")
                return False

            # For disk full errors, be even more aggressive
            if is_disk_full_error or self._is_windows:
                return self._windows_aggressive_file_removal(
                    file_path, is_emergency=is_disk_full_error
                )
            else:
                with suppress(Exception):
                    logger.warning(f"Failed to remove temporary file {file_path}: {e}")
                return False

    def _remove_directory_safely(self, dir_path: Path, force: bool = True) -> bool:
        """Safely remove a directory with Windows-specific handling.

        Args:
            dir_path: Path to the directory to remove
            force: If True, use aggressive cleanup methods

        Returns:
            True if removal was successful
        """
        if not dir_path.exists():
            return True

        try:
            # Try normal removal first
            shutil.rmtree(dir_path)
            logger.debug(f"Successfully removed temporary directory: {dir_path}")
            return True

        except OSError as e:
            if not force:
                logger.warning(f"Failed to remove temporary directory {dir_path}: {e}")
                return False

            # Windows-specific aggressive cleanup
            if self._is_windows:
                return self._windows_aggressive_directory_removal(dir_path)
            else:
                logger.warning(f"Failed to remove temporary directory {dir_path}: {e}")
                return False

    def _windows_aggressive_file_removal(
        self, file_path: Path, is_emergency: bool = False
    ) -> bool:
        """Aggressive file removal for Windows with retry and file unlocking.

        Args:
            file_path: Path to the file to remove
            is_emergency: If True, use emergency cleanup mode for disk full situations

        Returns:
            True if removal was successful
        """
        max_attempts = 10 if is_emergency else 5
        delay = 0.05 if is_emergency else 0.1

        for attempt in range(max_attempts):
            try:
                # Try to remove read-only attribute (owner permissions only for security)
                with suppress(OSError):
                    file_path.chmod(0o700)

                # Try to close any open handles (force garbage collection)
                gc.collect()

                # In emergency mode, try even more aggressive cleanup
                if is_emergency and attempt > 2:
                    # Force multiple garbage collections
                    for _ in range(3):
                        gc.collect()

                    # Try to truncate file first to free space immediately
                    try:
                        with suppress(OSError), open(file_path, "w") as f:
                            f.truncate(0)
                    except Exception as e:
                        # Log truncation failure but continue with cleanup attempt
                        with suppress(Exception):
                            logger.debug(
                                f"Failed to truncate file {file_path} during emergency cleanup: {e}"
                            )

                # Try removal
                file_path.unlink()
                with suppress(Exception):
                    if is_emergency:
                        logger.debug(
                            f"Emergency removal successful for file: {file_path}"
                        )
                    else:
                        logger.debug(
                            f"Aggressive removal successful for file: {file_path}"
                        )
                return True

            except OSError as e:
                if attempt < max_attempts - 1:
                    with suppress(Exception):
                        if is_emergency:
                            logger.debug(
                                f"Emergency attempt {attempt + 1} failed for {file_path}: {e}, retrying..."
                            )
                        else:
                            logger.debug(
                                f"Attempt {attempt + 1} failed for {file_path}: {e}, retrying..."
                            )
                    time.sleep(delay)
                    delay *= 1.5  # Slower exponential backoff in emergency mode
                else:
                    with suppress(Exception):
                        logger.warning(
                            f"All attempts failed to remove file {file_path}: {e}"
                        )
                    return False

        return False

    def _windows_aggressive_directory_removal(self, dir_path: Path) -> bool:
        """Aggressive directory removal for Windows with retry and file unlocking.

        Args:
            dir_path: Path to the directory to remove

        Returns:
            True if removal was successful
        """
        max_attempts = 5
        delay = 0.1

        for attempt in range(max_attempts):
            try:
                # Try to remove read-only attributes recursively (owner permissions only for security)
                with suppress(OSError):
                    for root, dirs, files in os.walk(dir_path):
                        for d in dirs:
                            os.chmod(os.path.join(root, d), 0o700)
                        for f in files:
                            os.chmod(os.path.join(root, f), 0o700)

                # Force garbage collection to close any handles
                gc.collect()

                # Try removal with error handler for individual files
                def handle_remove_readonly(func: Any, path: str, exc: Any) -> None:
                    """Error handler for shutil.rmtree on Windows."""
                    with suppress(OSError):
                        os.chmod(path, 0o700)  # Owner permissions only for security
                        func(path)

                shutil.rmtree(dir_path, onerror=handle_remove_readonly)
                logger.debug(f"Aggressive removal successful for directory: {dir_path}")
                return True

            except OSError as e:
                if attempt < max_attempts - 1:
                    logger.debug(
                        f"Attempt {attempt + 1} failed for {dir_path}: {e}, retrying..."
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.warning(
                        f"All attempts failed to remove directory {dir_path}: {e}"
                    )
                    return False

        return False

    def _cleanup_all_temp_resources(self) -> None:
        """Clean up all tracked temporary resources with disk space handling."""
        if self._shutdown_in_progress:
            return

        self._shutdown_in_progress = True

        # Use minimal logging to avoid I/O issues when disk is full
        with suppress(Exception):
            logger.debug("Starting cleanup of all temporary resources")

        cleaned_files = 0
        cleaned_dirs = 0
        failed_files = 0
        failed_dirs = 0

        # Clean up files first (these free up space immediately)
        try:
            with self._lock:
                temp_files = self._temp_files.copy()
        except Exception:
            # If we can't even copy the set, try to work with original
            temp_files = (
                set(self._temp_files) if hasattr(self, "_temp_files") else set()
            )

        for temp_file in temp_files:
            try:
                if self._remove_file_safely(temp_file, force=True):
                    cleaned_files += 1
                else:
                    failed_files += 1
            except Exception as e:
                # Continue cleanup even if individual file cleanup fails
                failed_files += 1
                # Log cleanup failure with minimal I/O to avoid issues when disk is full
                with suppress(Exception):
                    logger.debug(f"Failed to cleanup temp file {temp_file}: {e}")
                continue

        # Clean up directories (should have more space available now)
        try:
            with self._lock:
                temp_dirs = self._temp_dirs.copy()
        except Exception:
            # If we can't copy the set, try to work with original
            temp_dirs = set(self._temp_dirs) if hasattr(self, "_temp_dirs") else set()

        for temp_dir in temp_dirs:
            try:
                if self._remove_directory_safely(temp_dir, force=True):
                    cleaned_dirs += 1
                else:
                    failed_dirs += 1
            except Exception as e:
                # Continue cleanup even if individual directory cleanup fails
                failed_dirs += 1
                # Log cleanup failure with minimal I/O to avoid issues when disk is full
                with suppress(Exception):
                    logger.debug(f"Failed to cleanup temp directory {temp_dir}: {e}")
                continue

        # Clear tracking sets (handle potential memory/disk issues)
        try:
            with self._lock:
                self._temp_files.clear()
                self._temp_dirs.clear()
        except Exception as e:
            # If clearing fails, try individual clearing
            with suppress(Exception):
                logger.debug(f"Failed to clear tracking sets in bulk: {e}")
            try:
                if hasattr(self, "_temp_files"):
                    self._temp_files.clear()
            except Exception as e:
                with suppress(Exception):
                    logger.debug(f"Failed to clear temp files tracking set: {e}")
            try:
                if hasattr(self, "_temp_dirs"):
                    self._temp_dirs.clear()
            except Exception as e:
                with suppress(Exception):
                    logger.debug(f"Failed to clear temp dirs tracking set: {e}")

        # Log results only if logging is available
        with suppress(Exception):
            if cleaned_files > 0 or cleaned_dirs > 0:
                logger.info(
                    f"Cleanup complete: {cleaned_files} files, {cleaned_dirs} directories removed"
                )

            if failed_files > 0 or failed_dirs > 0:
                logger.warning(
                    f"Cleanup incomplete: {failed_files} files, {failed_dirs} directories failed to remove"
                )

    def get_tracked_resources(self) -> tuple[set[Path], set[Path]]:
        """Get currently tracked temporary resources.

        Returns:
            Tuple of (temp_directories, temp_files)
        """
        with self._lock:
            return self._temp_dirs.copy(), self._temp_files.copy()

    def force_cleanup_all(self) -> None:
        """Force immediate cleanup of all temporary resources."""
        self._cleanup_all_temp_resources()


# Global instance (lazy initialization)
_global_temp_manager: Optional[GlobalTempManager] = None


def _get_global_temp_manager() -> GlobalTempManager:
    """Get the global temporary file manager instance with lazy initialization."""
    global _global_temp_manager
    if _global_temp_manager is None:
        _global_temp_manager = GlobalTempManager()
    return _global_temp_manager


# Public API functions for convenience
def create_temp_directory(suffix: str = "", prefix: str = TEMP_DIR_PREFIX) -> Path:
    """Create a temporary directory with automatic cleanup.

    Args:
        suffix: Suffix for the directory name
        prefix: Prefix for the directory name

    Returns:
        Path to the created temporary directory
    """
    return _get_global_temp_manager().create_temp_directory(
        suffix=suffix, prefix=prefix
    )


def create_temp_file(suffix: str = "", prefix: str = TEMP_DIR_PREFIX) -> Path:
    """Create a temporary file with automatic cleanup.

    Args:
        suffix: Suffix for the file name
        prefix: Prefix for the file name

    Returns:
        Path to the created temporary file
    """
    return _get_global_temp_manager().create_temp_file(suffix=suffix, prefix=prefix)


def track_temp_directory(temp_dir: Union[str, Path]) -> None:
    """Track an existing temporary directory for cleanup.

    Args:
        temp_dir: Path to the temporary directory to track
    """
    _get_global_temp_manager().track_temp_directory(temp_dir)


def track_temp_file(temp_file: Union[str, Path]) -> None:
    """Track an existing temporary file for cleanup.

    Args:
        temp_file: Path to the temporary file to track
    """
    _get_global_temp_manager().track_temp_file(temp_file)


def cleanup_temp_directory(temp_dir: Union[str, Path]) -> bool:
    """Clean up a specific temporary directory.

    Args:
        temp_dir: Path to the temporary directory

    Returns:
        True if cleanup was successful
    """
    return _get_global_temp_manager().cleanup_temp_directory(temp_dir)


def cleanup_temp_file(temp_file: Union[str, Path]) -> bool:
    """Clean up a specific temporary file.

    Args:
        temp_file: Path to the temporary file

    Returns:
        True if cleanup was successful
    """
    return _get_global_temp_manager().cleanup_temp_file(temp_file)


def force_cleanup_all() -> None:
    """Force immediate cleanup of all temporary resources."""
    _get_global_temp_manager().force_cleanup_all()


def get_tracked_resources() -> tuple[set[Path], set[Path]]:
    """Get currently tracked temporary resources.

    Returns:
        Tuple of (temp_directories, temp_files)
    """
    return _get_global_temp_manager().get_tracked_resources()
