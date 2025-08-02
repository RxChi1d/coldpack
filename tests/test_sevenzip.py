"""Tests for 7z compression utilities using py7zz."""

from unittest.mock import Mock, patch

import pytest

from coldpack.config.settings import SevenZipSettings
from coldpack.utils.sevenzip import (
    CompressionError,
    SevenZipCompressor,
    get_7z_info,
    optimize_7z_compression_settings,
    validate_7z_archive,
)


class TestSevenZipSettings:
    """Test SevenZipSettings configuration class."""

    def test_default_settings(self):
        """Test default 7z settings."""
        settings = SevenZipSettings()
        assert settings.level == 5
        assert settings.dictionary_size == "16m"
        assert settings.threads == 0
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_custom_settings(self):
        """Test custom 7z settings."""
        settings = SevenZipSettings(
            level=7, dictionary_size="64m", threads=4, solid=False, method="LZMA"
        )
        assert settings.level == 7
        assert settings.dictionary_size == "64m"
        assert settings.threads == 4
        assert settings.solid is False
        assert settings.method == "LZMA"

    def test_level_bounds_validation(self):
        """Test compression level bounds validation."""
        # Valid levels
        SevenZipSettings(level=1)
        SevenZipSettings(level=9)

        # Invalid levels should raise validation error
        with pytest.raises(ValueError):
            SevenZipSettings(level=0)  # Below minimum

        with pytest.raises(ValueError):
            SevenZipSettings(level=-1)

        with pytest.raises(ValueError):
            SevenZipSettings(level=10)

    def test_dictionary_size_validation(self):
        """Test dictionary size validation."""
        # Valid sizes based on the updated parameter table
        for size in ["128k", "1m", "4m", "16m", "64m", "256m", "512m"]:
            settings = SevenZipSettings(dictionary_size=size)
            assert settings.dictionary_size == size

        # Invalid size should raise validation error
        with pytest.raises(ValueError):
            SevenZipSettings(dictionary_size="128m")

        with pytest.raises(ValueError):
            SevenZipSettings(dictionary_size="invalid")

    def test_method_validation(self):
        """Test compression method validation."""
        # Valid methods
        for method in ["LZMA2", "LZMA", "PPMd", "BZip2"]:
            settings = SevenZipSettings(method=method)
            assert settings.method == method

        # Invalid method should raise validation error
        with pytest.raises(ValueError):
            SevenZipSettings(method="INVALID")

    def test_to_py7zz_config(self):
        """Test conversion to py7zz config dictionary."""
        settings = SevenZipSettings(
            level=7, dictionary_size="64m", threads=4, solid=False, method="LZMA"
        )
        config = settings.to_py7zz_config()

        expected = {
            "level": 7,
            "compression": "lzma",  # Changed from "method" to "compression" and lowercase
            "dictionary_size": "64m",
            "solid": False,
            "threads": 4,
        }
        assert config == expected


class TestSevenZipCompressor:
    """Test SevenZipCompressor class."""

    def test_initialization_default_settings(self):
        """Test SevenZipCompressor initialization with default settings."""
        compressor = SevenZipCompressor()
        assert compressor.settings.level == 5
        assert compressor.settings.dictionary_size == "16m"
        assert compressor._preset == "balanced"  # level 5 maps to balanced

    def test_initialization_custom_settings(self):
        """Test SevenZipCompressor initialization with custom settings."""
        settings = SevenZipSettings(level=7, dictionary_size="64m")
        compressor = SevenZipCompressor(settings)
        assert compressor.settings.level == 7
        assert compressor.settings.dictionary_size == "64m"
        assert compressor._preset == "maximum"  # level 7 maps to maximum

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_compress_directory_success(self, mock_py7zz, tmp_path):
        """Test successful directory compression."""
        # Create test directory structure
        test_dir = tmp_path / "test_source"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("test content 1")
        (test_dir / "file2.txt").write_text("test content 2")

        # Test compression
        compressor = SevenZipCompressor()
        archive_path = tmp_path / "test.7z"

        compressor.compress_directory(test_dir, archive_path)

        # Verify py7zz.create_archive was called correctly
        mock_py7zz.create_archive.assert_called_once_with(
            str(archive_path), [str(test_dir)], preset="balanced"
        )

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_compress_directory_with_progress_callback(self, mock_py7zz, tmp_path):
        """Test directory compression with progress callback."""
        # Create test directory
        test_dir = tmp_path / "test_source"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("test content")

        # Create progress callback
        progress_calls = []

        def progress_callback(percentage, current_file):
            progress_calls.append((percentage, current_file))

        # Test compression with callback (progress callbacks not supported in current simple API)
        compressor = SevenZipCompressor()
        archive_path = tmp_path / "test.7z"

        compressor.compress_directory(test_dir, archive_path, progress_callback)

        # Verify py7zz.create_archive was called correctly
        mock_py7zz.create_archive.assert_called_once_with(
            str(archive_path), [str(test_dir)], preset="balanced"
        )

    def test_compress_directory_nonexistent_source(self, tmp_path):
        """Test compression with non-existent source."""
        compressor = SevenZipCompressor()
        nonexistent_dir = tmp_path / "nonexistent"
        archive_path = tmp_path / "test.7z"

        with pytest.raises(FileNotFoundError, match="Source directory not found"):
            compressor.compress_directory(nonexistent_dir, archive_path)

    def test_compress_directory_not_directory(self, tmp_path):
        """Test compression with file instead of directory."""
        compressor = SevenZipCompressor()
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test content")
        archive_path = tmp_path / "test.7z"

        with pytest.raises(ValueError, match="Source must be a directory"):
            compressor.compress_directory(test_file, archive_path)

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_compress_directory_py7zz_error(self, mock_py7zz, tmp_path):
        """Test handling of py7zz compression errors."""
        # Create test directory
        test_dir = tmp_path / "test_source"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("test content")

        # Setup mocks to raise error
        # Create proper exception class for py7zz
        mock_py7zz.CompressionError = type("CompressionError", (Exception,), {})
        mock_py7zz.create_archive.side_effect = mock_py7zz.CompressionError(
            "Compression failed"
        )

        compressor = SevenZipCompressor()
        archive_path = tmp_path / "test.7z"

        with pytest.raises(CompressionError, match="7z compression failed"):
            compressor.compress_directory(test_dir, archive_path)

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_test_integrity_success(self, mock_py7zz, tmp_path):
        """Test successful archive integrity test."""
        archive_path = tmp_path / "test.7z"
        archive_path.write_text("mock archive content")

        mock_py7zz.test_archive.return_value = True

        compressor = SevenZipCompressor()
        result = compressor.test_integrity(archive_path)

        assert result is True
        mock_py7zz.test_archive.assert_called_once_with(str(archive_path))

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_test_integrity_failure(self, mock_py7zz, tmp_path):
        """Test failed archive integrity test."""
        archive_path = tmp_path / "test.7z"
        archive_path.write_text("mock archive content")

        mock_py7zz.test_archive.return_value = False

        compressor = SevenZipCompressor()
        result = compressor.test_integrity(archive_path)

        assert result is False

    def test_test_integrity_nonexistent_archive(self, tmp_path):
        """Test integrity test with non-existent archive."""
        compressor = SevenZipCompressor()
        nonexistent_archive = tmp_path / "nonexistent.7z"

        result = compressor.test_integrity(nonexistent_archive)
        assert result is False

    def test_progress_adapter(self):
        """Test progress callback adapter."""
        compressor = SevenZipCompressor()

        progress_calls = []

        def test_callback(percentage, current_file):
            progress_calls.append((percentage, current_file))

        adapter = compressor._create_progress_adapter(test_callback)

        # Test with mock progress info
        mock_progress_info = Mock()
        mock_progress_info.percentage = 50.5
        mock_progress_info.current_file = "test_file.txt"

        adapter(mock_progress_info)

        assert len(progress_calls) == 1
        assert progress_calls[0] == (50, "test_file.txt")

    def test_progress_adapter_missing_attributes(self):
        """Test progress adapter with missing attributes."""
        compressor = SevenZipCompressor()

        progress_calls = []

        def test_callback(percentage, current_file):
            progress_calls.append((percentage, current_file))

        adapter = compressor._create_progress_adapter(test_callback)

        # Test with mock progress info missing attributes
        mock_progress_info = Mock(spec=[])  # No attributes

        adapter(mock_progress_info)

        assert len(progress_calls) == 1
        assert progress_calls[0] == (0, "Processing...")


class TestOptimization:
    """Test 7z compression optimization functions."""

    def test_optimize_tiny_size(self):
        """Test optimization for tiny files (< 256 KiB)."""
        # 100 KiB
        settings = optimize_7z_compression_settings(100 * 1024)
        assert settings.level == 1
        assert settings.dictionary_size == "128k"
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_optimize_small_size(self):
        """Test optimization for small files (256 KiB – 1 MiB)."""
        # 500 KiB
        settings = optimize_7z_compression_settings(500 * 1024)
        assert settings.level == 3
        assert settings.dictionary_size == "1m"
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_optimize_small_medium_size(self):
        """Test optimization for small-medium files (1 – 8 MiB)."""
        # 4 MiB
        settings = optimize_7z_compression_settings(4 * 1024 * 1024)
        assert settings.level == 5
        assert settings.dictionary_size == "4m"
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_optimize_medium_size(self):
        """Test optimization for medium files (8 – 64 MiB)."""
        # 32 MiB
        settings = optimize_7z_compression_settings(32 * 1024 * 1024)
        assert settings.level == 6
        assert settings.dictionary_size == "16m"
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_optimize_large_size(self):
        """Test optimization for large files (64 – 512 MiB)."""
        # 256 MiB
        settings = optimize_7z_compression_settings(256 * 1024 * 1024)
        assert settings.level == 7
        assert settings.dictionary_size == "64m"
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_optimize_very_large_size(self):
        """Test optimization for very large files (512 MiB – 2 GiB)."""
        # 1 GiB
        settings = optimize_7z_compression_settings(1024 * 1024 * 1024)
        assert settings.level == 9
        assert settings.dictionary_size == "256m"
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_optimize_huge_size(self):
        """Test optimization for huge files (> 2 GiB)."""
        # 4 GiB
        settings = optimize_7z_compression_settings(4 * 1024 * 1024 * 1024)
        assert settings.level == 9
        assert settings.dictionary_size == "512m"
        assert settings.solid is True
        assert settings.method == "LZMA2"

    def test_optimize_boundary_conditions(self):
        """Test optimization at precise boundary conditions."""
        # Exactly 256 KiB - should be tiny
        settings = optimize_7z_compression_settings(256 * 1024)
        assert settings.level == 3  # Small file range

        # Exactly 1 MiB - should be small
        settings = optimize_7z_compression_settings(1024 * 1024)
        assert settings.level == 5  # Small-medium range

        # Exactly 8 MiB - should be small-medium
        settings = optimize_7z_compression_settings(8 * 1024 * 1024)
        assert settings.level == 6  # Medium range

        # Exactly 64 MiB - should be medium
        settings = optimize_7z_compression_settings(64 * 1024 * 1024)
        assert settings.level == 7  # Large range

        # Exactly 512 MiB - should be large
        settings = optimize_7z_compression_settings(512 * 1024 * 1024)
        assert settings.level == 9  # Very large range

        # Exactly 2 GiB - should be very large
        settings = optimize_7z_compression_settings(2 * 1024 * 1024 * 1024)
        assert settings.level == 9  # Huge range

    def test_optimize_with_threads(self):
        """Test optimization with custom thread count."""
        # Test with specific thread count
        settings = optimize_7z_compression_settings(1024 * 1024, threads=4)
        assert settings.level == 5  # Small-medium range
        assert settings.dictionary_size == "4m"
        assert settings.threads == 4

        # Test with auto-detect threads (default)
        settings = optimize_7z_compression_settings(1024 * 1024)
        assert settings.threads == 0  # Auto-detect


class TestUtilityFunctions:
    """Test utility functions for 7z operations."""

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_get_7z_info_success(self, mock_py7zz, tmp_path):
        """Test successful 7z archive info retrieval with py7zz v1.0.0 API."""
        archive_path = tmp_path / "test.7z"
        archive_path.write_text("mock archive")

        # Mock py7zz.get_archive_info (v1.0.0: only returns statistics)
        mock_py7zz.get_archive_info.return_value = {
            "compressed_size": 1024,
            "file_count": 2,
            "uncompressed_size": 2048,
            "compression_ratio": 0.5,
        }

        # Mock SevenZipFile for file list analysis
        mock_archive = mock_py7zz.SevenZipFile.return_value.__enter__.return_value
        mock_archive.namelist.return_value = [
            "root_dir/file1.txt",
            "root_dir/file2.txt",
        ]

        info = get_7z_info(archive_path)

        assert info["path"] == str(archive_path)
        assert info["format"] == ".7z"
        assert info["file_count"] == 2
        assert info["has_single_root"] is True
        assert info["root_name"] == "root_dir"

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_get_7z_info_multiple_roots(self, mock_py7zz, tmp_path):
        """Test 7z info with multiple root directories."""
        archive_path = tmp_path / "test.7z"
        archive_path.write_text("mock archive")

        # Mock py7zz.get_archive_info (v1.0.0: only returns statistics)
        mock_py7zz.get_archive_info.return_value = {
            "compressed_size": 1024,
            "file_count": 3,
            "uncompressed_size": 2048,
            "compression_ratio": 0.5,
        }

        # Mock SevenZipFile for file list analysis (multiple roots)
        mock_archive = mock_py7zz.SevenZipFile.return_value.__enter__.return_value
        mock_archive.namelist.return_value = [
            "dir1/file1.txt",
            "dir2/file2.txt",
            "file3.txt",
        ]

        info = get_7z_info(archive_path)

        assert info["has_single_root"] is False
        assert info["root_name"] is None

    def test_get_7z_info_nonexistent_archive(self, tmp_path):
        """Test 7z info with non-existent archive."""
        nonexistent_archive = tmp_path / "nonexistent.7z"

        with pytest.raises(FileNotFoundError):
            get_7z_info(nonexistent_archive)

    @patch("coldpack.utils.sevenzip.SevenZipCompressor")
    def test_validate_7z_archive_success(self, mock_compressor):
        """Test successful 7z archive validation."""
        mock_compressor_instance = Mock()
        mock_compressor_instance.test_integrity.return_value = True
        mock_compressor.return_value = mock_compressor_instance

        result = validate_7z_archive("test.7z")
        assert result is True

    @patch("coldpack.utils.sevenzip.SevenZipCompressor")
    def test_validate_7z_archive_failure(self, mock_compressor):
        """Test failed 7z archive validation."""
        mock_compressor_instance = Mock()
        mock_compressor_instance.test_integrity.return_value = False
        mock_compressor.return_value = mock_compressor_instance

        result = validate_7z_archive("test.7z")
        assert result is False

    @patch("coldpack.utils.sevenzip.SevenZipCompressor")
    def test_validate_7z_archive_exception(self, mock_compressor):
        """Test 7z archive validation with exception."""
        mock_compressor.side_effect = Exception("Test error")

        result = validate_7z_archive("test.7z")
        assert result is False


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility features."""

    def test_path_handling(self, tmp_path):
        """Test that Path objects are converted to strings for py7zz."""
        compressor = SevenZipCompressor()

        # Test with Path objects
        test_dir = tmp_path / "test_source"
        test_dir.mkdir()
        (test_dir / "test_file.txt").write_text("test content")
        archive_path = tmp_path / "test.7z"

        # This should not raise an error about Path objects - just test that it works
        with patch("coldpack.utils.sevenzip.py7zz") as mock_py7zz:
            # Should complete without errors
            compressor.compress_directory(test_dir, archive_path)

            # Verify that create_archive was called with string paths
            assert mock_py7zz.create_archive.call_count == 1
            call_args = mock_py7zz.create_archive.call_args
            assert isinstance(call_args[0][0], str)  # archive path is string
            assert isinstance(call_args[0][1][0], str)  # source path is string
            assert call_args[1]["preset"] == "balanced"


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_compression_error_types(self, mock_py7zz, tmp_path):
        """Test different types of compression errors."""
        test_dir = tmp_path / "test_source"
        test_dir.mkdir()
        archive_path = tmp_path / "test.7z"

        compressor = SevenZipCompressor()

        # Create proper exception classes for py7zz
        mock_py7zz.CompressionError = type("CompressionError", (Exception,), {})
        mock_py7zz.FileNotFoundError = type("FileNotFoundError", (Exception,), {})
        mock_py7zz.InsufficientSpaceError = type(
            "InsufficientSpaceError", (Exception,), {}
        )

        # Test CompressionError
        mock_py7zz.create_archive.side_effect = mock_py7zz.CompressionError(
            "Compression failed"
        )
        with pytest.raises(CompressionError):
            compressor.compress_directory(test_dir, archive_path)

        # Test FileNotFoundError
        mock_py7zz.create_archive.side_effect = mock_py7zz.FileNotFoundError(
            "File not found"
        )
        with pytest.raises(FileNotFoundError):
            compressor.compress_directory(test_dir, archive_path)

        # Test InsufficientSpaceError
        mock_py7zz.create_archive.side_effect = mock_py7zz.InsufficientSpaceError(
            "Not enough space"
        )
        with pytest.raises(CompressionError, match="Insufficient disk space"):
            compressor.compress_directory(test_dir, archive_path)

        # Test generic Exception
        mock_py7zz.create_archive.side_effect = Exception("Generic error")
        with pytest.raises(CompressionError, match="Unexpected error"):
            compressor.compress_directory(test_dir, archive_path)

    def test_progress_callback_exception_handling(self):
        """Test that progress callback exceptions don't break compression."""
        compressor = SevenZipCompressor()

        def failing_callback(percentage, current_file):
            raise Exception("Callback error")

        adapter = compressor._create_progress_adapter(failing_callback)

        # This should not raise an exception
        mock_progress_info = Mock()
        mock_progress_info.percentage = 50
        mock_progress_info.current_file = "test.txt"

        adapter(mock_progress_info)  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
