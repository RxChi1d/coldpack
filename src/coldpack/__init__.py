"""coldpack - Cross-platform cold storage CLI package.

This package provides a standardized solution for creating tar.zst cold storage
archives with comprehensive verification and repair mechanisms.
"""

from .config.settings import ArchiveMetadata, CompressionSettings
from .core.archiver import ColdStorageArchiver
from .core.extractor import MultiFormatExtractor
from .core.repairer import ArchiveRepairer
from .core.verifier import ArchiveVerifier

# Dynamic version detection using hatch-vcs
try:
    # Standard way for installed packages (Python 3.8+)
    from importlib.metadata import version as _get_version

    __version__ = _get_version("coldpack")
except ImportError:
    # Fallback for older Python versions or missing package
    try:
        from importlib_metadata import version as _get_version

        __version__ = _get_version("coldpack")
    except (ImportError, Exception):
        # Final fallback for development/edge cases
        __version__ = "0.0.0+unknown"
__author__ = "coldpack contributors"
__license__ = "BSD-3-Clause"

# Main API exports
__all__ = [
    "ColdStorageArchiver",
    "MultiFormatExtractor",
    "ArchiveVerifier",
    "ArchiveRepairer",
    "CompressionSettings",
    "ArchiveMetadata",
    "__version__",
]


# Package metadata
def get_version() -> str:
    """Get the current coldpack version."""
    return __version__


def get_package_info() -> dict[str, str]:
    """Get comprehensive package information."""
    return {
        "name": "coldpack",
        "version": __version__,
        "author": __author__,
        "license": __license__,
        "description": "Cross-platform cold storage CLI package",
        "supported_formats": "7z, zip, tar.gz, rar, tar.zst",
        "verification_layers": "tar header, zstd, SHA-256, BLAKE3, PAR2",
    }
