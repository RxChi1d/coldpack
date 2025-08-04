"""Pydantic settings models for coldpack configuration."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import toml
from pydantic import BaseModel, Field, field_validator

# Import version detection
try:
    from importlib.metadata import version as _get_version

    _coldpack_version = _get_version("coldpack")
except Exception:
    # Fallback for edge cases
    _coldpack_version = "0.0.0+unknown"

# Handle tomllib compatibility (Python 3.11+ has tomllib built-in)
if sys.version_info >= (3, 11):
    import tomllib

    HAS_TOMLLIB = True
else:
    # For Python < 3.11, try to use tomli
    HAS_TOMLLIB = False
    try:
        import tomli as tomllib

        HAS_TOMLLIB = True
    except ImportError:
        # tomli not available, will fall back to using TOML parsing via other means
        pass


class PAR2Settings(BaseModel):
    """Configuration for PAR2 recovery files."""

    redundancy_percent: int = Field(
        default=10, ge=1, le=50, description="PAR2 redundancy percentage"
    )
    block_count: int = Field(
        default=2000, ge=100, le=32768, description="Number of PAR2 blocks"
    )

    def to_par2_params(self) -> list[str]:
        """Convert settings to PAR2 command line parameters."""
        return [
            f"-r{self.redundancy_percent}",
            f"-n{self.block_count}",
            "-q",  # Quiet mode
        ]


class SevenZipSettings(BaseModel):
    """Configuration for 7z compression operations using py7zz."""

    level: int = Field(default=5, ge=1, le=9, description="Compression level (1-9)")
    dictionary_size: str = Field(
        default="16m",
        description="Dictionary size (128k, 1m, 4m, 16m, 64m, 256m, 512m)",
    )
    threads: Union[int, bool] = Field(
        default=True,
        description="Number of threads (True=all cores, False=single-thread, int=specific count)",
    )
    solid: bool = Field(default=True, description="Enable solid compression")
    method: str = Field(default="LZMA2", description="Compression method")
    manual_settings: bool = Field(
        default=False,
        description="Whether settings are manually specified (disables dynamic optimization)",
    )

    @field_validator("dictionary_size")
    @classmethod
    def validate_dictionary_size(cls, v: str) -> str:
        """Validate dictionary size format."""
        valid_sizes = {"128k", "1m", "4m", "16m", "64m", "256m", "512m"}
        if v.lower() not in valid_sizes:
            raise ValueError(f"Dictionary size must be one of: {valid_sizes}")
        return v.lower()

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate compression method."""
        valid_methods = {"LZMA2", "LZMA", "PPMd", "BZip2"}
        if v not in valid_methods:
            raise ValueError(f"Compression method must be one of: {valid_methods}")
        return v

    @field_validator("threads")
    @classmethod
    def validate_threads(cls, v: Union[int, bool]) -> Union[int, bool]:
        """Validate threads parameter."""
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            if v == 0:
                raise ValueError(
                    "threads=0 is not supported, use threads=True for all cores or threads=False for single-thread"
                )
            if v < 0:
                raise ValueError(
                    "threads must be positive integer, True (all cores), or False (single-thread)"
                )
            return v
        raise ValueError(
            "threads must be int, bool True (all cores), or bool False (single-thread)"
        )

    def to_py7zz_config(self) -> dict[str, Any]:
        """Convert settings to py7zz Config compatible dictionary."""
        return {
            "level": self.level,
            "compression": self.method.lower(),  # py7zz uses lowercase compression names
            "dictionary_size": self.dictionary_size,
            "solid": self.solid,
            "threads": self.threads,
        }


class ArchiveMetadata(BaseModel):
    """Comprehensive metadata for archive operations with complete persistence support."""

    # Core identification
    source_path: Path
    archive_path: Path
    archive_name: str = Field(description="Name of the archive (without extension)")

    # Version and creation info
    coldpack_version: str = Field(
        default_factory=lambda: _coldpack_version, description="coldpack version used"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    created_at_iso: str = Field(default="", description="ISO formatted creation time")

    # Archive format
    archive_format: str = Field(default="7z", description="Archive format (7z only)")

    # Processing settings (7z format only)
    sevenzip_settings: Optional[SevenZipSettings] = Field(
        default=None, description="7z compression settings"
    )
    par2_settings: PAR2Settings = Field(default_factory=PAR2Settings)

    @field_validator("archive_format")
    @classmethod
    def validate_archive_format(cls, v: str) -> str:
        """Validate archive format."""
        from .constants import SUPPORTED_OUTPUT_FORMATS

        if v not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(
                f"Archive format must be one of: {SUPPORTED_OUTPUT_FORMATS}"
            )
        return v

    # Content statistics
    file_count: int = Field(default=0, ge=0, description="Total number of files")
    directory_count: int = Field(
        default=0, ge=0, description="Total number of directories"
    )
    original_size: int = Field(
        default=0, ge=0, description="Original uncompressed size in bytes"
    )
    compressed_size: int = Field(
        default=0, ge=0, description="Compressed archive size in bytes"
    )
    compression_ratio: float = Field(
        default=0.0, ge=0.0, description="Compression ratio (compressed/original)"
    )

    # Integrity verification
    verification_hashes: dict[str, str] = Field(
        default_factory=dict, description="Hash values (sha256, blake3)"
    )
    hash_files: dict[str, str] = Field(
        default_factory=dict, description="Generated hash files (algo: filename)"
    )
    par2_files: list[str] = Field(
        default_factory=list, description="Generated PAR2 recovery files"
    )

    # Archive structure info
    has_single_root: bool = Field(
        default=False, description="Whether archive has single root directory"
    )
    root_directory: Optional[str] = Field(
        default=None, description="Root directory name if has_single_root"
    )

    # Processing details
    processing_time_seconds: float = Field(
        default=0.0, ge=0.0, description="Total processing time"
    )
    temp_directory_used: Optional[str] = Field(
        default=None, description="Temporary directory used during creation"
    )

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization processing."""
        # Ensure ISO timestamp is set
        if not self.created_at_iso:
            self.created_at_iso = self.created_at.isoformat()

        # Calculate compression ratio if sizes are available
        self.calculate_compression_ratio()

        # Ensure 7z settings are set
        if self.sevenzip_settings is None:
            self.sevenzip_settings = SevenZipSettings()

    @property
    def compression_percentage(self) -> float:
        """Get compression percentage (100% - compression_ratio * 100)."""
        return (1.0 - self.compression_ratio) * 100.0

    @property
    def total_entries(self) -> int:
        """Get total number of entries (files + directories)."""
        return self.file_count + self.directory_count

    def calculate_compression_ratio(self) -> None:
        """Calculate compression ratio from original and compressed sizes."""
        if self.original_size > 0:
            self.compression_ratio = self.compressed_size / self.original_size
        else:
            self.compression_ratio = 0.0

    def to_toml_dict(self) -> dict[str, Any]:
        """Convert metadata to TOML-compatible dictionary with proper structure."""
        return {
            "metadata": {
                "coldpack_version": self.coldpack_version,
                "created_at": self.created_at_iso,
                "archive_name": self.archive_name,
                "source_path": str(self.source_path),
                "archive_path": str(self.archive_path),
            },
            "content": {
                "file_count": self.file_count,
                "directory_count": self.directory_count,
                "total_entries": self.total_entries,
                "original_size": self.original_size,
                "compressed_size": self.compressed_size,
                "compression_ratio": round(self.compression_ratio, 4),
                "compression_percentage": round(self.compression_percentage, 2),
                "has_single_root": self.has_single_root,
                "root_directory": self.root_directory,
            },
            "archive": {
                "format": self.archive_format,
            },
            "sevenzip": self._get_sevenzip_dict(),
            "par2": {
                "redundancy_percent": self.par2_settings.redundancy_percent,
                "block_count": self.par2_settings.block_count,
                "files": self.par2_files,
            },
            "integrity": {
                "hashes": self.verification_hashes,
                "hash_files": self.hash_files,
            },
            "processing": {
                "time_seconds": self.processing_time_seconds,
                "temp_directory": self.temp_directory_used,
            },
        }

    def _get_sevenzip_dict(self) -> dict[str, Any]:
        """Get sevenzip settings dictionary for TOML serialization."""
        if self.sevenzip_settings is not None:
            # Convert threads to serializable format
            threads_value = self.sevenzip_settings.threads
            threads_serialized: Union[str, int]
            if threads_value is True:
                threads_serialized = "all"
            elif threads_value is False:
                threads_serialized = "single"
            else:
                threads_serialized = threads_value

            return {
                "level": self.sevenzip_settings.level,
                "dictionary_size": self.sevenzip_settings.dictionary_size,
                "threads": threads_serialized,
                "solid": self.sevenzip_settings.solid,
                "method": self.sevenzip_settings.method,
            }
        return {}

    def save_to_toml(self, file_path: Path) -> None:
        """Save metadata to TOML file."""
        toml_data = self.to_toml_dict()

        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write TOML file
        with open(file_path, "w", encoding="utf-8") as f:
            toml.dump(toml_data, f)

    @classmethod
    def load_from_toml(cls, file_path: Path) -> "ArchiveMetadata":
        """Load metadata from TOML file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {file_path}")

        # Read TOML file with compatibility handling
        if HAS_TOMLLIB:
            # Use tomllib (Python 3.11+) or tomli
            with open(file_path, "rb") as f:
                toml_data = tomllib.load(f)
        else:
            # Fallback to toml library
            import toml

            with open(file_path, encoding="utf-8") as f:
                toml_data = toml.load(f)

        # Extract sections
        metadata_section = toml_data.get("metadata", {})
        content_section = toml_data.get("content", {})
        archive_section = toml_data.get("archive", {})
        sevenzip_section = toml_data.get("sevenzip", {})
        par2_section = toml_data.get("par2", {})
        integrity_section = toml_data.get("integrity", {})
        processing_section = toml_data.get("processing", {})

        # Get archive format
        archive_format = archive_section.get("format", "7z")

        # Reconstruct 7z settings
        sevenzip_settings = None
        if sevenzip_section:
            # Convert threads from serialized format
            threads_data = sevenzip_section.get("threads", True)
            if threads_data == "all":
                threads_value = True
            elif threads_data == "single":
                threads_value = False
            else:
                threads_value = threads_data

            sevenzip_data = dict(sevenzip_section)
            sevenzip_data["threads"] = threads_value
            sevenzip_settings = SevenZipSettings(**sevenzip_data)

        par2_settings = PAR2Settings(
            redundancy_percent=par2_section.get("redundancy_percent", 10),
            block_count=par2_section.get("block_count", 2000),
        )

        # Create metadata object
        return cls(
            # Core identification
            source_path=Path(metadata_section.get("source_path", "")),
            archive_path=Path(metadata_section.get("archive_path", "")),
            archive_name=metadata_section.get("archive_name", ""),
            # Version and creation
            coldpack_version=metadata_section.get("coldpack_version", "unknown"),
            created_at=datetime.fromisoformat(
                metadata_section.get("created_at", datetime.now().isoformat())
            ),
            created_at_iso=metadata_section.get("created_at", ""),
            # Archive format
            archive_format=archive_format,
            # Settings
            sevenzip_settings=sevenzip_settings,
            par2_settings=par2_settings,
            # Content statistics
            file_count=content_section.get("file_count", 0),
            directory_count=content_section.get("directory_count", 0),
            original_size=content_section.get("original_size", 0),
            compressed_size=content_section.get("compressed_size", 0),
            compression_ratio=content_section.get("compression_ratio", 0.0),
            # Archive structure
            has_single_root=content_section.get("has_single_root", False),
            root_directory=content_section.get("root_directory"),
            # Integrity
            verification_hashes=integrity_section.get("hashes", {}),
            hash_files=integrity_section.get("hash_files", {}),
            par2_files=par2_section.get("files", []),
            # Processing
            processing_time_seconds=processing_section.get("time_seconds", 0.0),
            temp_directory_used=processing_section.get("temp_directory"),
        )


class ProcessingOptions(BaseModel):
    """Options for archive processing operations."""

    verify_integrity: bool = Field(
        default=True, description="Enable integrity verification (overall control)"
    )
    # Individual verification layer controls
    verify_sha256: bool = Field(
        default=True, description="Enable SHA-256 hash verification"
    )
    verify_blake3: bool = Field(
        default=True, description="Enable BLAKE3 hash verification"
    )
    verify_par2: bool = Field(
        default=True, description="Enable PAR2 recovery verification"
    )
    generate_par2: bool = Field(
        default=True, description="Generate PAR2 recovery files"
    )
    par2_redundancy: int = Field(
        default=10, ge=1, le=50, description="PAR2 redundancy percentage"
    )
    cleanup_on_error: bool = Field(default=True, description="Clean up files on error")
    verbose: bool = Field(default=False, description="Enable verbose output")
    force_overwrite: bool = Field(
        default=False, description="Force overwrite existing files"
    )
    progress_callback: Optional[object] = Field(
        default=None, description="Progress callback function"
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
