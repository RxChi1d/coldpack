"""Configuration module for coldpack."""

from .constants import (
    DEFAULT_COMPRESSION_LEVEL,
    DEFAULT_PAR2_REDUNDANCY,
    SUPPORTED_INPUT_FORMATS,
    TEMP_DIR_PREFIX,
)
from .settings import ArchiveMetadata, CompressionSettings

__all__ = [
    "CompressionSettings",
    "ArchiveMetadata",
    "DEFAULT_COMPRESSION_LEVEL",
    "DEFAULT_PAR2_REDUNDANCY",
    "SUPPORTED_INPUT_FORMATS",
    "TEMP_DIR_PREFIX",
]
