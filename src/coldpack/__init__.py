"""coldpack - Cross-platform cold storage CLI package.

This package provides a standardized solution for creating tar.zst cold storage
archives with comprehensive verification and repair mechanisms.
"""

from importlib.metadata import PackageNotFoundError

# Dynamic version detection using hatch-vcs
from importlib.metadata import version as _get_version

from .config.settings import ArchiveMetadata, CompressionSettings
from .core.archiver import ColdStorageArchiver
from .core.extractor import MultiFormatExtractor
from .core.repairer import ArchiveRepairer
from .core.verifier import ArchiveVerifier

try:
    __version__ = _get_version("coldpack")
except PackageNotFoundError:  # pragma: no cover
    # Fallback for development/edge cases when the package metadata isn't available
    __version__ = "0.0.0+unknown"
__author__ = "coldpack contributors"
__license__ = "MIT"

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
