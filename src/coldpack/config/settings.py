"""Pydantic settings models for coldpack configuration."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator

# Handle tomllib compatibility (Python 3.11+ has tomllib built-in)
if sys.version_info >= (3, 11):
    import tomllib

    HAS_TOMLLIB = True
else:
    # For Python < 3.11, try to use tomli
    HAS_TOMLLIB = False
    try:
        import tomli as tomllib  # type: ignore[import-not-found, import-untyped, unused-ignore]

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


class ArchiveMetadata(BaseModel):
    """Metadata for archive operations."""

    source_path: Path
    archive_path: Path
    compression_settings: CompressionSettings
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    file_count: int = Field(default=0, ge=0)
    original_size: int = Field(default=0, ge=0)
    compressed_size: int = Field(default=0, ge=0)
    compression_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    verification_hashes: dict[str, str] = Field(default_factory=dict)
    par2_files: list[str] = Field(default_factory=list)
    par2_redundancy: int = Field(
        default=10, ge=1, le=50, description="PAR2 redundancy percentage"
    )

    @property
    def compression_percentage(self) -> float:
        """Get compression percentage (100% - compression_ratio * 100)."""
        return (1.0 - self.compression_ratio) * 100.0

    def calculate_compression_ratio(self) -> None:
        """Calculate compression ratio from original and compressed sizes."""
        if self.original_size > 0:
            self.compression_ratio = self.compressed_size / self.original_size
        else:
            self.compression_ratio = 0.0

    @classmethod
    def load_from_toml(cls, file_path: Union[str, Path]) -> "ArchiveMetadata":
        """Load ArchiveMetadata from a TOML file.

        Args:
            file_path: Path to the TOML metadata file

        Returns:
            ArchiveMetadata instance

        Raises:
            FileNotFoundError: If TOML file doesn't exist
            ValueError: If TOML parsing fails or required TOML library unavailable
        """
        toml_path = Path(file_path)

        if not toml_path.exists():
            raise FileNotFoundError(f"TOML metadata file not found: {toml_path}")

        if HAS_TOMLLIB:
            # Use tomllib (Python 3.11+) or tomli
            with open(toml_path, "rb") as f:
                toml_data = tomllib.load(f)
        else:
            # Fallback to toml library
            try:
                import toml

                with open(toml_path, encoding="utf-8") as f:
                    toml_data = toml.load(f)
            except ImportError as e:
                raise ValueError(
                    "No TOML library available. Install tomli for Python < 3.11"
                ) from e

        # Convert string paths back to Path objects
        if "source_path" in toml_data:
            toml_data["source_path"] = Path(toml_data["source_path"])
        if "archive_path" in toml_data:
            toml_data["archive_path"] = Path(toml_data["archive_path"])

        # Parse nested compression_settings if present
        if "compression_settings" in toml_data:
            toml_data["compression_settings"] = CompressionSettings(
                **toml_data["compression_settings"]
            )

        return cls(**toml_data)


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
