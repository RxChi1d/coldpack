"""Filesystem utilities for safe file operations and temporary directory management."""

import os
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, Union

from loguru import logger

from ..config.constants import MIN_DISK_SPACE_GB, TEMP_DIR_PREFIX


class FilesystemError(Exception):
    """Base exception for filesystem operations."""

    pass


class InsufficientSpaceError(FilesystemError):
    """Raised when there is insufficient disk space."""

    pass


class PermissionError(FilesystemError):
    """Raised when file permissions are insufficient."""

    pass


def check_disk_space(
    path: Union[str, Path], required_gb: float = MIN_DISK_SPACE_GB
) -> bool:
    """Check if there is sufficient disk space available.

    Args:
        path: Path to check disk space for
        required_gb: Required space in GB

    Returns:
        True if sufficient space is available

    Raises:
        InsufficientSpaceError: If there is not enough space
    """
    try:
        stat = shutil.disk_usage(path)
        available_gb = stat.free / (1024**3)

        if available_gb < required_gb:
            raise InsufficientSpaceError(
                f"Insufficient disk space: {available_gb:.2f}GB available, "
                f"{required_gb:.2f}GB required"
            )

        logger.debug(f"Disk space check passed: {available_gb:.2f}GB available")
        return True

    except OSError as e:
        logger.error(f"Failed to check disk space for {path}: {e}")
        raise FilesystemError(f"Cannot check disk space: {e}") from e


def validate_paths(*paths: Union[str, Path]) -> bool:
    """Validate that all paths are safe and accessible.

    Args:
        *paths: Paths to validate

    Returns:
        True if all paths are valid

    Raises:
        PermissionError: If paths are not accessible
        FileNotFoundError: If required paths don't exist
    """
    for path in paths:
        path_obj = Path(path)

        # Check if parent directory exists and is writable for output paths
        if not path_obj.exists():
            parent = path_obj.parent
            if not parent.exists():
                raise FileNotFoundError(f"Parent directory does not exist: {parent}")
            if not os.access(parent, os.W_OK):
                raise PermissionError(f"No write permission for directory: {parent}")

        # Check read permission for existing files
        elif path_obj.is_file() and not os.access(path_obj, os.R_OK):
            raise PermissionError(f"No read permission for file: {path_obj}")

        # Check write permission for existing directories
        elif path_obj.is_dir() and not os.access(path_obj, os.W_OK):
            raise PermissionError(f"No write permission for directory: {path_obj}")

    return True


def create_temp_directory(suffix: str = "", prefix: str = TEMP_DIR_PREFIX) -> Path:
    """Create a secure temporary directory.

    Args:
        suffix: Suffix for the directory name
        prefix: Prefix for the directory name

    Returns:
        Path to the created temporary directory

    Raises:
        FilesystemError: If directory creation fails
    """
    try:
        temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix)
        temp_path = Path(temp_dir)

        # Ensure proper permissions (owner read/write/execute only)
        os.chmod(temp_path, 0o700)

        logger.debug(f"Created temporary directory: {temp_path}")
        return temp_path

    except OSError as e:
        logger.error(f"Failed to create temporary directory: {e}")
        raise FilesystemError(f"Cannot create temporary directory: {e}") from e


def cleanup_temp_directory(temp_dir: Union[str, Path], force: bool = False) -> bool:
    """Clean up a temporary directory and all its contents.

    Args:
        temp_dir: Path to the temporary directory
        force: If True, ignore errors and force removal

    Returns:
        True if cleanup was successful

    Raises:
        FilesystemError: If cleanup fails and force is False
    """
    temp_path = Path(temp_dir)

    if not temp_path.exists():
        logger.debug(f"Temporary directory already removed: {temp_path}")
        return True

    try:
        shutil.rmtree(temp_path)
        logger.debug(f"Successfully cleaned up temporary directory: {temp_path}")
        return True

    except OSError as e:
        error_msg = f"Failed to clean up temporary directory {temp_path}: {e}"

        if force:
            logger.warning(error_msg)
            return False
        else:
            logger.error(error_msg)
            raise FilesystemError(error_msg) from e


@contextmanager
def safe_temp_directory(
    suffix: str = "", prefix: str = TEMP_DIR_PREFIX
) -> Generator[Path, None, None]:
    """Context manager for safe temporary directory operations.

    Args:
        suffix: Suffix for the directory name
        prefix: Prefix for the directory name

    Yields:
        Path to the temporary directory

    Example:
        with safe_temp_directory() as temp_dir:
            # Use temp_dir safely
            pass
        # temp_dir is automatically cleaned up
    """
    temp_dir = None
    try:
        temp_dir = create_temp_directory(suffix=suffix, prefix=prefix)
        yield temp_dir
    finally:
        if temp_dir:
            cleanup_temp_directory(temp_dir, force=True)


class safe_file_operations:
    """Context manager for safe file operations with automatic cleanup on error."""

    def __init__(self, cleanup_on_error: bool = True):
        """Initialize safe file operations context.

        Args:
            cleanup_on_error: Whether to clean up created files on error
        """
        self.cleanup_on_error = cleanup_on_error
        self.created_files: list[Path] = []
        self.created_dirs: list[Path] = []

    def __enter__(self) -> "safe_file_operations":
        """Enter the context manager."""
        return self

    def __exit__(
        self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Any
    ) -> None:
        """Exit the context manager and clean up on error."""
        if exc_type is not None and self.cleanup_on_error:
            self._cleanup_created_files()

    def track_file(self, file_path: Union[str, Path]) -> None:
        """Track a file for potential cleanup.

        Args:
            file_path: Path to the file to track
        """
        self.created_files.append(Path(file_path))

    def track_directory(self, dir_path: Union[str, Path]) -> None:
        """Track a directory for potential cleanup.

        Args:
            dir_path: Path to the directory to track
        """
        self.created_dirs.append(Path(dir_path))

    def _cleanup_created_files(self) -> None:
        """Clean up all tracked files and directories."""
        # Clean up files first
        for file_path in self.created_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.debug(f"Cleaned up file: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up file {file_path}: {e}")

        # Clean up directories (in reverse order)
        for dir_path in reversed(self.created_dirs):
            try:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                    logger.debug(f"Cleaned up directory: {dir_path}")
            except OSError as e:
                logger.warning(f"Failed to clean up directory {dir_path}: {e}")


def ensure_parent_directory(file_path: Union[str, Path]) -> None:
    """Ensure parent directory exists for a file path.

    Args:
        file_path: Path to the file

    Raises:
        FilesystemError: If directory creation fails
    """
    parent_dir = Path(file_path).parent

    try:
        parent_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured parent directory exists: {parent_dir}")
    except OSError as e:
        logger.error(f"Failed to create parent directory {parent_dir}: {e}")
        raise FilesystemError(f"Cannot create parent directory: {e}") from e


def get_file_size(file_path: Union[str, Path]) -> int:
    """Get file size in bytes.

    Args:
        file_path: Path to the file

    Returns:
        File size in bytes

    Raises:
        FileNotFoundError: If file doesn't exist
        FilesystemError: If size cannot be determined
    """
    path = Path(file_path)

    try:
        return path.stat().st_size
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {path}")
    except OSError as e:
        raise FilesystemError(f"Cannot get file size for {path}: {e}") from e


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.2f} GB"
    elif size_bytes >= 1024**2:
        return f"{size_bytes / (1024**2):.2f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes} bytes"
