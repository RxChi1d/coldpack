"""Tests for Windows filename handling utilities."""

from pathlib import Path
from unittest.mock import patch

from coldpack.utils.filesystem import (
    WINDOWS_INVALID_CHARS,
    WINDOWS_RESERVED_NAMES,
    check_windows_filename_conflicts,
    create_filename_mapping,
    is_windows_system,
    needs_windows_filename_handling,
    sanitize_windows_filename,
)


class TestSanitizeWindowsFilename:
    """Test Windows filename sanitization."""

    def test_valid_filename_unchanged(self):
        """Test that valid filenames are not changed."""
        filename = "normal_file.txt"
        result = sanitize_windows_filename(filename)
        assert result == filename

    def test_reserved_names_handled(self):
        """Test that reserved names are properly handled."""
        for reserved_name in WINDOWS_RESERVED_NAMES:
            result = sanitize_windows_filename(reserved_name)
            assert result != reserved_name
            assert result == f"{reserved_name}__file"

            # Test with extension
            result_with_ext = sanitize_windows_filename(f"{reserved_name}.txt")
            assert result_with_ext != f"{reserved_name}.txt"
            assert result_with_ext == f"{reserved_name}__file.txt"

    def test_invalid_characters_replaced(self):
        """Test that invalid characters are replaced."""
        for invalid_char in WINDOWS_INVALID_CHARS:
            filename = f"test{invalid_char}file.txt"
            result = sanitize_windows_filename(filename)
            assert invalid_char not in result
            assert result == "test_file.txt"

    def test_control_characters_replaced(self):
        """Test that control characters are replaced."""
        filename = f"test{chr(1)}file.txt"  # Control character
        result = sanitize_windows_filename(filename)
        assert chr(1) not in result
        assert result == "test_file.txt"

    def test_trailing_dots_and_spaces_removed(self):
        """Test that trailing dots and spaces are removed from name part."""
        filename = "test... .txt"
        result = sanitize_windows_filename(filename)
        assert result == "test.txt"

    def test_empty_filename_handled(self):
        """Test that empty filenames are handled."""
        result = sanitize_windows_filename("")
        assert result == "unnamed_file"

    def test_long_filename_truncated(self):
        """Test that long filenames are truncated."""
        long_name = "a" * 300
        result = sanitize_windows_filename(long_name + ".txt")
        assert len(result) <= 255

    def test_path_separators_replaced(self):
        """Test that path separators are replaced."""
        filename = "folder/file.txt"
        result = sanitize_windows_filename(filename)
        assert "/" not in result
        assert result == "folder_file.txt"

    def test_custom_replacement_character(self):
        """Test using custom replacement character."""
        filename = "test<file>.txt"
        result = sanitize_windows_filename(filename, replacement_char="-")
        assert result == "test-file-.txt"


class TestCheckWindowsFilenameConflicts:
    """Test Windows filename conflict detection."""

    def test_no_conflicts(self):
        """Test files with no conflicts."""
        file_list = ["normal_file.txt", "another_file.pdf", "folder/file.doc"]
        conflicts = check_windows_filename_conflicts(file_list)

        assert not any(conflicts.values())

    def test_reserved_names_detected(self):
        """Test that reserved names are detected."""
        file_list = ["CON.txt", "PRN", "folder/AUX.pdf"]
        conflicts = check_windows_filename_conflicts(file_list)

        assert len(conflicts["reserved_names"]) == 3
        assert "CON.txt" in conflicts["reserved_names"]
        assert "PRN" in conflicts["reserved_names"]
        assert "folder/AUX.pdf" in conflicts["reserved_names"]

    def test_invalid_chars_detected(self):
        """Test that invalid characters are detected."""
        file_list = ["test<file>.txt", "another|file.pdf", 'file"with"quotes.doc']
        conflicts = check_windows_filename_conflicts(file_list)

        assert len(conflicts["invalid_chars"]) == 3

    def test_case_conflicts_detected(self):
        """Test that case sensitivity conflicts are detected."""
        file_list = ["File.txt", "file.txt", "FILE.TXT"]
        conflicts = check_windows_filename_conflicts(file_list)

        assert len(conflicts["case_conflicts"]) == 3

    def test_length_conflicts_detected(self):
        """Test that length conflicts are detected."""
        long_filename = "a" * 300 + ".txt"
        file_list = ["normal.txt", long_filename]
        conflicts = check_windows_filename_conflicts(file_list)

        assert len(conflicts["length_conflicts"]) == 1
        assert long_filename in conflicts["length_conflicts"]


class TestCreateFilenameMapping:
    """Test filename mapping creation."""

    def test_no_conflicts_no_mapping(self):
        """Test that files without conflicts are not changed."""
        file_list = ["normal_file.txt", "another_file.pdf"]
        mapping = create_filename_mapping(file_list)

        for original_path in file_list:
            assert mapping[original_path] == original_path

    def test_reserved_names_mapped(self):
        """Test that reserved names are properly mapped."""
        file_list = ["CON.txt", "PRN.pdf"]
        mapping = create_filename_mapping(file_list)

        assert mapping["CON.txt"] != "CON.txt"
        assert mapping["PRN.pdf"] != "PRN.pdf"
        # Verify that the original reserved name is modified (not exact match)
        assert mapping["CON.txt"].upper() != "CON.TXT"
        assert mapping["PRN.pdf"].upper() != "PRN.PDF"

    def test_invalid_chars_mapped(self):
        """Test that invalid characters are mapped."""
        file_list = ["test<file>.txt", "another|file.pdf"]
        mapping = create_filename_mapping(file_list)

        for original_path in file_list:
            sanitized = mapping[original_path]
            assert not any(char in sanitized for char in WINDOWS_INVALID_CHARS)

    def test_duplicate_handling(self):
        """Test that duplicate sanitized names get unique suffixes."""
        file_list = ["test<file>.txt", "test>file<.txt", "test|file|.txt"]
        mapping = create_filename_mapping(file_list)

        # All should be sanitized to unique names
        sanitized_names = list(mapping.values())
        assert len(set(sanitized_names)) == len(sanitized_names)  # All unique

    def test_path_structure_preserved(self):
        """Test that directory structure is preserved in mapping."""
        file_list = ["folder/CON.txt", "another/folder/PRN.pdf"]
        mapping = create_filename_mapping(file_list)

        # On Windows, paths use backslashes, so we need to normalize for comparison
        mapped_path_1 = mapping["folder/CON.txt"].replace("\\", "/")
        mapped_path_2 = mapping["another/folder/PRN.pdf"].replace("\\", "/")

        assert mapped_path_1.startswith("folder/")
        assert mapped_path_2.startswith("another/folder/")


class TestWindowsSystemDetection:
    """Test Windows system detection and handling logic."""

    @patch("coldpack.utils.filesystem.platform.system")
    def test_is_windows_system_true(self, mock_system):
        """Test Windows system detection returns True on Windows."""
        mock_system.return_value = "Windows"
        assert is_windows_system() is True

    @patch("coldpack.utils.filesystem.platform.system")
    def test_is_windows_system_false(self, mock_system):
        """Test Windows system detection returns False on non-Windows."""
        mock_system.return_value = "Linux"
        assert is_windows_system() is False

    @patch("coldpack.utils.filesystem.is_windows_system")
    def test_needs_windows_filename_handling_non_windows(self, mock_is_windows):
        """Test that non-Windows systems don't need filename handling."""
        mock_is_windows.return_value = False
        file_list = ["CON.txt", "test<file>.txt"]

        assert needs_windows_filename_handling(file_list) is False

    @patch("coldpack.utils.filesystem.is_windows_system")
    def test_needs_windows_filename_handling_windows_with_conflicts(
        self, mock_is_windows
    ):
        """Test that Windows systems with conflicts need handling."""
        mock_is_windows.return_value = True
        file_list = ["CON.txt", "test<file>.txt"]

        assert needs_windows_filename_handling(file_list) is True

    @patch("coldpack.utils.filesystem.is_windows_system")
    def test_needs_windows_filename_handling_windows_no_conflicts(
        self, mock_is_windows
    ):
        """Test that Windows systems without conflicts don't need handling."""
        mock_is_windows.return_value = True
        file_list = ["normal_file.txt", "another_file.pdf"]

        assert needs_windows_filename_handling(file_list) is False


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""

    def test_mixed_conflicts_scenario(self):
        """Test a complex scenario with multiple types of conflicts."""
        file_list = [
            "CON.txt",  # Reserved name
            "test<file>.txt",  # Invalid chars
            "File.txt",  # Case conflict part 1
            "file.txt",  # Case conflict part 2
            "a" * 300 + ".txt",  # Length conflict
            "normal_file.pdf",  # No conflicts
        ]

        # Check conflicts
        conflicts = check_windows_filename_conflicts(file_list)
        assert conflicts["reserved_names"]
        assert conflicts["invalid_chars"]
        assert conflicts["case_conflicts"]
        assert conflicts["length_conflicts"]

        # Create mapping
        mapping = create_filename_mapping(file_list)

        # Verify all files are mapped
        assert len(mapping) == len(file_list)

        # Verify all mapped names are unique
        mapped_names = list(mapping.values())
        assert len(set(mapped_names)) == len(mapped_names)

        # Verify normal file is unchanged
        assert mapping["normal_file.pdf"] == "normal_file.pdf"

    def test_archive_extraction_scenario(self):
        """Test scenario simulating archive extraction with conflicts."""
        # Simulate file list from an archive with Windows conflicts
        archive_files = [
            "project/src/CON.java",  # Reserved name
            "project/docs/file<1>.txt",  # Invalid chars
            "project/README.md",  # Normal file
            "project/test/Test.java",  # Case conflict part 1
            "project/test/test.java",  # Case conflict part 2
        ]

        # This would be called during extraction on Windows
        mapping = create_filename_mapping(archive_files)

        # Verify structure
        for original_path in archive_files:
            mapped_path = mapping[original_path]

            # Directory structure should be preserved
            # Normalize path separators for cross-platform comparison
            original_parent = str(Path(original_path).parent).replace("\\", "/")
            mapped_parent = str(Path(mapped_path).parent).replace("\\", "/")

            if original_parent != ".":
                assert mapped_parent == original_parent
