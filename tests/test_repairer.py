"""Tests for coldpack archive repair functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coldpack.core.repairer import (
    ArchiveRepairer,
    RepairError,
    RepairResult,
)


class TestRepairResult:
    """Test RepairResult class."""

    def test_repair_result_initialization(self):
        """Test RepairResult initialization."""
        repaired_files = ["file1.txt", "file2.txt"]

        result = RepairResult(
            success=True,
            message="Repair completed successfully",
            repaired_files=repaired_files,
            error_details="No errors",
        )

        assert result.success is True
        assert result.message == "Repair completed successfully"
        assert result.repaired_files == repaired_files
        assert result.error_details == "No errors"

    def test_repair_result_defaults(self):
        """Test RepairResult with default values."""
        result = RepairResult(success=False)

        assert result.success is False
        assert result.message == ""
        assert result.repaired_files == []
        assert result.error_details is None

    def test_repair_result_str_success(self):
        """Test string representation for successful result."""
        result = RepairResult(success=True, message="Archive repaired")

        str_repr = str(result)
        assert str_repr == "Repair SUCCESS: Archive repaired"

    def test_repair_result_str_failure(self):
        """Test string representation for failed result."""
        result = RepairResult(success=False, message="Archive corruption beyond repair")

        str_repr = str(result)
        assert str_repr == "Repair FAILED: Archive corruption beyond repair"


class TestArchiveRepairer:
    """Test ArchiveRepairer class."""

    @pytest.fixture
    def temp_par2_file(self):
        """Create a temporary PAR2 file."""
        with tempfile.NamedTemporaryFile(suffix=".par2", delete=False) as tmp_file:
            tmp_file.write(b"dummy par2 content")
            par2_path = Path(tmp_file.name)

        yield par2_path

        # Cleanup
        if par2_path.exists():
            par2_path.unlink()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repairer_initialization_success(self, mock_par2_manager):
        """Test successful ArchiveRepairer initialization."""
        mock_par2_manager.return_value = MagicMock()

        repairer = ArchiveRepairer(redundancy_percent=15)

        assert repairer.par2_manager is not None
        mock_par2_manager.assert_called_once_with(15)

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repairer_initialization_default_redundancy(self, mock_par2_manager):
        """Test ArchiveRepairer initialization with default redundancy."""
        mock_par2_manager.return_value = MagicMock()

        ArchiveRepairer()

        mock_par2_manager.assert_called_once_with(10)  # Default value

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repairer_initialization_par2_not_found(self, mock_par2_manager):
        """Test ArchiveRepairer initialization when PAR2 tools not found."""
        from coldpack.utils.par2 import PAR2NotFoundError

        mock_par2_manager.side_effect = PAR2NotFoundError("PAR2 not found")

        with pytest.raises(RepairError, match="PAR2 tools not available"):
            ArchiveRepairer()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repair_archive_nonexistent_par2_file(
        self, mock_par2_manager, temp_par2_file
    ):
        """Test repair_archive with non-existent PAR2 file."""
        mock_par2_manager.return_value = MagicMock()
        repairer = ArchiveRepairer()

        # Remove the temporary file
        temp_par2_file.unlink()

        with pytest.raises(FileNotFoundError, match="PAR2 file not found"):
            repairer.repair_archive(temp_par2_file)

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repair_archive_success(self, mock_par2_manager, temp_par2_file):
        """Test successful archive repair."""
        # Mock PAR2Manager
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance

        # Mock repair operation
        mock_par2_instance.repair_files.return_value = True

        # Mock verification methods
        repairer = ArchiveRepairer()

        with (
            patch.object(repairer, "_get_original_file_from_par2") as mock_get_original,
            patch.object(repairer, "_verify_before_repair") as mock_verify_before,
            patch.object(repairer, "_verify_after_repair") as mock_verify_after,
        ):
            # Create a dummy original file
            original_file = temp_par2_file.parent / "test.7z"
            original_file.write_bytes(b"dummy archive")
            mock_get_original.return_value = original_file

            # Mock verifications
            mock_verify_before.return_value = True  # Archive is corrupted
            mock_verify_after.return_value = True  # Archive is now valid

            result = repairer.repair_archive(temp_par2_file)

            assert isinstance(result, RepairResult)
            assert result.success is True
            assert "repaired successfully" in result.message.lower()

            # Verify methods were called
            mock_par2_instance.repair_files.assert_called_once()
            mock_verify_before.assert_called_once()
            mock_verify_after.assert_called_once()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repair_archive_par2_failure(self, mock_par2_manager, temp_par2_file):
        """Test archive repair when PAR2 repair fails."""
        # Mock PAR2Manager
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance

        # Mock repair operation to fail
        mock_par2_instance.repair_files.return_value = False

        repairer = ArchiveRepairer()

        with (
            patch.object(repairer, "_get_original_file_from_par2") as mock_get_original,
            patch.object(repairer, "_verify_before_repair") as mock_verify_before,
        ):
            # Create a dummy original file
            original_file = temp_par2_file.parent / "test.7z"
            original_file.write_bytes(b"dummy archive")
            mock_get_original.return_value = original_file

            # Mock verification - archive is corrupted
            mock_verify_before.return_value = True

            result = repairer.repair_archive(temp_par2_file)

            assert isinstance(result, RepairResult)
            assert result.success is False
            assert "repair failed" in result.message.lower()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repair_archive_no_corruption_detected(
        self, mock_par2_manager, temp_par2_file
    ):
        """Test repair_archive when no corruption is detected."""
        mock_par2_manager.return_value = MagicMock()
        repairer = ArchiveRepairer()

        with (
            patch.object(repairer, "_get_original_file_from_par2") as mock_get_original,
            patch.object(repairer, "_verify_before_repair") as mock_verify_before,
        ):
            # Create a dummy original file
            original_file = temp_par2_file.parent / "test.7z"
            original_file.write_bytes(b"dummy archive")
            mock_get_original.return_value = original_file

            # Mock verification - no corruption detected
            mock_verify_before.return_value = False

            result = repairer.repair_archive(temp_par2_file)

            assert isinstance(result, RepairResult)
            assert result.success is True
            assert "no corruption detected" in result.message.lower()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_repair_archive_exception_handling(self, mock_par2_manager, temp_par2_file):
        """Test repair_archive with exception during repair."""
        # Mock PAR2Manager
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance

        # Mock repair to raise exception
        mock_par2_instance.repair_files.side_effect = Exception("Repair failed")

        repairer = ArchiveRepairer()

        with (
            patch.object(repairer, "_get_original_file_from_par2") as mock_get_original,
            patch.object(repairer, "_verify_before_repair") as mock_verify_before,
        ):
            # Create a dummy original file
            original_file = temp_par2_file.parent / "test.7z"
            original_file.write_bytes(b"dummy archive")
            mock_get_original.return_value = original_file
            mock_verify_before.return_value = True

            result = repairer.repair_archive(temp_par2_file)

            assert isinstance(result, RepairResult)
            assert result.success is False
            assert "error during repair" in result.message.lower()
            assert result.error_details is not None

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_check_repair_capability_success(self, mock_par2_manager, temp_par2_file):
        """Test successful repair capability check."""
        # Mock PAR2Manager
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance
        mock_par2_instance.verify_recovery_data.return_value = True

        repairer = ArchiveRepairer()

        with patch.object(
            repairer, "_get_original_file_from_par2"
        ) as mock_get_original:
            # Create a dummy original file
            original_file = temp_par2_file.parent / "test.7z"
            original_file.write_bytes(b"dummy archive")
            mock_get_original.return_value = original_file

            capability = repairer.check_repair_capability(temp_par2_file)

            assert isinstance(capability, dict)
            assert "can_repair" in capability
            assert "par2_status" in capability
            assert "original_file_exists" in capability
            assert capability["can_repair"] is True

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_check_repair_capability_no_original_file(
        self, mock_par2_manager, temp_par2_file
    ):
        """Test repair capability check when original file doesn't exist."""
        mock_par2_manager.return_value = MagicMock()
        repairer = ArchiveRepairer()

        with patch.object(
            repairer, "_get_original_file_from_par2"
        ) as mock_get_original:
            # No original file found
            mock_get_original.return_value = None

            capability = repairer.check_repair_capability(temp_par2_file)

            assert capability["can_repair"] is False
            assert capability["original_file_exists"] is False

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_create_recovery_files_success(self, mock_par2_manager):
        """Test successful recovery file creation."""
        # Mock PAR2Manager
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance

        # Create temporary archive file
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_file:
            tmp_file.write(b"dummy archive content")
            archive_path = Path(tmp_file.name)

        try:
            expected_par2_files = [
                archive_path.parent / f"{archive_path.stem}.par2",
                archive_path.parent / f"{archive_path.stem}.vol000+01.par2",
            ]
            mock_par2_instance.create_recovery_files.return_value = expected_par2_files

            repairer = ArchiveRepairer()
            result_files = repairer.create_recovery_files(archive_path)

            assert result_files == expected_par2_files
            mock_par2_instance.create_recovery_files.assert_called_once_with(
                archive_path
            )
        finally:
            archive_path.unlink()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_create_recovery_files_failure(self, mock_par2_manager):
        """Test recovery file creation failure."""
        # Mock PAR2Manager to raise exception
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance
        mock_par2_instance.create_recovery_files.side_effect = Exception(
            "Creation failed"
        )

        # Create temporary archive file
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_file:
            tmp_file.write(b"dummy archive content")
            archive_path = Path(tmp_file.name)

        try:
            repairer = ArchiveRepairer()

            with pytest.raises(RepairError, match="Failed to create recovery files"):
                repairer.create_recovery_files(archive_path)
        finally:
            archive_path.unlink()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_verify_recovery_files_success(self, mock_par2_manager, temp_par2_file):
        """Test successful recovery file verification."""
        # Mock PAR2Manager
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance
        mock_par2_instance.verify_recovery_data.return_value = True

        repairer = ArchiveRepairer()
        result = repairer.verify_recovery_files(temp_par2_file)

        assert result is True
        mock_par2_instance.verify_recovery_data.assert_called_once_with(temp_par2_file)

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_verify_recovery_files_failure(self, mock_par2_manager, temp_par2_file):
        """Test recovery file verification failure."""
        # Mock PAR2Manager
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance
        mock_par2_instance.verify_recovery_data.return_value = False

        repairer = ArchiveRepairer()
        result = repairer.verify_recovery_files(temp_par2_file)

        assert result is False

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_verify_recovery_files_exception(self, mock_par2_manager, temp_par2_file):
        """Test recovery file verification with exception."""
        # Mock PAR2Manager to raise exception
        mock_par2_instance = MagicMock()
        mock_par2_manager.return_value = mock_par2_instance
        mock_par2_instance.verify_recovery_data.side_effect = Exception(
            "Verification failed"
        )

        repairer = ArchiveRepairer()
        result = repairer.verify_recovery_files(temp_par2_file)

        assert result is False

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_get_original_file_from_par2_found(self, mock_par2_manager, temp_par2_file):
        """Test getting original file from PAR2 when it exists."""
        mock_par2_manager.return_value = MagicMock()
        repairer = ArchiveRepairer()

        # Create the expected original file
        expected_original = temp_par2_file.parent / "test.7z"
        expected_original.write_bytes(b"dummy archive")

        # Mock the PAR2 file name to match
        temp_par2_file.unlink()
        par2_path = temp_par2_file.parent / "test.par2"
        par2_path.write_bytes(b"dummy par2")

        try:
            result = repairer._get_original_file_from_par2(par2_path)
            assert result == expected_original
        finally:
            expected_original.unlink()
            par2_path.unlink()

    @patch("coldpack.core.repairer.PAR2Manager")
    def test_get_original_file_from_par2_not_found(
        self, mock_par2_manager, temp_par2_file
    ):
        """Test getting original file from PAR2 when it doesn't exist."""
        mock_par2_manager.return_value = MagicMock()
        repairer = ArchiveRepairer()

        result = repairer._get_original_file_from_par2(temp_par2_file)
        assert result is None

    @patch("coldpack.core.repairer.PAR2Manager")
    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_before_repair_corrupted(self, mock_validate, mock_par2_manager):
        """Test verification before repair with corrupted archive."""
        mock_par2_manager.return_value = MagicMock()
        mock_validate.return_value = False  # Archive is corrupted

        repairer = ArchiveRepairer()

        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_file:
            tmp_file.write(b"corrupted archive")
            archive_path = Path(tmp_file.name)

        try:
            result = repairer._verify_before_repair(archive_path)
            assert result is True  # Corruption detected
            mock_validate.assert_called_once_with(str(archive_path))
        finally:
            archive_path.unlink()

    @patch("coldpack.core.repairer.PAR2Manager")
    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_before_repair_valid(self, mock_validate, mock_par2_manager):
        """Test verification before repair with valid archive."""
        mock_par2_manager.return_value = MagicMock()
        mock_validate.return_value = True  # Archive is valid

        repairer = ArchiveRepairer()

        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_file:
            tmp_file.write(b"valid archive")
            archive_path = Path(tmp_file.name)

        try:
            result = repairer._verify_before_repair(archive_path)
            assert result is False  # No corruption detected
        finally:
            archive_path.unlink()

    @patch("coldpack.core.repairer.PAR2Manager")
    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_after_repair_success(self, mock_validate, mock_par2_manager):
        """Test verification after repair shows archive is fixed."""
        mock_par2_manager.return_value = MagicMock()
        mock_validate.return_value = True  # Archive is now valid

        repairer = ArchiveRepairer()

        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_file:
            tmp_file.write(b"repaired archive")
            archive_path = Path(tmp_file.name)

        try:
            result = repairer._verify_after_repair(archive_path)
            assert result is True  # Archive is now valid
        finally:
            archive_path.unlink()


class TestRepairError:
    """Test RepairError exception."""

    def test_repair_error_creation(self):
        """Test RepairError can be created and raised."""
        with pytest.raises(RepairError, match="Test error"):
            raise RepairError("Test error")

    def test_repair_error_inheritance(self):
        """Test RepairError inherits from Exception."""
        error = RepairError("Test")
        assert isinstance(error, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
