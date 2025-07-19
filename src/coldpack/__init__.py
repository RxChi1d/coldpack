"""coldpack - Cross-platform cold storage CLI package.

This package provides a standardized solution for creating tar.zst cold storage
archives with comprehensive verification and repair mechanisms.
"""

from .config.settings import ArchiveMetadata, CompressionSettings
from .core.archiver import ColdStorageArchiver
from .core.extractor import MultiFormatExtractor
from .core.repairer import ArchiveRepairer
from .core.verifier import ArchiveVerifier

__version__ = "0.1.0"
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
