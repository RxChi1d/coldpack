"""Tests for coldpack archive verification functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coldpack.core.verifier import (
    ArchiveVerifier,
    VerificationError,
    VerificationResult,
)


class TestVerificationResult:
    """Test VerificationResult class."""

    def test_verification_result_initialization(self):
        """Test VerificationResult initialization."""
        result = VerificationResult(
            layer="test_layer",
            success=True,
            message="Test message",
            details={"key": "value"},
        )

        assert result.layer == "test_layer"
        assert result.success is True
        assert result.message == "Test message"
        assert result.details == {"key": "value"}
        assert result.timestamp is None

    def test_verification_result_defaults(self):
        """Test VerificationResult with default values."""
        result = VerificationResult(layer="test", success=False)

        assert result.layer == "test"
        assert result.success is False
        assert result.message == ""
        assert result.details == {}

    def test_verification_result_str_success(self):
        """Test string representation for successful result."""
        result = VerificationResult(
            layer="hash_verification", success=True, message="Hash matches"
        )

        str_repr = str(result)
        assert str_repr == "[hash_verification] PASS: Hash matches"

    def test_verification_result_str_failure(self):
        """Test string representation for failed result."""
        result = VerificationResult(
            layer="integrity_check", success=False, message="Archive corrupted"
        )

        str_repr = str(result)
        assert str_repr == "[integrity_check] FAIL: Archive corrupted"


class TestArchiveVerifier:
    """Test ArchiveVerifier class."""

    @pytest.fixture
    def verifier(self):
        """Create an ArchiveVerifier instance."""
        return ArchiveVerifier()

    @pytest.fixture
    def temp_archive(self):
        """Create a temporary archive file."""
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_file:
            tmp_file.write(b"dummy archive content")
            archive_path = Path(tmp_file.name)

        yield archive_path

        # Cleanup
        if archive_path.exists():
            archive_path.unlink()

    def test_verifier_initialization(self, verifier):
        """Test ArchiveVerifier initialization."""
        assert verifier.hash_verifier is not None
        assert verifier.par2_manager is None

    def test_verify_complete_nonexistent_archive(self, verifier):
        """Test verify_complete with non-existent archive."""
        nonexistent_path = Path("/nonexistent/archive.7z")

        with pytest.raises(FileNotFoundError, match="Archive not found"):
            verifier.verify_complete(nonexistent_path)

    @patch("coldpack.core.verifier.ArchiveVerifier.verify_7z_integrity")
    @patch("coldpack.core.verifier.ArchiveVerifier.verify_hash_files")
    @patch("coldpack.core.verifier.ArchiveVerifier.verify_par2_recovery")
    def test_verify_complete_basic(
        self, mock_par2, mock_hash, mock_7z, verifier, temp_archive
    ):
        """Test basic complete verification."""
        # Mock individual verification methods
        mock_7z.return_value = VerificationResult("7z_integrity", True, "7z OK")
        mock_hash.return_value = [
            VerificationResult("sha256", True, "SHA256 OK"),
            VerificationResult("blake3", True, "BLAKE3 OK"),
        ]
        mock_par2.return_value = VerificationResult("par2_recovery", True, "PAR2 OK")

        # Create dummy hash files
        with tempfile.TemporaryDirectory() as temp_dir:
            hash_files = {
                "sha256": Path(temp_dir) / "test.sha256",
                "blake3": Path(temp_dir) / "test.blake3",
            }
            for hash_file in hash_files.values():
                hash_file.write_text("dummy_hash_content")

            # Create dummy PAR2 file
            par2_file = Path(temp_dir) / "test.par2"
            par2_file.write_text("dummy par2 content")

            results = verifier.verify_complete(
                temp_archive, hash_files=hash_files, par2_file=par2_file
            )

            # Should have results from all layers
            assert len(results) >= 4  # 7z + 2 hash + par2

            # Verify all individual methods were called
            mock_7z.assert_called_once_with(temp_archive)
            mock_hash.assert_called_once()
            mock_par2.assert_called_once()

    def test_verify_7z_integrity_nonexistent_file(self, verifier):
        """Test 7z integrity verification with non-existent file."""
        nonexistent_path = Path("/nonexistent/archive.7z")

        result = verifier.verify_7z_integrity(nonexistent_path)

        assert result.layer == "7z_integrity"
        assert result.success is False
        assert "not found" in result.message.lower()

    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_7z_integrity_success(self, mock_validate, verifier, temp_archive):
        """Test successful 7z integrity verification."""
        mock_validate.return_value = True

        result = verifier.verify_7z_integrity(temp_archive)

        assert result.layer == "7z_integrity"
        assert result.success is True
        assert "integrity verified" in result.message.lower()
        mock_validate.assert_called_once_with(str(temp_archive))

    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_7z_integrity_failure(self, mock_validate, verifier, temp_archive):
        """Test failed 7z integrity verification."""
        mock_validate.return_value = False

        result = verifier.verify_7z_integrity(temp_archive)

        assert result.layer == "7z_integrity"
        assert result.success is False
        assert "failed" in result.message.lower()

    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_7z_integrity_exception(self, mock_validate, verifier, temp_archive):
        """Test 7z integrity verification with exception."""
        mock_validate.side_effect = Exception("Validation error")

        result = verifier.verify_7z_integrity(temp_archive)

        assert result.layer == "7z_integrity"
        assert result.success is False
        assert "error" in result.message.lower()

    def test_verify_hash_files_no_files(self, verifier, temp_archive):
        """Test hash verification with no hash files."""
        results = verifier.verify_hash_files(temp_archive, {})

        # Should return empty list
        assert len(results) == 0

    @patch("coldpack.core.verifier.HashVerifier")
    def test_verify_hash_files_success(
        self, mock_hash_verifier_class, verifier, temp_archive
    ):
        """Test successful hash file verification."""
        # Mock HashVerifier instance
        mock_hash_verifier = MagicMock()
        mock_hash_verifier_class.return_value = mock_hash_verifier
        mock_hash_verifier.verify_file_hash.return_value = True

        # Create verifier with mocked hash_verifier
        verifier.hash_verifier = mock_hash_verifier

        with tempfile.TemporaryDirectory() as temp_dir:
            hash_files = {"sha256": Path(temp_dir) / "test.sha256"}
            hash_files["sha256"].write_text("dummy_hash")

            results = verifier.verify_hash_files(temp_archive, hash_files)

            assert len(results) == 1
            assert results[0].layer == "sha256"
            assert results[0].success is True

    @patch("coldpack.core.verifier.HashVerifier")
    def test_verify_hash_files_failure(
        self, mock_hash_verifier_class, verifier, temp_archive
    ):
        """Test failed hash file verification."""
        # Mock HashVerifier instance
        mock_hash_verifier = MagicMock()
        mock_hash_verifier_class.return_value = mock_hash_verifier
        mock_hash_verifier.verify_file_hash.return_value = False

        # Create verifier with mocked hash_verifier
        verifier.hash_verifier = mock_hash_verifier

        with tempfile.TemporaryDirectory() as temp_dir:
            hash_files = {"blake3": Path(temp_dir) / "test.blake3"}
            hash_files["blake3"].write_text("dummy_hash")

            results = verifier.verify_hash_files(temp_archive, hash_files)

            assert len(results) == 1
            assert results[0].layer == "blake3"
            assert results[0].success is False

    def test_verify_par2_recovery_no_file(self, verifier, temp_archive):
        """Test PAR2 verification with no PAR2 file."""
        result = verifier.verify_par2_recovery(temp_archive, None)

        assert result.layer == "par2_recovery"
        assert result.success is False
        assert "not available" in result.message.lower()

    def test_verify_par2_recovery_nonexistent_file(self, verifier, temp_archive):
        """Test PAR2 verification with non-existent PAR2 file."""
        nonexistent_par2 = Path("/nonexistent/file.par2")

        result = verifier.verify_par2_recovery(temp_archive, nonexistent_par2)

        assert result.layer == "par2_recovery"
        assert result.success is False
        assert "not found" in result.message.lower()

    @patch("coldpack.utils.par2.PAR2Manager")
    def test_verify_par2_recovery_success(
        self, mock_par2_manager_class, verifier, temp_archive
    ):
        """Test successful PAR2 recovery verification."""
        # Mock PAR2Manager
        mock_par2_manager = MagicMock()
        mock_par2_manager_class.return_value = mock_par2_manager
        mock_par2_manager.verify_recovery_files.return_value = True

        with tempfile.NamedTemporaryFile(suffix=".par2", delete=False) as par2_file:
            par2_path = Path(par2_file.name)
            par2_file.write(b"dummy par2 content")

        try:
            result = verifier.verify_par2_recovery(temp_archive, par2_path)

            assert result.layer == "par2_recovery"
            assert result.success is True
            assert "passed" in result.message.lower()
        finally:
            par2_path.unlink()

    @patch("coldpack.utils.par2.PAR2Manager")
    def test_verify_par2_recovery_failure(
        self, mock_par2_manager_class, verifier, temp_archive
    ):
        """Test failed PAR2 recovery verification."""
        # Mock PAR2Manager
        mock_par2_manager = MagicMock()
        mock_par2_manager_class.return_value = mock_par2_manager
        mock_par2_manager.verify_recovery_files.return_value = False

        with tempfile.NamedTemporaryFile(suffix=".par2", delete=False) as par2_file:
            par2_path = Path(par2_file.name)
            par2_file.write(b"dummy par2 content")

        try:
            result = verifier.verify_par2_recovery(temp_archive, par2_path)

            assert result.layer == "par2_recovery"
            assert result.success is False
            assert "failed" in result.message.lower()
        finally:
            par2_path.unlink()

    def test_get_verification_summary_all_pass(self, verifier):
        """Test verification summary with all passing results."""
        results = [
            VerificationResult("7z_integrity", True, "OK"),
            VerificationResult("sha256", True, "OK"),
            VerificationResult("blake3", True, "OK"),
            VerificationResult("par2_recovery", True, "OK"),
        ]

        summary = verifier.get_verification_summary(results)

        assert summary["total_layers"] == 4
        assert summary["passed_layers"] == 4
        assert summary["failed_layers"] == 0
        assert summary["overall_success"] is True

    def test_get_verification_summary_some_fail(self, verifier):
        """Test verification summary with some failing results."""
        results = [
            VerificationResult("7z_integrity", True, "OK"),
            VerificationResult("sha256", False, "Failed"),
            VerificationResult("blake3", True, "OK"),
            VerificationResult("par2_recovery", False, "Failed"),
        ]

        summary = verifier.get_verification_summary(results)

        assert summary["total_layers"] == 4
        assert summary["passed_layers"] == 2
        assert summary["failed_layers"] == 2
        assert summary["overall_success"] is False

    def test_verify_quick_nonexistent_archive(self, verifier):
        """Test quick verification with non-existent archive."""
        nonexistent_path = Path("/nonexistent/archive.7z")

        result = verifier.verify_quick(nonexistent_path)
        assert result is False

    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_quick_success(self, mock_validate, verifier, temp_archive):
        """Test successful quick verification."""
        mock_validate.return_value = True

        result = verifier.verify_quick(temp_archive)

        assert result is True
        mock_validate.assert_called_once_with(str(temp_archive))

    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_quick_failure(self, mock_validate, verifier, temp_archive):
        """Test failed quick verification."""
        mock_validate.return_value = False

        result = verifier.verify_quick(temp_archive)

        assert result is False

    @patch("coldpack.core.verifier.ArchiveVerifier._discover_hash_files")
    @patch("coldpack.core.verifier.ArchiveVerifier._discover_par2_file")
    @patch("coldpack.core.verifier.ArchiveVerifier._verify_complete_with_skip")
    def test_verify_auto(
        self,
        mock_verify_complete,
        mock_discover_par2,
        mock_discover_hash,
        verifier,
        temp_archive,
    ):
        """Test automatic verification with discovery."""
        # Mock discovery methods
        mock_discover_hash.return_value = {
            "sha256": Path("test.sha256"),
            "blake3": Path("test.blake3"),
        }
        mock_discover_par2.return_value = Path("test.par2")

        # Mock complete verification
        mock_verify_complete.return_value = [
            VerificationResult("7z_integrity", True, "OK")
        ]

        verifier.verify_auto(temp_archive)

        # Should call discovery methods
        mock_discover_hash.assert_called_once()
        mock_discover_par2.assert_called_once()

        # Should call complete verification with discovered files
        mock_verify_complete.assert_called_once()
        call_args = mock_verify_complete.call_args
        # Check that hash_files and par2_file were passed (can be positional or keyword args)
        if len(call_args[0]) > 1:  # positional args
            hash_files_arg = (
                call_args[0][1]
                if len(call_args[0]) > 1
                else call_args[1].get("hash_files")
            )
            par2_file_arg = (
                call_args[0][2]
                if len(call_args[0]) > 2
                else call_args[1].get("par2_file")
            )
        else:  # keyword args
            hash_files_arg = call_args[1].get("hash_files")
            par2_file_arg = call_args[1].get("par2_file")

        assert hash_files_arg is not None
        assert par2_file_arg is not None

    def test_discover_hash_files_no_files(self, verifier, temp_archive):
        """Test hash file discovery with no hash files."""
        hash_files = verifier._discover_hash_files(temp_archive, set())

        # Should return empty dict when no hash files exist
        assert hash_files == {}

    def test_discover_hash_files_with_files(self, verifier):
        """Test hash file discovery with existing hash files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "test.7z"
            archive_path.write_text("dummy archive")

            # Create hash files
            sha256_file = Path(temp_dir) / "test.sha256"
            blake3_file = Path(temp_dir) / "test.blake3"
            sha256_file.write_text("dummy hash")
            blake3_file.write_text("dummy hash")

            hash_files = verifier._discover_hash_files(archive_path, set())

            assert "sha256" in hash_files
            assert "blake3" in hash_files
            assert hash_files["sha256"] == sha256_file
            assert hash_files["blake3"] == blake3_file

    def test_discover_par2_file_no_file(self, verifier, temp_archive):
        """Test PAR2 file discovery with no PAR2 file."""
        par2_file = verifier._discover_par2_file(temp_archive, set())

        # Should return None when no PAR2 file exists
        assert par2_file is None

    def test_discover_par2_file_with_file(self, verifier):
        """Test PAR2 file discovery with existing PAR2 file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "test.7z"
            archive_path.write_text("dummy archive")

            # Create PAR2 file
            par2_file = Path(temp_dir) / "test.par2"
            par2_file.write_text("dummy par2 content")

            discovered_par2 = verifier._discover_par2_file(archive_path, set())

            assert discovered_par2 == par2_file

    def test_detect_archive_format(self, verifier):
        """Test archive format detection."""
        # Test various formats
        assert verifier._detect_archive_format(Path("test.7z")) == "7z"
        assert verifier._detect_archive_format(Path("test.zip")) == "zip"
        assert verifier._detect_archive_format(Path("test.tar.gz")) == "tar"
        assert verifier._detect_archive_format(Path("test.unknown")) == "unknown"


class TestVerificationError:
    """Test VerificationError exception."""

    def test_verification_error_creation(self):
        """Test VerificationError can be created and raised."""
        with pytest.raises(VerificationError, match="Test error"):
            raise VerificationError("Test error")

    def test_verification_error_inheritance(self):
        """Test VerificationError inherits from Exception."""
        error = VerificationError("Test")
        assert isinstance(error, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
