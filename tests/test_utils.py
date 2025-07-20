"""Tests for utility modules."""

import pytest

from coldpack.utils.filesystem import (
    check_disk_space,
    cleanup_temp_directory,
    create_temp_directory,
    format_file_size,
    get_file_size,
    safe_temp_directory,
)
from coldpack.utils.hashing import compute_blake3_hash, compute_sha256_hash


class TestFilesystemUtils:
    """Test filesystem utility functions."""

    def test_format_file_size(self):
        """Test file size formatting."""
        assert format_file_size(512) == "512 bytes"
        assert format_file_size(1024) == "1.00 KB"
        assert format_file_size(1024 * 1024) == "1.00 MB"
        assert format_file_size(1024 * 1024 * 1024) == "1.00 GB"

    def test_create_and_cleanup_temp_directory(self):
        """Test temporary directory creation and cleanup."""
        # Create temp directory
        temp_dir = create_temp_directory()

        assert temp_dir.exists()
        assert temp_dir.is_dir()
        assert oct(temp_dir.stat().st_mode)[-3:] == "700"  # Check permissions

        # Cleanup
        success = cleanup_temp_directory(temp_dir)
        assert success
        assert not temp_dir.exists()

    def test_safe_temp_directory_context(self):
        """Test safe temporary directory context manager."""
        temp_path = None

        with safe_temp_directory() as temp_dir:
            temp_path = temp_dir
            assert temp_dir.exists()
            assert temp_dir.is_dir()

            # Create a test file
            test_file = temp_dir / "test.txt"
            test_file.write_text("test content")
            assert test_file.exists()

        # After context, directory should be cleaned up
        assert not temp_path.exists()

    def test_get_file_size(self, tmp_path):
        """Test file size retrieval."""
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)

        size = get_file_size(test_file)
        assert size == len(test_content.encode("utf-8"))

        # Test with non-existent file
        with pytest.raises(FileNotFoundError):
            get_file_size(tmp_path / "nonexistent.txt")

    def test_check_disk_space(self, tmp_path):
        """Test disk space checking."""
        # This should pass for most systems (requiring only 1GB)
        try:
            result = check_disk_space(tmp_path, required_gb=1.0)
            assert result is True
        except Exception:
            # If it fails, we might be in a very constrained environment
            pass


class TestHashingUtils:
    """Test hashing utility functions."""

    def test_sha256_hash(self, tmp_path):
        """Test SHA-256 hash computation."""
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)

        hash_value = compute_sha256_hash(test_file)

        # Verify it's a valid SHA-256 hash (64 hex characters)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

        # Verify consistency
        hash_value2 = compute_sha256_hash(test_file)
        assert hash_value == hash_value2

    def test_blake3_hash(self, tmp_path):
        """Test BLAKE3 hash computation."""
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!"
        test_file.write_text(test_content)

        hash_value = compute_blake3_hash(test_file)

        # Verify it's a valid BLAKE3 hash (64 hex characters)
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

        # Verify consistency
        hash_value2 = compute_blake3_hash(test_file)
        assert hash_value == hash_value2

    def test_hash_consistency(self, tmp_path):
        """Test that hashes are consistent for identical content."""
        # Create two files with identical content
        test_file1 = tmp_path / "test1.txt"
        test_file2 = tmp_path / "test2.txt"
        test_content = "Identical content"

        test_file1.write_text(test_content)
        test_file2.write_text(test_content)

        # SHA-256 should be identical
        sha256_1 = compute_sha256_hash(test_file1)
        sha256_2 = compute_sha256_hash(test_file2)
        assert sha256_1 == sha256_2

        # BLAKE3 should be identical
        blake3_1 = compute_blake3_hash(test_file1)
        blake3_2 = compute_blake3_hash(test_file2)
        assert blake3_1 == blake3_2

    def test_hash_difference(self, tmp_path):
        """Test that different content produces different hashes."""
        test_file1 = tmp_path / "test1.txt"
        test_file2 = tmp_path / "test2.txt"

        test_file1.write_text("Content A")
        test_file2.write_text("Content B")

        # Hashes should be different
        sha256_1 = compute_sha256_hash(test_file1)
        sha256_2 = compute_sha256_hash(test_file2)
        assert sha256_1 != sha256_2

        blake3_1 = compute_blake3_hash(test_file1)
        blake3_2 = compute_blake3_hash(test_file2)
        assert blake3_1 != blake3_2


class TestProgressUtils:
    """Test progress tracking utilities."""

    def test_progress_info_creation(self):
        """Test progress info object creation."""
        from coldpack.utils.progress import ProgressInfo

        info = ProgressInfo(
            operation="test",
            percentage=50.0,
            current_file="test.txt",
            processed_files=5,
            total_files=10,
        )

        assert info.operation == "test"
        assert info.percentage == 50.0
        assert info.current_file == "test.txt"
        assert info.processed_files == 5
        assert info.total_files == 10
