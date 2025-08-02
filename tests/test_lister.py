"""Tests for coldpack archive listing functionality with new py7zz.run_7z implementation."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coldpack.core.lister import (
    ArchiveFile,
    ArchiveLister,
    ListingError,
    UnsupportedFormatError,
    list_archive_contents,
)


class TestArchiveFile:
    """Test the ArchiveFile class."""

    def test_archive_file_initialization(self):
        """Test ArchiveFile initialization with basic parameters."""
        file = ArchiveFile(path="test/file.txt", size=1024, is_directory=False)

        assert file.path == "test/file.txt"
        assert file.name == "file.txt"
        assert file.size == 1024
        assert file.is_directory is False
        assert file.level == 1  # "test" is level 0, "file.txt" is level 1

    def test_archive_file_directory(self):
        """Test ArchiveFile for directory entries."""
        dir_file = ArchiveFile(path="test_dir/", size=0, is_directory=True)

        assert dir_file.path == "test_dir/"
        assert dir_file.name == "test_dir"
        assert dir_file.is_directory is True
        assert dir_file.level == 0

    def test_archive_file_with_metadata(self):
        """Test ArchiveFile with complete metadata."""
        modified = datetime(2023, 7, 24, 12, 30, 45)
        file = ArchiveFile(
            path="docs/readme.md",
            size=2048,
            compressed_size=1024,
            modified=modified,
            is_directory=False,
            crc="a1b2c3d4",
        )

        assert file.path == "docs/readme.md"
        assert file.size == 2048
        assert file.compressed_size == 1024
        assert file.modified == modified
        assert file.crc == "a1b2c3d4"


class TestArchiveListerNew:
    """Test the ArchiveLister class with new implementation."""

    @pytest.fixture
    def lister(self):
        """Create a lister instance."""
        return ArchiveLister()

    @pytest.fixture
    def mock_archive_path(self, tmp_path):
        """Create a mock archive file."""
        archive_path = tmp_path / "test.7z"
        archive_path.write_bytes(b"dummy archive content")
        return archive_path

    def test_lister_initialization(self, lister):
        """Test that lister initializes correctly."""
        assert isinstance(lister, ArchiveLister)

    def test_is_supported_format(self, lister):
        """Test format support detection."""
        # Test supported formats
        assert lister._is_supported_format(Path("test.7z"))
        assert lister._is_supported_format(Path("test.zip"))
        assert lister._is_supported_format(Path("test.rar"))
        assert lister._is_supported_format(Path("test.tar"))
        assert lister._is_supported_format(Path("test.tar.gz"))

        # Test unsupported format
        assert not lister._is_supported_format(Path("test.unsupported"))
        assert not lister._is_supported_format(Path("test.txt"))

    def test_list_archive_file_not_found(self, lister):
        """Test listing non-existent archive."""
        with pytest.raises(FileNotFoundError, match="Archive not found"):
            lister.list_archive("/nonexistent/archive.7z")

    def test_list_archive_unsupported_format(self, lister, tmp_path):
        """Test listing unsupported archive format."""
        unsupported_file = tmp_path / "test.unsupported"
        unsupported_file.write_text("dummy content")

        with pytest.raises(
            UnsupportedFormatError, match="is not supported for listing"
        ):
            lister.list_archive(unsupported_file)

    @patch("coldpack.core.lister.py7zz")
    def test_list_archive_basic(self, mock_py7zz, lister, mock_archive_path):
        """Test basic archive listing functionality with py7zz v1.0.0."""
        # Mock py7zz.SevenZipFile for file listing
        mock_archive = mock_py7zz.SevenZipFile.return_value.__enter__.return_value
        mock_info_list = []

        # Create mock ArchiveInfo objects for each file
        for filename in ["test_file.txt", "subdir/", "subdir/nested_file.py"]:
            mock_info = type("MockArchiveInfo", (), {})()
            mock_info.filename = filename
            mock_info.file_size = 0
            mock_info.compress_size = 0
            mock_info.date_time = None
            mock_info.CRC = 0
            mock_info.is_dir = filename.endswith("/")
            mock_info_list.append(mock_info)

        mock_archive.infolist.return_value = mock_info_list

        # Test listing
        result = lister.list_archive(mock_archive_path)

        # Verify results
        assert result["archive_path"] == str(mock_archive_path)
        assert result["format"] == ".7z"
        assert result["total_files"] == 2  # txt and py files
        assert result["total_directories"] == 1  # subdir
        assert result["total_entries"] == 3
        assert len(result["files"]) == 3

        # Verify file objects
        files_by_path = {f.path: f for f in result["files"]}

        txt_file = files_by_path["test_file.txt"]
        assert txt_file.size == 0  # Mock provides size 0
        assert not txt_file.is_directory
        assert txt_file.crc == "00000000"  # Mock CRC value

        subdir = files_by_path["subdir/"]
        assert subdir.is_directory
        assert subdir.size == 0

        py_file = files_by_path["subdir/nested_file.py"]
        assert py_file.size == 0  # Mock provides size 0
        assert not py_file.is_directory
        assert py_file.crc == "00000000"  # Mock CRC value

    @patch("coldpack.core.lister.py7zz")
    def test_list_archive_with_filter(self, mock_py7zz, lister, mock_archive_path):
        """Test archive listing with filter using py7zz v1.0.0."""
        # Mock py7zz.SevenZipFile for file listing
        mock_archive = mock_py7zz.SevenZipFile.return_value.__enter__.return_value
        mock_info_list = []

        # Create mock ArchiveInfo objects for each file
        files_data = [
            ("document.txt", 100, 50, 0x12345678),
            ("script.py", 200, 100, 0x87654321),
            ("image.jpg", 5000, 4500, 0xABCDEF12),
            ("data.txt", 300, 150, 0x87654321),
        ]

        for filename, size, compressed_size, crc in files_data:
            mock_info = type("MockArchiveInfo", (), {})()
            mock_info.filename = filename
            mock_info.file_size = size
            mock_info.compress_size = compressed_size
            mock_info.date_time = (2025, 7, 22, 0, 5, 10)
            mock_info.CRC = crc
            mock_info.is_dir = False
            mock_info_list.append(mock_info)

        mock_archive.infolist.return_value = mock_info_list

        # Test filter for txt files
        result = lister.list_archive(mock_archive_path, filter_pattern="*.txt")

        assert len(result["files"]) == 2
        txt_files = [f.path for f in result["files"]]
        assert "document.txt" in txt_files
        assert "data.txt" in txt_files
        assert "script.py" not in txt_files

    @patch("coldpack.core.lister.py7zz")
    def test_list_archive_dirs_only(self, mock_py7zz, lister, mock_archive_path):
        """Test archive listing with dirs_only filter using py7zz v1.0.0."""
        # Mock py7zz.SevenZipFile for file listing
        mock_archive = mock_py7zz.SevenZipFile.return_value.__enter__.return_value
        mock_info_list = []

        # Create mock ArchiveInfo objects with mixed files and directories
        files_data = [
            ("file.txt", 100, 50, 0x12345678, False),
            ("dir1/", 0, 0, 0, True),
            ("dir1/subfile.py", 200, 100, 0x87654321, False),
            ("dir2/", 0, 0, 0, True),
        ]

        for filename, size, compressed_size, crc, is_dir in files_data:
            mock_info = type("MockArchiveInfo", (), {})()
            mock_info.filename = filename
            mock_info.file_size = size
            mock_info.compress_size = compressed_size
            mock_info.date_time = (2025, 7, 22, 0, 5, 10)
            mock_info.CRC = crc
            mock_info.is_dir = is_dir
            mock_info_list.append(mock_info)

        mock_archive.infolist.return_value = mock_info_list

        # Test dirs_only
        result = lister.list_archive(mock_archive_path, dirs_only=True)

        assert len(result["files"]) == 2
        dir_paths = [f.path for f in result["files"]]
        assert "dir1/" in dir_paths
        assert "dir2/" in dir_paths
        assert all(f.is_directory for f in result["files"])

    @patch("coldpack.core.lister.py7zz")
    def test_list_archive_error_handling(self, mock_py7zz, lister, mock_archive_path):
        """Test error handling when py7zz operations fail."""
        # Mock SevenZipFile to raise an exception
        mock_py7zz.SevenZipFile.side_effect = RuntimeError("Archive corrupted")

        with pytest.raises(ListingError, match="Failed to list archive contents"):
            lister.list_archive(mock_archive_path)


class TestConvenienceFunction:
    """Test the convenience function."""

    @patch("coldpack.core.lister.ArchiveLister")
    def test_list_archive_contents(self, mock_lister_class):
        """Test the convenience function."""
        mock_lister = MagicMock()
        mock_lister_class.return_value = mock_lister

        expected_result = {"test": "result"}
        mock_lister.list_archive.return_value = expected_result

        result = list_archive_contents(
            archive_path="test.7z",
            limit=10,
            offset=5,
            filter_pattern="*.txt",
            dirs_only=True,
            summary_only=False,
        )

        assert result == expected_result
        mock_lister.list_archive.assert_called_once_with(
            archive_path="test.7z",
            limit=10,
            offset=5,
            filter_pattern="*.txt",
            dirs_only=True,
            files_only=False,
            summary_only=False,
        )
