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

    @patch("coldpack.core.lister.py7zz.run_7z")
    def test_list_archive_basic(self, mock_run_7z, lister, mock_archive_path):
        """Test basic archive listing functionality."""
        # Mock 7zz l -slt output with realistic data
        mock_output = """
7-Zip (z) 25.00 (arm64) : Copyright (c) 1999-2025 Igor Pavlov : 2025-07-05

Scanning the drive for archives:
1 file, 100 bytes (1 KiB)

Listing archive: test.7z

--
Path = test.7z
Type = 7z
Physical Size = 100

----------
Path = test_file.txt
Size = 36
Packed Size = 20
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = 5CB2342E

Path = subdir
Size = 0
Packed Size = 0
Modified = 2025-07-22 00:05:10
Attributes = D drwxr-xr-x
CRC =

Path = subdir/nested_file.py
Size = 100
Packed Size = 60
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = ABC12345
"""

        # Mock the run_7z call
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_output
        mock_result.stderr = ""
        mock_run_7z.return_value = mock_result

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
        assert txt_file.size == 36
        assert not txt_file.is_directory
        assert txt_file.crc == "5CB2342E"

        subdir = files_by_path["subdir"]
        assert subdir.is_directory
        assert subdir.size == 0

        py_file = files_by_path["subdir/nested_file.py"]
        assert py_file.size == 100
        assert not py_file.is_directory
        assert py_file.crc == "ABC12345"

    @patch("coldpack.core.lister.py7zz.run_7z")
    def test_list_archive_with_filter(self, mock_run_7z, lister, mock_archive_path):
        """Test archive listing with filter."""
        # Mock output with various file types
        mock_output = """
----------
Path = document.txt
Size = 100
Packed Size = 50
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = 12345678

Path = script.py
Size = 200
Packed Size = 100
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = 87654321

Path = image.jpg
Size = 5000
Packed Size = 4500
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = ABCDEF12

Path = data.txt
Size = 300
Packed Size = 150
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = 87654321
"""

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_output
        mock_result.stderr = ""
        mock_run_7z.return_value = mock_result

        # Test filter for txt files
        result = lister.list_archive(mock_archive_path, filter_pattern="*.txt")

        assert len(result["files"]) == 2
        txt_files = [f.path for f in result["files"]]
        assert "document.txt" in txt_files
        assert "data.txt" in txt_files
        assert "script.py" not in txt_files

    @patch("coldpack.core.lister.py7zz.run_7z")
    def test_list_archive_dirs_only(self, mock_run_7z, lister, mock_archive_path):
        """Test archive listing with dirs_only filter."""
        mock_output = """
----------
Path = file.txt
Size = 100
Packed Size = 50
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = 12345678

Path = dir1
Size = 0
Packed Size = 0
Modified = 2025-07-22 00:05:10
Attributes = D drwxr-xr-x
CRC =

Path = dir1/subfile.py
Size = 200
Packed Size = 100
Modified = 2025-07-22 00:05:10
Attributes = A -rw-r--r--
CRC = 87654321

Path = dir2
Size = 0
Packed Size = 0
Modified = 2025-07-22 00:05:10
Attributes = D drwxr-xr-x
CRC =
"""

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = mock_output
        mock_result.stderr = ""
        mock_run_7z.return_value = mock_result

        # Test dirs_only
        result = lister.list_archive(mock_archive_path, dirs_only=True)

        assert len(result["files"]) == 2
        dir_paths = [f.path for f in result["files"]]
        assert "dir1" in dir_paths
        assert "dir2" in dir_paths
        assert all(f.is_directory for f in result["files"])

    @patch("coldpack.core.lister.py7zz.run_7z")
    def test_list_archive_error_handling(self, mock_run_7z, lister, mock_archive_path):
        """Test error handling when 7zz command fails."""
        # Mock failed command
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "Archive corrupted"
        mock_run_7z.return_value = mock_result

        with pytest.raises(ListingError, match="7zz command failed"):
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
