"""Pydantic settings models for coldpack configuration."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import toml
from pydantic import BaseModel, Field, field_validator

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
        pass


class CompressionSettings(BaseModel):
    """Compression configuration for zstd operations."""

    level: int = Field(default=19, ge=1, le=22, description="Compression level")
    threads: int = Field(default=0, ge=0, description="Number of threads (0=auto)")
    long_mode: bool = Field(default=True, description="Enable long-distance matching")
    long_distance: Optional[int] = Field(
        default=None,
        ge=10,
        le=31,
        description="Long-distance matching value (overrides long_mode)",
    )
    ultra_mode: bool = Field(
        default=False, description="Enable ultra mode (levels 20-22)"
    )

    @field_validator("ultra_mode")
    @classmethod
    def validate_ultra_mode(cls, v: bool, info: Any) -> bool:
        """Validate ultra mode based on compression level."""
        level = info.data.get("level", 19)
        if v and level < 20:
            raise ValueError("Ultra mode requires compression level >= 20")
        return v

    def to_zstd_params(self) -> list[str]:
        """Convert settings to zstd command line parameters."""
        params = [f"-{self.level}"]

        if self.ultra_mode:
            params.append("--ultra")

        if self.threads > 0:
            params.append(f"-T{self.threads}")
        else:
            params.append("-T0")

        if self.long_distance is not None:
            # Manual long distance value overrides long_mode
            params.append(f"--long={self.long_distance}")
        elif self.long_mode:
            params.append("--long=31")

        params.extend(["--check", "--force"])
        return params


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


class TarSettings(BaseModel):
    """Configuration for TAR operations."""

    method: str = Field(
        default="auto", description="TAR creation method (auto/gnu/bsd/python)"
    )
    sort_files: bool = Field(
        default=True, description="Sort files for deterministic output"
    )
    preserve_permissions: bool = Field(
        default=True, description="Preserve file permissions"
    )

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate TAR method."""
        valid_methods = {"auto", "gnu", "bsd", "python"}
        if v not in valid_methods:
            raise ValueError(f"TAR method must be one of: {valid_methods}")
        return v


class ArchiveMetadata(BaseModel):
    """Comprehensive metadata for archive operations with complete persistence support."""

    # Core identification
    source_path: Path
    archive_path: Path
    archive_name: str = Field(description="Name of the archive (without extension)")

    # Version and creation info
    coldpack_version: str = Field(
        default="1.0.0-dev", description="coldpack version used"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )
    created_at_iso: str = Field(default="", description="ISO formatted creation time")

    # Processing settings (complete configuration preservation)
    compression_settings: CompressionSettings
    par2_settings: PAR2Settings = Field(default_factory=PAR2Settings)
    tar_settings: TarSettings = Field(default_factory=TarSettings)

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
            "compression": {
                "level": self.compression_settings.level,
                "threads": self.compression_settings.threads,
                "long_mode": self.compression_settings.long_mode,
                "long_distance": self.compression_settings.long_distance,
                "ultra_mode": self.compression_settings.ultra_mode,
            },
            "par2": {
                "redundancy_percent": self.par2_settings.redundancy_percent,
                "block_count": self.par2_settings.block_count,
                "files": self.par2_files,
            },
            "tar": {
                "method": self.tar_settings.method,
                "sort_files": self.tar_settings.sort_files,
                "preserve_permissions": self.tar_settings.preserve_permissions,
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
        compression_section = toml_data.get("compression", {})
        par2_section = toml_data.get("par2", {})
        tar_section = toml_data.get("tar", {})
        integrity_section = toml_data.get("integrity", {})
        processing_section = toml_data.get("processing", {})

        # Reconstruct settings objects
        compression_settings = CompressionSettings(**compression_section)
        par2_settings = PAR2Settings(
            redundancy_percent=par2_section.get("redundancy_percent", 10),
            block_count=par2_section.get("block_count", 2000),
        )
        tar_settings = TarSettings(**tar_section)

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
            # Settings
            compression_settings=compression_settings,
            par2_settings=par2_settings,
            tar_settings=tar_settings,
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
    verify_tar: bool = Field(default=True, description="Enable TAR header verification")
    verify_zstd: bool = Field(
        default=True, description="Enable Zstd integrity verification"
    )
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
