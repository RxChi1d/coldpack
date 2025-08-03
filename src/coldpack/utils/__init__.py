"""Utility modules for coldpack operations."""

from .filesystem import (
    check_disk_space,
    cleanup_temp_directory,
    create_temp_directory,
    safe_file_operations,
    validate_paths,
)
from .hashing import DualHasher, HashVerifier
from .par2 import PAR2Manager
from .progress import ProgressTracker, create_progress_callback
from .temp_manager import (
    GlobalTempManager,
    WindowsTempCleanupError,
    force_cleanup_all,
    get_tracked_resources,
)
from .windows_compat import (
    check_par2_related_paths_compatibility,
    check_windows_par2_unicode_compatibility,
)

__all__ = [
    "create_temp_directory",
    "cleanup_temp_directory",
    "check_disk_space",
    "validate_paths",
    "safe_file_operations",
    "GlobalTempManager",
    "WindowsTempCleanupError",
    "force_cleanup_all",
    "get_tracked_resources",
    "DualHasher",
    "HashVerifier",
    "PAR2Manager",
    "ProgressTracker",
    "create_progress_callback",
    "check_par2_related_paths_compatibility",
    "check_windows_par2_unicode_compatibility",
]
