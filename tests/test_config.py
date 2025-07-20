"""Tests for configuration modules."""

import pytest

from coldpack.config.constants import DEFAULT_COMPRESSION_LEVEL, SUPPORTED_INPUT_FORMATS
from coldpack.config.settings import ArchiveMetadata, CompressionSettings


class TestCompressionSettings:
    """Test compression settings validation."""

    def test_default_settings(self):
        """Test default compression settings."""
        settings = CompressionSettings()
        assert settings.level == DEFAULT_COMPRESSION_LEVEL
        assert settings.threads == 0
        assert settings.long_mode is True
        assert settings.ultra_mode is False

    def test_ultra_mode_validation(self):
        """Test ultra mode validation based on compression level."""
        # Ultra mode should be allowed for level 20+
        settings = CompressionSettings(level=20, ultra_mode=True)
        assert settings.ultra_mode is True

        # Ultra mode should raise error for level < 20
        with pytest.raises(
            ValueError, match="Ultra mode requires compression level >= 20"
        ):
            CompressionSettings(level=19, ultra_mode=True)

    def test_compression_level_bounds(self):
        """Test compression level bounds validation."""
        # Valid levels
        CompressionSettings(level=1)
        CompressionSettings(level=22)

        # Invalid levels should raise validation error
        with pytest.raises(ValueError):
            CompressionSettings(level=0)

        with pytest.raises(ValueError):
            CompressionSettings(level=23)

    def test_to_zstd_params(self):
        """Test conversion to zstd parameters."""
        settings = CompressionSettings(level=15, threads=4, long_mode=True)
        params = settings.to_zstd_params()

        assert "-15" in params
        assert "-T4" in params
        assert "--long=31" in params
        assert "--check" in params
        assert "--force" in params


class TestArchiveMetadata:
    """Test archive metadata handling."""

    def test_metadata_creation(self, tmp_path):
        """Test creating archive metadata."""
        source_path = tmp_path / "source"
        archive_path = tmp_path / "archive.tar.zst"
        settings = CompressionSettings()

        metadata = ArchiveMetadata(
            source_path=source_path,
            archive_path=archive_path,
            compression_settings=settings,
            original_size=1000,
            compressed_size=600,
        )

        assert metadata.source_path == source_path
        assert metadata.archive_path == archive_path
        assert metadata.original_size == 1000
        assert metadata.compressed_size == 600

    def test_compression_ratio_calculation(self, tmp_path):
        """Test compression ratio calculation."""
        metadata = ArchiveMetadata(
            source_path=tmp_path / "source",
            archive_path=tmp_path / "archive.tar.zst",
            compression_settings=CompressionSettings(),
            original_size=1000,
            compressed_size=600,
        )

        metadata.calculate_compression_ratio()
        assert metadata.compression_ratio == 0.6
        assert metadata.compression_percentage == 40.0


class TestConstants:
    """Test constants and configuration values."""

    def test_supported_formats(self):
        """Test supported input formats."""
        assert ".7z" in SUPPORTED_INPUT_FORMATS
        assert ".zip" in SUPPORTED_INPUT_FORMATS
        assert ".tar.gz" in SUPPORTED_INPUT_FORMATS
        assert len(SUPPORTED_INPUT_FORMATS) > 5

    def test_compression_level_default(self):
        """Test default compression level."""
        assert DEFAULT_COMPRESSION_LEVEL == 19
        assert 1 <= DEFAULT_COMPRESSION_LEVEL <= 22
