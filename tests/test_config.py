# SPDX-FileCopyrightText: 2025 coldpack contributors
# SPDX-License-Identifier: MIT

"""Tests for configuration modules."""

from coldpack.config.constants import DEFAULT_COMPRESSION_LEVEL, SUPPORTED_INPUT_FORMATS
from coldpack.config.settings import (
    ArchiveMetadata,
    SevenZipSettings,
)


class TestArchiveMetadata:
    """Test archive metadata handling."""

    def test_metadata_creation(self, tmp_path):
        """Test creating archive metadata."""
        source_path = tmp_path / "source"
        archive_path = tmp_path / "archive.7z"

        metadata = ArchiveMetadata(
            source_path=source_path,
            archive_path=archive_path,
            archive_name="test_archive",
            sevenzip_settings=SevenZipSettings(),
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
            archive_path=tmp_path / "archive.7z",
            archive_name="test_archive",
            sevenzip_settings=SevenZipSettings(),
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
