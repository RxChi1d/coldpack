"""Tests for coldpack extractor functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest

from coldpack.core.extractor import (
    MultiFormatExtractor,
    UnsupportedFormatError,
)


class TestMultiFormatExtractor:
    """Test the multi-format extractor."""

    @pytest.fixture
    def extractor(self):
        """Create an extractor instance."""
        return MultiFormatExtractor()

    @pytest.fixture
    def mock_7z_file(self, tmp_path):
        """Create a mock 7z file for testing."""
        archive_path = tmp_path / "test.7z"
        archive_path.write_bytes(b"dummy 7z content")
        return archive_path

    def test_extractor_initialization(self, extractor):
        """Test that extractor initializes correctly."""
        assert isinstance(extractor, MultiFormatExtractor)

    def test_is_supported_format(self, extractor):
        """Test format support detection."""
        # Test supported formats
        assert extractor._is_supported_format(Path("test.7z"))
        assert extractor._is_supported_format(Path("test.zip"))
        assert extractor._is_supported_format(Path("test.rar"))
        assert extractor._is_supported_format(Path("test.tar.gz"))
        assert extractor._is_supported_format(Path("test.tar.zst"))

        # Test unsupported format
        assert not extractor._is_supported_format(Path("test.unsupported"))

    def test_is_7z_format(self, extractor):
        """Test 7z format detection."""
        assert extractor._is_7z_format(Path("test.7z"))
        assert extractor._is_7z_format(Path("TEST.7Z"))  # case insensitive
        assert not extractor._is_7z_format(Path("test.zip"))

    def test_is_tar_zst_format(self, extractor):
        """Test tar.zst format detection."""
        assert extractor._is_tar_zst_format(Path("test.tar.zst"))
        assert extractor._is_tar_zst_format(Path("TEST.TAR.ZST"))  # case insensitive
        assert not extractor._is_tar_zst_format(Path("test.zst"))
        assert not extractor._is_tar_zst_format(Path("test.tar.gz"))

    def test_is_compound_tar_format(self, extractor):
        """Test compound tar format detection."""
        assert extractor._is_compound_tar_format(Path("test.tar.gz"))
        assert extractor._is_compound_tar_format(Path("test.tar.bz2"))
        assert extractor._is_compound_tar_format(Path("test.tar.xz"))
        assert not extractor._is_compound_tar_format(
            Path("test.tar.zst")
        )  # This is handled separately
        assert not extractor._is_compound_tar_format(Path("test.tar"))

    def test_get_clean_archive_name(self, extractor):
        """Test clean archive name extraction."""
        # Test single extensions
        assert extractor._get_clean_archive_name(Path("test.7z")) == "test"
        assert extractor._get_clean_archive_name(Path("test.zip")) == "test"

        # Test compound extensions
        assert extractor._get_clean_archive_name(Path("test.tar.gz")) == "test"
        assert extractor._get_clean_archive_name(Path("test.tar.zst")) == "test"
        assert extractor._get_clean_archive_name(Path("test.tar.bz2")) == "test"

        # Test no extension
        assert extractor._get_clean_archive_name(Path("test")) == "test"

        # Test directory
        test_dir = Path("/tmp/test_directory")
        assert extractor._get_clean_archive_name(test_dir) == "test_directory"

    def test_validate_archive_file_not_found(self, extractor):
        """Test validation with non-existent file."""
        with pytest.raises(FileNotFoundError):
            extractor.validate_archive(Path("nonexistent.7z"))

    def test_validate_archive_unsupported_format(self, extractor, tmp_path):
        """Test validation with unsupported format."""
        # Create a dummy file with unsupported extension
        unsupported_file = tmp_path / "test.unsupported"
        unsupported_file.write_text("dummy content")

        with pytest.raises(UnsupportedFormatError):
            extractor.validate_archive(unsupported_file)

    @patch("py7zz.SevenZipFile")
    def test_validate_archive_success(self, mock_7z, extractor, mock_7z_file):
        """Test successful archive validation."""
        # Mock py7zz behavior
        mock_archive = mock_7z.return_value.__enter__.return_value
        mock_archive.namelist.return_value = ["file1.txt", "file2.txt"]

        result = extractor.validate_archive(mock_7z_file)
        assert result is True

    @patch("py7zz.SevenZipFile")
    def test_validate_archive_empty(self, mock_7z, extractor, mock_7z_file):
        """Test validation with empty archive."""
        # Mock py7zz behavior for empty archive
        mock_archive = mock_7z.return_value.__enter__.return_value
        mock_archive.namelist.return_value = []

        result = extractor.validate_archive(mock_7z_file)
        assert result is False

    @patch("py7zz.SevenZipFile")
    def test_validate_archive_corrupted(self, mock_7z, extractor, mock_7z_file):
        """Test validation with corrupted archive."""
        # Mock py7zz behavior for corrupted archive
        mock_7z.return_value.__enter__.side_effect = Exception("Corrupted archive")

        result = extractor.validate_archive(mock_7z_file)
        assert result is False

    def test_extract_nonexistent_file(self, extractor, tmp_path):
        """Test extraction with non-existent source."""
        with pytest.raises(FileNotFoundError):
            extractor.extract("nonexistent.7z", tmp_path)

    def test_extract_unsupported_format(self, extractor, tmp_path):
        """Test extraction with unsupported format."""
        # Create a dummy file with unsupported extension
        unsupported_file = tmp_path / "test.unsupported"
        unsupported_file.write_text("dummy content")

        with pytest.raises(UnsupportedFormatError):
            extractor.extract(unsupported_file, tmp_path / "output")

    def test_handle_directory_input(self, extractor, tmp_path):
        """Test handling directory input."""
        test_dir = tmp_path / "test_directory"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("test content")

        output_dir = tmp_path / "output"
        result = extractor.extract(test_dir, output_dir)

        # Should return the source directory directly
        assert result == test_dir

    @patch("py7zz.SevenZipFile")
    def test_get_archive_info(self, mock_7z, extractor, mock_7z_file):
        """Test getting archive information."""
        # Mock py7zz behavior
        mock_archive = mock_7z.return_value.__enter__.return_value
        mock_archive.namelist.return_value = ["file1.txt", "dir/file2.txt"]

        info = extractor.get_archive_info(mock_7z_file)

        assert info["path"] == str(mock_7z_file)
        assert info["format"] == ".7z"
        assert info["file_count"] == 2
        assert "size" in info
        assert "has_single_root" in info

    def test_get_archive_info_nonexistent(self, extractor):
        """Test getting info for non-existent archive."""
        with pytest.raises(FileNotFoundError):
            extractor.get_archive_info("nonexistent.7z")

    def test_get_archive_info_unsupported_format(self, extractor, tmp_path):
        """Test getting info for unsupported format."""
        unsupported_file = tmp_path / "test.unsupported"
        unsupported_file.write_text("dummy content")

        with pytest.raises(UnsupportedFormatError):
            extractor.get_archive_info(unsupported_file)


class TestExtractorIntegrationWithCLI:
    """Test extractor integration with CLI verify option."""

    @pytest.fixture
    def extractor(self):
        """Create an extractor instance."""
        return MultiFormatExtractor()

    @patch("py7zz.SevenZipFile")
    def test_verify_before_extraction_success(self, mock_7z, extractor, tmp_path):
        """Test the verify before extraction workflow (success case)."""
        # Create mock archive file
        archive_path = tmp_path / "test.7z"
        archive_path.write_bytes(b"dummy 7z content")

        # Mock py7zz behavior for validation
        mock_archive = mock_7z.return_value.__enter__.return_value
        mock_archive.namelist.return_value = ["file1.txt", "file2.txt"]

        # Test validation step (this would be called with --verify flag)
        validation_result = extractor.validate_archive(archive_path)
        assert validation_result is True

        # The extraction would proceed normally after successful validation

    @patch("py7zz.SevenZipFile")
    def test_verify_before_extraction_failure(self, mock_7z, extractor, tmp_path):
        """Test the verify before extraction workflow (failure case)."""
        # Create mock archive file
        archive_path = tmp_path / "test.7z"
        archive_path.write_bytes(b"dummy 7z content")

        # Mock py7zz behavior for validation failure
        mock_7z.return_value.__enter__.side_effect = Exception("Corrupted archive")

        # Test validation step (this would be called with --verify flag)
        validation_result = extractor.validate_archive(archive_path)
        assert validation_result is False

        # In CLI, the extraction would still proceed with a warning message
