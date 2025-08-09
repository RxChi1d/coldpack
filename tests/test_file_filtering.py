# SPDX-FileCopyrightText: 2025 coldpack contributors
# SPDX-License-Identifier: MIT

"""Tests for system file filtering functionality."""

import platform
import shutil
import tempfile
from pathlib import Path

import pytest

from src.coldpack.utils.filesystem import (
    SYSTEM_FILE_PATTERNS,
    filter_files_for_archive,
    should_exclude_file,
)


class TestFileFiltering:
    """Test file filtering functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory with test files."""
        temp_dir = Path(tempfile.mkdtemp())

        # Create normal files
        (temp_dir / "normal_file.txt").write_text("content")
        (temp_dir / "document.pdf").write_text("pdf content")
        (temp_dir / "subdirectory").mkdir()
        (temp_dir / "subdirectory" / "nested_file.py").write_text("python code")

        # Create system files that should be excluded
        (temp_dir / ".DS_Store").write_text("macOS metadata")
        (temp_dir / "._resource_fork").write_text("macOS resource fork")
        (temp_dir / "Thumbs.db").write_text("Windows thumbnail")
        (temp_dir / "Desktop.ini").write_text("Windows desktop config")
        (temp_dir / "__pycache__").mkdir()
        (temp_dir / "__pycache__" / "module.pyc").write_text("python bytecode")
        (temp_dir / ".git").mkdir()
        (temp_dir / ".git" / "config").write_text("git config")

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_macos_system_files_excluded(self, temp_dir):
        """Test that macOS system files are excluded."""
        ds_store = temp_dir / ".DS_Store"
        resource_fork = temp_dir / "._resource_fork"

        assert should_exclude_file(ds_store, temp_dir) is True
        assert should_exclude_file(resource_fork, temp_dir) is True

    def test_windows_system_files_excluded(self, temp_dir):
        """Test that Windows system files are excluded."""
        thumbs = temp_dir / "Thumbs.db"
        desktop_ini = temp_dir / "Desktop.ini"

        assert should_exclude_file(thumbs, temp_dir) is True
        assert should_exclude_file(desktop_ini, temp_dir) is True

    def test_common_system_files_excluded(self, temp_dir):
        """Test that common system files are excluded."""
        pycache_file = temp_dir / "__pycache__" / "module.pyc"
        git_file = temp_dir / ".git" / "config"

        assert should_exclude_file(pycache_file, temp_dir) is True
        assert should_exclude_file(git_file, temp_dir) is True

    def test_normal_files_not_excluded(self, temp_dir):
        """Test that normal files are not excluded."""
        normal_file = temp_dir / "normal_file.txt"
        pdf_file = temp_dir / "document.pdf"
        nested_file = temp_dir / "subdirectory" / "nested_file.py"

        assert should_exclude_file(normal_file, temp_dir) is False
        assert should_exclude_file(pdf_file, temp_dir) is False
        assert should_exclude_file(nested_file, temp_dir) is False

    def test_filter_files_for_archive(self, temp_dir):
        """Test complete file filtering for archive."""
        filtered_files = filter_files_for_archive(temp_dir)

        # Convert to relative paths for easier checking
        rel_paths = [f.relative_to(temp_dir) for f in filtered_files]
        rel_paths_str = [str(p) for p in rel_paths]

        # Should include normal files
        assert "normal_file.txt" in rel_paths_str
        assert "document.pdf" in rel_paths_str
        assert str(Path("subdirectory") / "nested_file.py") in rel_paths_str

        # Should exclude system files
        assert ".DS_Store" not in rel_paths_str
        assert "._resource_fork" not in rel_paths_str
        assert "Thumbs.db" not in rel_paths_str
        assert "Desktop.ini" not in rel_paths_str
        assert str(Path("__pycache__") / "module.pyc") not in rel_paths_str
        assert str(Path(".git") / "config") not in rel_paths_str

    def test_pattern_matching_works(self):
        """Test that pattern matching works correctly."""
        # Test that wildcard patterns exist
        assert "._*" in SYSTEM_FILE_PATTERNS["macos"]

        # Verify common patterns exist
        common_patterns = SYSTEM_FILE_PATTERNS["common"]
        assert ".git" in common_patterns
        assert "__pycache__" in common_patterns
        assert "*.pyc" in common_patterns

    def test_empty_directory_handling(self):
        """Test handling of empty directories."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            filtered_files = filter_files_for_archive(temp_dir)
            assert filtered_files == []
        finally:
            shutil.rmtree(temp_dir)

    def test_nonexistent_directory_handling(self):
        """Test handling of nonexistent directories."""
        nonexistent = Path("/nonexistent/directory")
        with pytest.raises(ValueError):
            filter_files_for_archive(nonexistent)

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-specific test")
    def test_macos_specific_patterns(self):
        """Test macOS-specific file patterns on macOS."""
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create macOS-specific files
            (temp_dir / ".DS_Store").write_text("metadata")
            (temp_dir / ".fseventsd").mkdir()
            (temp_dir / ".fseventsd" / "fseventsd-uuid").write_text("events")
            (temp_dir / "normal_file.txt").write_text("content")

            filtered_files = filter_files_for_archive(temp_dir)
            rel_paths_str = [str(f.relative_to(temp_dir)) for f in filtered_files]

            assert "normal_file.txt" in rel_paths_str
            assert ".DS_Store" not in rel_paths_str
            assert str(Path(".fseventsd") / "fseventsd-uuid") not in rel_paths_str

        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__])
