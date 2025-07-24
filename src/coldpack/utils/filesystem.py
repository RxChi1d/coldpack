"""Filesystem utilities for safe file operations and temporary directory management."""

import os
import platform
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
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {path}") from e
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


# System-specific file patterns to exclude from archives
SYSTEM_FILE_PATTERNS = {
    "macos": [
        "._*",  # macOS resource forks
        ".DS_Store",  # macOS desktop services store
        ".fseventsd",  # macOS file system events daemon
        ".Spotlight-*",  # macOS spotlight indexing
        ".Trashes",  # macOS trash
        ".DocumentRevisions-V100",  # macOS document revisions
        ".TemporaryItems",  # macOS temporary items
        "__MACOSX",  # macOS archive metadata directory
        ".AppleDouble",  # macOS AppleDouble files
        ".LSOverride",  # macOS launch services override
        ".Spotlight-V100",  # macOS spotlight
        ".VolumeIcon.icns",  # macOS volume icon
    ],
    "windows": [
        "Thumbs.db",  # Windows thumbnail cache
        "Desktop.ini",  # Windows desktop configuration
        "*.tmp",  # Windows temporary files
        "*.lnk",  # Windows shortcuts (typically shouldn't be archived)
        "$RECYCLE.BIN",  # Windows recycle bin
        "System Volume Information",  # Windows system volume info
        "hiberfil.sys",  # Windows hibernate file
        "pagefile.sys",  # Windows page file
        "swapfile.sys",  # Windows swap file
        "*.cab",  # Windows cabinet files (system)
        "*.msi",  # Windows installer packages
        "*.exe",  # Windows executables (when found in system contexts)
    ],
    "linux": [
        ".Trash-*",  # Linux trash directories
        ".cache",  # Linux cache directory
        ".thumbnails",  # Linux thumbnail cache
        ".gvfs",  # Linux GNOME virtual file system
        "lost+found",  # Linux filesystem recovery directory
        ".xsession-errors",  # Linux X session errors
        "*.tmp",  # Linux temporary files
        "*~",  # Linux backup files
        ".nfs*",  # NFS temporary files
    ],
    "common": [
        ".git",  # Git repository data
        ".svn",  # Subversion repository data
        ".hg",  # Mercurial repository data
        ".bzr",  # Bazaar repository data
        "node_modules",  # Node.js modules (should be excluded from most archives)
        "__pycache__",  # Python bytecode cache
        "*.pyc",  # Python bytecode files
        "*.pyo",  # Python optimized bytecode
        ".pytest_cache",  # Pytest cache
        ".coverage",  # Coverage.py files
        ".tox",  # Tox testing tool
        ".venv",  # Python virtual environment
        "venv",  # Python virtual environment
        ".env",  # Environment files (may contain secrets)
        "*.log",  # Log files
        "*.lock",  # Lock files
        ".idea",  # JetBrains IDE
        ".vscode",  # Visual Studio Code
        ".vs",  # Visual Studio
        ".gradle",  # Gradle build cache
        ".m2",  # Maven cache
        "target",  # Maven/Gradle build output
        "build",  # Generic build directory
        "dist",  # Distribution directory
        "*.orig",  # Original files from merges
        "*.rej",  # Rejected patches
        ".sass-cache",  # Sass compilation cache
        ".npm",  # NPM cache
        "Cargo.lock",  # Rust lock file (context dependent)
        "package-lock.json",  # NPM lock file (context dependent)
        "yarn.lock",  # Yarn lock file (context dependent)
    ],
}


def should_exclude_file(file_path: Path, base_dir: Path) -> bool:
    """Determine if a file should be excluded from archiving.

    This function checks against system-specific file patterns that are
    typically unwanted in clean archives, including:
    - macOS system files (._*, .DS_Store, etc.)
    - Windows system files (Thumbs.db, Desktop.ini, etc.)
    - Linux system files (.Trash-*, .cache, etc.)
    - Common development artifacts (node_modules, __pycache__, etc.)

    Args:
        file_path: Path to the file to check
        base_dir: Base directory being archived (for relative path calculation)

    Returns:
        True if the file should be excluded from the archive
    """
    import fnmatch

    # Get relative path from base directory
    try:
        rel_path = file_path.relative_to(base_dir)
    except ValueError:
        # File is not under base_dir, probably shouldn't be archived anyway
        return True

    # Get file/directory name
    name = file_path.name
    rel_path_str = str(rel_path)

    # Always check all system patterns for maximum compatibility
    # Users may transfer files between different operating systems
    patterns_to_check = SYSTEM_FILE_PATTERNS["common"].copy()
    patterns_to_check.extend(SYSTEM_FILE_PATTERNS["macos"])
    patterns_to_check.extend(SYSTEM_FILE_PATTERNS["windows"])
    patterns_to_check.extend(SYSTEM_FILE_PATTERNS["linux"])

    # Check patterns against both filename and relative path
    for pattern in patterns_to_check:
        # Check exact name match
        if fnmatch.fnmatch(name, pattern):
            logger.debug(
                f"Excluding file (name pattern): {rel_path} (matched: {pattern})"
            )
            return True

        # Check relative path match (for directory patterns)
        if fnmatch.fnmatch(rel_path_str, pattern):
            logger.debug(
                f"Excluding file (path pattern): {rel_path} (matched: {pattern})"
            )
            return True

        # Check if any parent directory matches the pattern
        for parent in rel_path.parents:
            if fnmatch.fnmatch(parent.name, pattern):
                logger.debug(
                    f"Excluding file (parent pattern): {rel_path} (parent {parent.name} matched: {pattern})"
                )
                return True

    return False


def filter_files_for_archive(source_dir: Path) -> list[Path]:
    """Get a filtered list of files suitable for archiving.

    This function recursively finds all files in the source directory
    and excludes system files, build artifacts, and other files that
    typically shouldn't be included in clean archives.

    Args:
        source_dir: Directory to scan for files

    Returns:
        Sorted list of Path objects for files that should be archived
    """
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(
            f"Source directory does not exist or is not a directory: {source_dir}"
        )

    included_files = []
    excluded_count = 0

    for file_path in source_dir.rglob("*"):
        if not file_path.is_file():
            continue

        if should_exclude_file(file_path, source_dir):
            excluded_count += 1
            continue

        included_files.append(file_path)

    # Sort files for deterministic output
    included_files.sort()

    logger.info(
        f"File filtering complete: {len(included_files)} included, {excluded_count} excluded"
    )

    return included_files


# Windows filename handling utilities
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

WINDOWS_INVALID_CHARS = {"<", ">", ":", '"', "|", "?", "*"}
WINDOWS_INVALID_CONTROL_CHARS = {
    chr(i) for i in range(0, 32)
}  # Control characters 0-31
WINDOWS_INVALID_PATH_CHARS = WINDOWS_INVALID_CHARS | WINDOWS_INVALID_CONTROL_CHARS


def sanitize_windows_filename(filename: str, replacement_char: str = "_") -> str:
    """Sanitize a filename for Windows compatibility.

    This function handles Windows-specific filename restrictions:
    - Reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    - Invalid characters (< > : " | ? * and control chars 0-31)
    - Trailing dots and spaces
    - Maximum length restrictions

    Args:
        filename: Original filename to sanitize
        replacement_char: Character to use for replacing invalid characters

    Returns:
        Sanitized filename safe for Windows
    """
    if not filename:
        return "unnamed_file"

    # Remove path separators (shouldn't be in filename anyway)
    filename = filename.replace("/", replacement_char).replace("\\", replacement_char)

    # Split filename into name and extension
    if "." in filename:
        name_part, ext_part = filename.rsplit(".", 1)
        # Keep the dot for extension
        ext_part = "." + ext_part
    else:
        name_part = filename
        ext_part = ""

    # Replace invalid characters in name part
    sanitized_name = ""
    for char in name_part:
        if char in WINDOWS_INVALID_PATH_CHARS:
            sanitized_name += replacement_char
        else:
            sanitized_name += char

    # Replace invalid characters in extension part
    sanitized_ext = ""
    for char in ext_part:
        if char in WINDOWS_INVALID_PATH_CHARS:
            sanitized_ext += replacement_char
        else:
            sanitized_ext += char

    # Remove trailing dots and spaces from name part
    sanitized_name = sanitized_name.rstrip(". ")

    # Handle empty name after sanitization
    if not sanitized_name:
        sanitized_name = "unnamed_file"

    # Check for reserved names (case insensitive)
    name_upper = sanitized_name.upper()
    if name_upper in WINDOWS_RESERVED_NAMES:
        sanitized_name = f"{sanitized_name}_{replacement_char}file"

    # Combine name and extension
    result = sanitized_name + sanitized_ext

    # Windows has a 255 character limit for filenames
    if len(result) > 255:
        # Try to preserve extension if possible
        if len(sanitized_ext) < 200:  # Leave some room for name
            max_name_length = 255 - len(sanitized_ext)
            result = sanitized_name[:max_name_length] + sanitized_ext
        else:
            result = result[:255]

    return result


def check_windows_filename_conflicts(file_list: list[str]) -> dict[str, list[str]]:
    """Check for potential Windows filename conflicts in a list of files.

    This function identifies files that would cause problems on Windows:
    - Reserved names
    - Invalid characters
    - Case sensitivity conflicts (since Windows is case-insensitive)

    Args:
        file_list: List of file paths to check

    Returns:
        Dictionary mapping conflict types to lists of problematic files
    """
    conflicts: dict[str, list[str]] = {
        "reserved_names": [],
        "invalid_chars": [],
        "case_conflicts": [],
        "length_conflicts": [],
    }

    # Track case-insensitive names for conflict detection
    case_insensitive_map: dict[str, str] = {}

    for file_path in file_list:
        # Get just the filename part
        filename = Path(file_path).name

        # Check for reserved names
        name_part = filename.split(".")[0].upper()
        if name_part in WINDOWS_RESERVED_NAMES:
            conflicts["reserved_names"].append(file_path)

        # Check for invalid characters
        if any(char in WINDOWS_INVALID_PATH_CHARS for char in filename):
            conflicts["invalid_chars"].append(file_path)

        # Check for length conflicts
        if len(filename) > 255:
            conflicts["length_conflicts"].append(file_path)

        # Check for case sensitivity conflicts
        filename_lower = filename.lower()
        if filename_lower in case_insensitive_map:
            # This is a case conflict
            if file_path not in conflicts["case_conflicts"]:
                conflicts["case_conflicts"].append(file_path)
            if case_insensitive_map[filename_lower] not in conflicts["case_conflicts"]:
                conflicts["case_conflicts"].append(case_insensitive_map[filename_lower])
        else:
            case_insensitive_map[filename_lower] = file_path

    return conflicts


def create_filename_mapping(file_list: list[str]) -> dict[str, str]:
    """Create a mapping from original filenames to Windows-safe filenames.

    This function generates unique, Windows-compatible filenames for all files
    in the list, handling conflicts by adding numerical suffixes.

    Args:
        file_list: List of original file paths

    Returns:
        Dictionary mapping original paths to sanitized paths
    """
    mapping = {}
    used_names = set()

    for original_path in file_list:
        path_obj = Path(original_path)
        parent = path_obj.parent
        original_filename = path_obj.name

        # Sanitize the filename
        sanitized_filename = sanitize_windows_filename(original_filename)

        # Handle duplicates by adding numerical suffix
        if sanitized_filename.lower() in used_names:
            name_part, ext_part = (
                sanitized_filename.rsplit(".", 1)
                if "." in sanitized_filename
                else (sanitized_filename, "")
            )

            counter = 1
            while True:
                if ext_part:
                    candidate = f"{name_part}_{counter}.{ext_part}"
                else:
                    candidate = f"{name_part}_{counter}"

                if candidate.lower() not in used_names:
                    sanitized_filename = candidate
                    break
                counter += 1

        used_names.add(sanitized_filename.lower())

        # Create the new path
        if parent == Path("."):
            new_path = sanitized_filename
        else:
            new_path = str(parent / sanitized_filename)

        mapping[original_path] = new_path

    return mapping


def is_windows_system() -> bool:
    """Check if the current system is Windows.

    Returns:
        True if running on Windows
    """
    return platform.system().lower() == "windows"


def needs_windows_filename_handling(file_list: list[str]) -> bool:
    """Determine if Windows filename handling is needed.

    Since py7zz uses 7-Zip which handles most filename issues natively,
    we only need special handling for severe conflicts that 7-Zip cannot resolve.

    Args:
        file_list: List of file paths to check

    Returns:
        True if any files have severe Windows compatibility issues
    """
    if not is_windows_system():
        return False

    conflicts = check_windows_filename_conflicts(file_list)

    # Only trigger special handling for reserved names and invalid characters
    # Let 7-Zip handle case conflicts naturally (it's designed for this)
    severe_conflicts = (
        conflicts["reserved_names"]
        or conflicts["invalid_chars"]
        or conflicts["length_conflicts"]
    )

    return bool(severe_conflicts)
