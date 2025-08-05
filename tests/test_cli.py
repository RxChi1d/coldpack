"""Tests for coldpack CLI interface."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from coldpack.cli import app, get_global_options, setup_logging, version_callback
from coldpack.config.constants import ExitCodes


class TestCLIBasics:
    """Test basic CLI functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_version_callback(self):
        """Test version callback function."""
        with pytest.raises(typer.Exit):
            version_callback(True)

    def test_version_callback_false(self):
        """Test version callback with False value."""
        # Should not raise exception when value is False
        version_callback(False)

    def test_main_app_help(self, runner):
        """Test main app help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "coldpack" in result.stdout
        assert "Cross-platform cold storage CLI" in result.stdout

    def test_version_option(self, runner):
        """Test --version option."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "coldpack version" in result.stdout

    def test_verbose_and_quiet_conflict(self, runner):
        """Test that verbose and quiet cannot be used together."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = runner.invoke(app, ["--verbose", "--quiet", "create", temp_dir])
            assert result.exit_code == 1
            assert "cannot be used together" in result.stdout


class TestLoggingSetup:
    """Test logging configuration."""

    @patch("coldpack.cli.logger")
    def test_setup_logging_default(self, mock_logger):
        """Test default logging setup."""
        setup_logging(verbose=False, quiet=False)

        # Should remove default handler and add new one
        mock_logger.remove.assert_called_once()
        mock_logger.add.assert_called_once()

        # Check call arguments
        call_args = mock_logger.add.call_args
        assert call_args[1]["level"] == "INFO"

    @patch("coldpack.cli.logger")
    def test_setup_logging_verbose(self, mock_logger):
        """Test verbose logging setup."""
        setup_logging(verbose=True, quiet=False)

        call_args = mock_logger.add.call_args
        assert call_args[1]["level"] == "DEBUG"

    @patch("coldpack.cli.logger")
    def test_setup_logging_quiet(self, mock_logger):
        """Test quiet logging setup."""
        setup_logging(verbose=False, quiet=True)

        call_args = mock_logger.add.call_args
        assert call_args[1]["level"] == "WARNING"


class TestGlobalOptions:
    """Test global options handling."""

    def test_get_global_options_no_context(self):
        """Test getting options when context is None."""
        ctx = MagicMock()
        ctx.obj = None

        verbose, quiet = get_global_options(ctx)
        assert verbose is False
        assert quiet is False

    def test_get_global_options_with_context(self):
        """Test getting options from context."""
        ctx = MagicMock()
        ctx.obj = {"verbose": True, "quiet": False}

        verbose, quiet = get_global_options(ctx)
        assert verbose is True
        assert quiet is False

    def test_get_global_options_partial_context(self):
        """Test getting options with partial context."""
        ctx = MagicMock()
        ctx.obj = {"verbose": True}  # Missing quiet

        verbose, quiet = get_global_options(ctx)
        assert verbose is True
        assert quiet is False


class TestCreateCommand:
    """Test create command functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_source_dir(self):
        """Create temporary source directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "file1.txt").write_text("test content 1")
            (temp_path / "file2.txt").write_text("test content 2")

            # Create subdirectory
            subdir = temp_path / "subdir"
            subdir.mkdir()
            (subdir / "nested.txt").write_text("nested content")

            yield temp_path

    def test_create_help(self, runner):
        """Test create command help."""
        result = runner.invoke(app, ["create", "--help"])
        assert result.exit_code == 0
        assert "Create a cold storage 7z archive" in result.stdout

    def test_create_nonexistent_source(self, runner):
        """Test create with non-existent source."""
        result = runner.invoke(app, ["create", "/nonexistent/path"])
        assert result.exit_code == ExitCodes.FILE_NOT_FOUND
        assert "Source not found" in result.stdout

    def test_create_invalid_compression_level(self, runner, temp_source_dir):
        """Test create with invalid compression level."""
        result = runner.invoke(app, ["create", str(temp_source_dir), "--level", "10"])
        assert result.exit_code == ExitCodes.INVALID_FORMAT
        # Remove ANSI color codes for assertion
        clean_output = (
            result.stdout.replace("\x1b[31m", "")
            .replace("\x1b[0m", "")
            .replace("\x1b[1;31m", "")
        )
        assert "level must be between 0 and 9" in clean_output

    def test_create_invalid_dict_size(self, runner, temp_source_dir):
        """Test create with invalid dictionary size."""
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--dict", "invalid"]
        )
        assert result.exit_code == ExitCodes.INVALID_FORMAT
        assert "dict must be one of" in result.stdout

    def test_create_conflicting_verify_options(self, runner, temp_source_dir):
        """Test create with conflicting verification options."""
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--no-verify", "--no-verify-7z"]
        )
        assert result.exit_code == 1
        assert "cannot be used with individual --no-verify-*" in result.stdout

    def test_create_local_verbose_quiet_conflict(self, runner, temp_source_dir):
        """Test create with local verbose and quiet conflict."""
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--verbose", "--quiet"]
        )
        assert result.exit_code == 1
        assert "cannot be used together" in result.stdout

    @patch("coldpack.cli.ColdStorageArchiver")
    @patch("coldpack.cli.check_par2_availability")
    def test_create_success_basic(
        self, mock_par2_check, mock_archiver, runner, temp_source_dir
    ):
        """Test successful basic archive creation."""
        from coldpack.core.archiver import ArchiveResult

        # Mock PAR2 as available
        mock_par2_check.return_value = True

        # Mock archiver
        mock_archiver_instance = MagicMock()
        mock_archiver.return_value = mock_archiver_instance

        # Create a successful ArchiveResult
        success_result = ArchiveResult(
            success=True, message="Archive created successfully", created_files=[]
        )
        mock_archiver_instance.create_archive.return_value = success_result

        with tempfile.TemporaryDirectory() as output_dir:
            result = runner.invoke(
                app,
                [
                    "create",
                    str(temp_source_dir),
                    "--output-dir",
                    output_dir,
                    "--name",
                    "test_archive",
                ],
            )

            # Should succeed (exit code 0)
            assert result.exit_code == 0

            # Verify archiver was called
            mock_archiver.assert_called_once()
            mock_archiver_instance.create_archive.assert_called_once()

    @patch("coldpack.cli.check_par2_availability")
    def test_create_par2_unavailable_warning(
        self, mock_par2_check, runner, temp_source_dir
    ):
        """Test create command when PAR2 is unavailable."""
        from coldpack.core.archiver import ArchiveResult

        # Mock PAR2 as unavailable
        mock_par2_check.return_value = False

        with patch("coldpack.cli.ColdStorageArchiver") as mock_archiver:
            mock_archiver_instance = MagicMock()
            mock_archiver.return_value = mock_archiver_instance

            # Create a successful ArchiveResult
            success_result = ArchiveResult(
                success=True, message="Archive created successfully", created_files=[]
            )
            mock_archiver_instance.create_archive.return_value = success_result

            with tempfile.TemporaryDirectory() as output_dir:
                result = runner.invoke(
                    app, ["create", str(temp_source_dir), "--output-dir", output_dir]
                )

                # Should still succeed but with warning
                assert result.exit_code == 0
                assert "PAR2 tools not found" in result.stdout


class TestExtractCommand:
    """Test extract command functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_extract_help(self, runner):
        """Test extract command help."""
        result = runner.invoke(app, ["extract", "--help"])
        assert result.exit_code == 0
        assert "Extract" in result.stdout

    def test_extract_nonexistent_archive(self, runner):
        """Test extract with non-existent archive."""
        result = runner.invoke(app, ["extract", "/nonexistent/archive.7z"])
        assert result.exit_code == ExitCodes.FILE_NOT_FOUND
        assert "Archive not found" in result.stdout

    @patch("coldpack.cli.MultiFormatExtractor")
    def test_extract_success(self, mock_extractor, runner):
        """Test successful extraction."""
        # Create temporary archive file
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_archive:
            archive_path = tmp_archive.name
            tmp_archive.write(b"dummy archive content")

        try:
            # Mock extractor
            mock_extractor_instance = MagicMock()
            mock_extractor.return_value = mock_extractor_instance

            with tempfile.TemporaryDirectory() as output_dir:
                result = runner.invoke(
                    app, ["extract", archive_path, "--output-dir", output_dir]
                )

                # Should succeed
                assert result.exit_code == 0
                mock_extractor_instance.extract.assert_called_once()
        finally:
            # Cleanup
            os.unlink(archive_path)


class TestListCommand:
    """Test list command functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_list_help(self, runner):
        """Test list command help."""
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
        assert "List" in result.stdout

    def test_list_nonexistent_archive(self, runner):
        """Test list with non-existent archive."""
        result = runner.invoke(app, ["list", "/nonexistent/archive.7z"])
        assert result.exit_code == ExitCodes.FILE_NOT_FOUND
        assert "Archive not found" in result.stdout

    @patch("coldpack.cli.ArchiveLister")
    def test_list_success(self, mock_lister, runner):
        """Test successful archive listing."""
        # Create temporary archive file
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_archive:
            archive_path = tmp_archive.name
            tmp_archive.write(b"dummy archive content")

        try:
            # Mock lister
            mock_lister_instance = MagicMock()
            mock_lister.return_value = mock_lister_instance

            # Create complete mock result with all required fields
            mock_lister_instance.list_archive.return_value = {
                "archive_path": archive_path,
                "format": ".7z",
                "total_files": 2,
                "total_directories": 1,
                "total_entries": 3,
                "total_size": 1024,
                "total_compressed_size": 512,
                "compression_ratio": 50.0,
                "showing_range": "All 3 entries",
                "has_more": False,
                "files": [],
            }

            result = runner.invoke(app, ["list", archive_path])

            # Should succeed
            assert result.exit_code == 0
            mock_lister_instance.list_archive.assert_called_once()
        finally:
            # Cleanup
            os.unlink(archive_path)


class TestVerifyCommand:
    """Test verify command functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_verify_help(self, runner):
        """Test verify command help."""
        result = runner.invoke(app, ["verify", "--help"])
        assert result.exit_code == 0
        assert "Verify" in result.stdout

    def test_verify_nonexistent_archive(self, runner):
        """Test verify with non-existent archive."""
        result = runner.invoke(app, ["verify", "/nonexistent/archive.7z"])
        assert result.exit_code == ExitCodes.FILE_NOT_FOUND
        assert "Archive not found" in result.stdout

    @patch("coldpack.cli.ArchiveVerifier")
    def test_verify_success(self, mock_verifier, runner):
        """Test successful verification."""
        # Create temporary archive file
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_archive:
            archive_path = tmp_archive.name
            tmp_archive.write(b"dummy archive content")

        try:
            # Mock verifier
            mock_verifier_instance = MagicMock()
            mock_verifier.return_value = mock_verifier_instance

            # Mock successful verification results
            from coldpack.core.verifier import VerificationResult

            successful_result = VerificationResult(
                layer="7z_integrity", success=True, message="Verification passed"
            )
            mock_verifier_instance.verify_auto.return_value = [successful_result]

            result = runner.invoke(app, ["verify", archive_path])

            # Should succeed
            assert result.exit_code == 0
            mock_verifier_instance.verify_auto.assert_called_once()
        finally:
            # Cleanup
            os.unlink(archive_path)


class TestRepairCommand:
    """Test repair command functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_repair_help(self, runner):
        """Test repair command help."""
        result = runner.invoke(app, ["repair", "--help"])
        assert result.exit_code == 0
        assert "Repair" in result.stdout

    def test_repair_nonexistent_archive(self, runner):
        """Test repair with non-existent archive."""
        result = runner.invoke(app, ["repair", "/nonexistent/archive.7z"])
        assert result.exit_code == ExitCodes.FILE_NOT_FOUND
        # Remove ANSI color codes for assertion
        clean_output = result.stdout.replace("\x1b[31m", "").replace("\x1b[0m", "")
        assert "File not found" in clean_output

    @patch("coldpack.cli.ArchiveRepairer")
    def test_repair_success(self, mock_repairer, runner):
        """Test successful repair."""
        # Create temporary PAR2 file
        with tempfile.NamedTemporaryFile(suffix=".par2", delete=False) as tmp_par2:
            par2_path = tmp_par2.name
            tmp_par2.write(b"dummy par2 content")

        try:
            # Mock repairer
            mock_repairer_instance = MagicMock()
            mock_repairer.return_value = mock_repairer_instance

            # Mock repair capability check
            mock_repairer_instance.check_repair_capability.return_value = {
                "can_repair": True,
                "par2_status": "available",
                "original_file_exists": True,
            }

            # Mock successful repair result
            from coldpack.core.repairer import RepairResult

            successful_result = RepairResult(
                success=True, message="Archive repaired successfully", repaired_files=[]
            )
            mock_repairer_instance.repair_archive.return_value = successful_result

            result = runner.invoke(app, ["repair", par2_path])

            # Should succeed
            assert result.exit_code == 0
            mock_repairer_instance.check_repair_capability.assert_called_once()
            mock_repairer_instance.repair_archive.assert_called_once()
        finally:
            # Cleanup
            os.unlink(par2_path)


class TestInfoCommand:
    """Test info command functionality."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_info_help(self, runner):
        """Test info command help."""
        result = runner.invoke(app, ["info", "--help"])
        assert result.exit_code == 0
        assert "Show" in result.stdout

    def test_info_nonexistent_archive(self, runner):
        """Test info with non-existent archive."""
        result = runner.invoke(app, ["info", "/nonexistent/archive.7z"])
        assert result.exit_code == ExitCodes.FILE_NOT_FOUND
        # Remove ANSI color codes for assertion
        clean_output = result.stdout.replace("\x1b[31m", "").replace("\x1b[0m", "")
        assert "File not found" in clean_output

    @patch("coldpack.cli.MultiFormatExtractor")
    def test_info_success(self, mock_extractor, runner):
        """Test successful info display."""
        # Create temporary archive file
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp_archive:
            archive_path = tmp_archive.name
            tmp_archive.write(b"dummy archive content")

        try:
            # Mock extractor
            mock_extractor_instance = MagicMock()
            mock_extractor.return_value = mock_extractor_instance
            mock_extractor_instance.get_archive_info.return_value = {
                "path": archive_path,
                "format": ".7z",
                "file_count": 5,
                "size": 1024,
                "has_single_root": True,
                "root_name": "test_root",
            }

            result = runner.invoke(app, ["info", archive_path])

            # Should succeed
            assert result.exit_code == 0
            mock_extractor_instance.get_archive_info.assert_called_once()
            assert "Archive:" in result.stdout
        finally:
            # Cleanup
            os.unlink(archive_path)


class TestMetadataLoading:
    """Test coldpack metadata loading functionality."""

    def test_load_metadata_no_file(self):
        """Test loading metadata when file doesn't exist."""
        from coldpack.cli import _load_coldpack_metadata

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "test.7z"
            archive_path.write_text("dummy archive")

            metadata, error = _load_coldpack_metadata(archive_path)
            assert metadata is None
            assert error is None

    def test_load_metadata_corrupted_file(self):
        """Test loading corrupted metadata file."""
        from coldpack.cli import _load_coldpack_metadata

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "test.7z"
            archive_path.write_text("dummy archive")

            # Create corrupted metadata file
            metadata_dir = archive_path.parent / "metadata"
            metadata_dir.mkdir()
            metadata_file = metadata_dir / "metadata.toml"
            metadata_file.write_text("invalid toml content [[[")

            metadata, error = _load_coldpack_metadata(archive_path, verbose=True)
            assert metadata is None
            assert error is not None
            assert "Corrupted metadata.toml" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
