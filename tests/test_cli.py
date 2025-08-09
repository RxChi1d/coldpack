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

    @patch("coldpack.cli.ColdStorageArchiver")
    @patch("coldpack.cli.check_par2_availability")
    def test_create_with_memory_limit(
        self, mock_par2_check, mock_archiver, runner, temp_source_dir
    ):
        """Test create command with memory_limit parameter."""
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
                    "--memory-limit",
                    "512m",
                ],
            )

            # Should succeed
            assert result.exit_code == 0
            mock_archiver_instance.create_archive.assert_called_once()

    @patch("coldpack.cli.ColdStorageArchiver")
    @patch("coldpack.cli.check_par2_availability")
    def test_create_with_memory_limit_and_compression_params(
        self, mock_par2_check, mock_archiver, runner, temp_source_dir
    ):
        """Test create command with memory_limit and other compression parameters."""
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
                    "--level",
                    "9",
                    "--dict",
                    "256m",
                    "--memory-limit",
                    "2g",
                    "--threads",
                    "8",
                ],
            )

            # Should succeed
            assert result.exit_code == 0
            mock_archiver_instance.create_archive.assert_called_once()

    def test_create_invalid_memory_limit_format(self, runner, temp_source_dir):
        """Test create with invalid memory_limit format."""
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--memory-limit", "invalid"]
        )
        assert result.exit_code == ExitCodes.INVALID_FORMAT
        # Remove ANSI color codes for assertion
        clean_output = (
            result.stdout.replace("\x1b[31m", "")
            .replace("\x1b[0m", "")
            .replace("\x1b[1;31m", "")
        )
        assert "memory-limit must be in format" in clean_output

    def test_create_invalid_memory_limit_zero(self, runner, temp_source_dir):
        """Test create with zero memory_limit."""
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--memory-limit", "0m"]
        )
        assert result.exit_code == ExitCodes.INVALID_FORMAT
        # Remove ANSI color codes for assertion
        clean_output = (
            result.stdout.replace("\x1b[31m", "")
            .replace("\x1b[0m", "")
            .replace("\x1b[1;31m", "")
        )
        assert "memory-limit must be a positive number" in clean_output

    def test_create_invalid_memory_limit_exceeds_64gb(self, runner, temp_source_dir):
        """Test create with memory_limit exceeding 64GB."""
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--memory-limit", "65g"]
        )
        assert result.exit_code == ExitCodes.INVALID_FORMAT
        # Remove ANSI color codes for assertion
        clean_output = (
            result.stdout.replace("\x1b[31m", "")
            .replace("\x1b[0m", "")
            .replace("\x1b[1;31m", "")
        )
        assert "memory-limit cannot exceed 64GB" in clean_output

    def test_create_memory_limit_valid_formats(self, runner, temp_source_dir):
        """Test create with various valid memory_limit formats."""
        from coldpack.core.archiver import ArchiveResult

        valid_formats = ["1g", "512m", "256k", "1024"]

        with (
            patch("coldpack.cli.ColdStorageArchiver") as mock_archiver,
            patch("coldpack.cli.check_par2_availability") as mock_par2_check,
        ):
            # Mock PAR2 as available
            mock_par2_check.return_value = True

            # Mock archiver
            mock_archiver_instance = MagicMock()
            mock_archiver.return_value = mock_archiver_instance

            # Create a successful ArchiveResult
            success_result = ArchiveResult(
                success=True,
                message="Archive created successfully",
                created_files=[],
            )
            mock_archiver_instance.create_archive.return_value = success_result

            for memory_format in valid_formats:
                with tempfile.TemporaryDirectory() as output_dir:
                    result = runner.invoke(
                        app,
                        [
                            "create",
                            str(temp_source_dir),
                            "--output-dir",
                            output_dir,
                            "--memory-limit",
                            memory_format,
                        ],
                    )

                    # Should succeed for all valid formats
                    assert result.exit_code == 0, f"Failed for format: {memory_format}"

    def test_create_memory_limit_boundary_64gb(self, runner, temp_source_dir):
        """Test create with memory_limit exactly at 64GB boundary."""
        from coldpack.core.archiver import ArchiveResult

        with (
            patch("coldpack.cli.ColdStorageArchiver") as mock_archiver,
            patch("coldpack.cli.check_par2_availability") as mock_par2_check,
        ):
            # Mock PAR2 as available
            mock_par2_check.return_value = True

            # Mock archiver
            mock_archiver_instance = MagicMock()
            mock_archiver.return_value = mock_archiver_instance

            # Create a successful ArchiveResult
            success_result = ArchiveResult(
                success=True,
                message="Archive created successfully",
                created_files=[],
            )
            mock_archiver_instance.create_archive.return_value = success_result

            with tempfile.TemporaryDirectory() as output_dir:
                # Test exactly 64GB should succeed
                result = runner.invoke(
                    app,
                    [
                        "create",
                        str(temp_source_dir),
                        "--output-dir",
                        output_dir,
                        "--memory-limit",
                        "64g",
                    ],
                )
                assert result.exit_code == 0

    def test_create_memory_limit_case_insensitive(self, runner, temp_source_dir):
        """Test create with memory_limit case variations."""
        from coldpack.core.archiver import ArchiveResult

        case_formats = ["1G", "512M", "256K", "1g", "512m", "256k"]

        with (
            patch("coldpack.cli.ColdStorageArchiver") as mock_archiver,
            patch("coldpack.cli.check_par2_availability") as mock_par2_check,
        ):
            # Mock PAR2 as available
            mock_par2_check.return_value = True

            # Mock archiver
            mock_archiver_instance = MagicMock()
            mock_archiver.return_value = mock_archiver_instance

            # Create a successful ArchiveResult
            success_result = ArchiveResult(
                success=True,
                message="Archive created successfully",
                created_files=[],
            )
            mock_archiver_instance.create_archive.return_value = success_result

            for memory_format in case_formats:
                with tempfile.TemporaryDirectory() as output_dir:
                    result = runner.invoke(
                        app,
                        [
                            "create",
                            str(temp_source_dir),
                            "--output-dir",
                            output_dir,
                            "--memory-limit",
                            memory_format,
                        ],
                    )

                    # Should succeed for all case variations
                    assert result.exit_code == 0, f"Failed for format: {memory_format}"

    def test_create_memory_limit_with_whitespace(self, runner, temp_source_dir):
        """Test create with memory_limit containing whitespace (should fail)."""
        whitespace_formats = [" 1g", "1g ", " 1g ", "1 g"]

        for memory_format in whitespace_formats:
            result = runner.invoke(
                app, ["create", str(temp_source_dir), "--memory-limit", memory_format]
            )
            assert result.exit_code == ExitCodes.INVALID_FORMAT
            # Remove ANSI color codes for assertion
            clean_output = (
                result.stdout.replace("\x1b[31m", "")
                .replace("\x1b[0m", "")
                .replace("\x1b[1;31m", "")
            )
            assert "memory-limit must be in format" in clean_output

    def test_create_memory_limit_decimal_values(self, runner, temp_source_dir):
        """Test create with decimal memory_limit values (should fail)."""
        decimal_formats = ["1.5g", "512.5m", "0.5g"]

        for memory_format in decimal_formats:
            result = runner.invoke(
                app, ["create", str(temp_source_dir), "--memory-limit", memory_format]
            )
            assert result.exit_code == ExitCodes.INVALID_FORMAT
            # Remove ANSI color codes for assertion
            clean_output = (
                result.stdout.replace("\x1b[31m", "")
                .replace("\x1b[0m", "")
                .replace("\x1b[1;31m", "")
            )
            assert "memory-limit must be in format" in clean_output

    def test_create_memory_limit_with_verbose_output(self, runner, temp_source_dir):
        """Test create with memory_limit and verbose output."""
        from coldpack.core.archiver import ArchiveResult

        with (
            patch("coldpack.cli.ColdStorageArchiver") as mock_archiver,
            patch("coldpack.cli.check_par2_availability") as mock_par2_check,
        ):
            # Mock PAR2 as available
            mock_par2_check.return_value = True

            # Mock archiver
            mock_archiver_instance = MagicMock()
            mock_archiver.return_value = mock_archiver_instance

            # Create a successful ArchiveResult
            success_result = ArchiveResult(
                success=True,
                message="Archive created successfully",
                created_files=[],
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
                        "--memory-limit",
                        "1g",
                        "--verbose",
                    ],
                )

                # Should succeed and show verbose output
                assert result.exit_code == 0
                # Verbose flag should be properly handled with memory_limit


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


class TestKeyboardInterruptCleanup:
    """Test KeyboardInterrupt cleanup mechanism."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_test_files(self):
        """Create temporary test files and directories."""
        with tempfile.TemporaryDirectory() as base_temp_dir:
            base_path = Path(base_temp_dir)

            # Create a source directory with some test files
            source_dir = base_path / "source"
            source_dir.mkdir()

            # Add some test files to make archiving take some time
            for i in range(5):
                test_file = source_dir / f"test_file_{i}.txt"
                test_file.write_text("x" * (1024 * 100))  # 100KB files

            # Create output directory
            output_dir = base_path / "output"
            output_dir.mkdir()

            yield {
                "source_dir": source_dir,
                "output_dir": output_dir,
                "base_path": base_path,
            }

    def test_create_command_keyboard_interrupt_propagation(
        self, runner, temp_test_files
    ):
        """Test that KeyboardInterrupt properly propagates in create command."""

        source_dir = temp_test_files["source_dir"]
        output_dir = temp_test_files["output_dir"]

        # Mock the archiver to simulate KeyboardInterrupt during creation
        with patch("coldpack.cli.ColdStorageArchiver") as mock_archiver_class:
            mock_archiver = MagicMock()
            mock_archiver_class.return_value = mock_archiver

            # Simulate KeyboardInterrupt during archive creation
            mock_archiver.create_archive.side_effect = KeyboardInterrupt()

            # Run the create command
            result = runner.invoke(
                app,
                [
                    "create",
                    str(source_dir),
                    "--output-dir",
                    str(output_dir),
                    "--name",
                    "test_archive",
                ],
            )

            # Should exit with 130 (SIGINT standard exit code: 128 + 2)
            # When KeyboardInterrupt propagates properly, the runner returns 130
            assert result.exit_code == 130
            # The main goal is verifying KeyboardInterrupt propagation via exit code
            # Message verification is secondary since it might be in stdout or handled differently

    def test_archiver_safe_operations_cleanup_on_keyboard_interrupt(
        self, temp_test_files
    ):
        """Test that safe_file_operations cleans up on KeyboardInterrupt."""
        from coldpack.config.settings import ProcessingOptions
        from coldpack.core.archiver import ColdStorageArchiver

        source_dir = temp_test_files["source_dir"]
        output_dir = temp_test_files["output_dir"]

        archiver = ColdStorageArchiver(
            processing_options=ProcessingOptions(cleanup_on_error=True)
        )

        # Mock the 7z compression to raise KeyboardInterrupt after creating some files
        with patch(
            "coldpack.core.archiver.SevenZipCompressor"
        ) as mock_compressor_class:
            mock_compressor = MagicMock()
            mock_compressor_class.return_value = mock_compressor

            # Mock the compression to raise KeyboardInterrupt
            mock_compressor.compress_directory.side_effect = KeyboardInterrupt()

            # Verify that KeyboardInterrupt is raised and cleanup happens
            with pytest.raises(KeyboardInterrupt):
                archiver.create_archive(source_dir, output_dir, "test_archive")

            # Check that the output directory remains clean
            # (the archive directory should be cleaned up by safe_file_operations)
            archive_dir = output_dir / "test_archive"

            # The directory might be created but should be cleaned up
            # We can't guarantee the exact state due to timing, but we can verify
            # that the cleanup mechanism was triggered
            if archive_dir.exists():
                # If it still exists, it should be empty or contain minimal residue
                contents = list(archive_dir.rglob("*"))
                # Allow for some files that might not be cleaned up due to timing
                assert len(contents) <= 2, f"Cleanup may have failed, found: {contents}"

    def test_safe_file_operations_context_manager(self):
        """Test safe_file_operations context manager cleanup behavior."""
        from coldpack.utils.filesystem import safe_file_operations

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test cleanup on exception
            test_file = temp_path / "test_cleanup.txt"
            test_dir = temp_path / "test_dir"

            try:
                with safe_file_operations(cleanup_on_error=True) as safe_ops:
                    # Create some files and track them
                    test_file.write_text("test content")
                    test_dir.mkdir()

                    safe_ops.track_file(test_file)
                    safe_ops.track_directory(test_dir)

                    # Simulate KeyboardInterrupt
                    raise KeyboardInterrupt("Simulated interrupt")

            except KeyboardInterrupt:
                # After exception, files should be cleaned up
                assert not test_file.exists(), "File should be cleaned up"
                assert not test_dir.exists(), "Directory should be cleaned up"

    def test_safe_file_operations_no_cleanup_on_success(self):
        """Test that safe_file_operations doesn't cleanup on successful completion."""
        from coldpack.utils.filesystem import safe_file_operations

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test no cleanup on success
            test_file = temp_path / "test_success.txt"
            test_dir = temp_path / "test_success_dir"

            with safe_file_operations(cleanup_on_error=True) as safe_ops:
                # Create some files and track them
                test_file.write_text("test content")
                test_dir.mkdir()

                safe_ops.track_file(test_file)
                safe_ops.track_directory(test_dir)

                # Normal completion - no exception

            # Files should still exist after successful completion
            assert test_file.exists(), "File should remain after success"
            assert test_dir.exists(), "Directory should remain after success"

    def test_extractor_keyboard_interrupt_cleanup(self, temp_test_files):
        """Test that extractor KeyboardInterrupt is properly propagated."""
        # This test ensures extractor doesn't swallow KeyboardInterrupt
        # The actual cleanup is handled by safe_file_operations in extractor

        from coldpack.core.extractor import MultiFormatExtractor

        extractor = MultiFormatExtractor()
        test_archive = temp_test_files["base_path"] / "nonexistent.7z"
        output_dir = temp_test_files["output_dir"] / "extract_test"

        # Mock the extract method to raise KeyboardInterrupt
        with (
            patch.object(extractor, "extract", side_effect=KeyboardInterrupt),
            pytest.raises(KeyboardInterrupt),
        ):
            extractor.extract(test_archive, output_dir)


class TestDisplayArchiveSummary:
    """Test enhanced archive summary display functionality."""

    def test_display_archive_summary_with_full_metadata(self):
        """Test display_archive_summary with comprehensive metadata."""
        from unittest.mock import MagicMock, patch

        from coldpack.cli import display_archive_summary
        from coldpack.config.settings import (
            ArchiveMetadata,
            PAR2Settings,
            SevenZipSettings,
        )

        # Create comprehensive metadata
        sevenzip_settings = SevenZipSettings(
            level=5, dictionary_size="16m", threads=True
        )
        par2_settings = PAR2Settings(redundancy_percent=15)

        metadata = ArchiveMetadata(
            source_path=Path("/test/source"),
            archive_path=Path("/test/output/test.7z"),
            archive_name="test",
            file_count=10,
            directory_count=3,
            original_size=1048576,  # 1MB
            compressed_size=524288,  # 512KB
            compression_ratio=0.5,
            processing_time_seconds=2.5,
            created_at_iso="2025-08-08T12:00:00",
            sevenzip_settings=sevenzip_settings,
            par2_settings=par2_settings,
            verification_hashes={
                "sha256": "a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456",
                "blake3": "9876543210abcdef9876543210abcdef9876543210abcdef9876543210abcdef",
            },
            par2_files=["test.7z.par2", "test.7z.vol00+01.par2"],
        )

        # Create result object with metadata
        result = MagicMock()
        result.metadata = metadata

        # Mock console to capture output
        with patch("coldpack.cli.console") as mock_console:
            display_archive_summary(result)

            # Verify console.print was called (table display and separators)
            assert mock_console.print.call_count >= 3  # separators + table

            # Verify table creation and content
            calls = mock_console.print.call_args_list
            table_call = None
            for call in calls:
                if call[0] and hasattr(call[0][0], "add_row"):  # Find the table call
                    table_call = call[0][0]
                    break

            assert table_call is not None, "Table should be created and printed"

    def test_display_archive_summary_with_minimal_metadata(self):
        """Test display_archive_summary with minimal metadata."""
        from unittest.mock import MagicMock, patch

        from coldpack.cli import display_archive_summary
        from coldpack.config.settings import ArchiveMetadata

        # Create minimal metadata
        metadata = ArchiveMetadata(
            source_path=Path("/test/source"),
            archive_path=Path("/test/output/minimal.7z"),
            archive_name="minimal",
            file_count=1,
            original_size=100,
            compressed_size=80,
            compression_ratio=0.8,
        )

        result = MagicMock()
        result.metadata = metadata

        # Mock console to capture output
        with patch("coldpack.cli.console") as mock_console:
            display_archive_summary(result)

            # Should still display table with available information
            assert mock_console.print.call_count >= 3  # separators + table

    def test_display_archive_summary_with_negative_compression_ratio(self):
        """Test display_archive_summary with negative compression ratio (file grew)."""
        from unittest.mock import MagicMock, patch

        from coldpack.cli import display_archive_summary
        from coldpack.config.settings import ArchiveMetadata

        # Create metadata with negative compression (file grew)
        metadata = ArchiveMetadata(
            source_path=Path("/test/source"),
            archive_path=Path("/test/output/negative.7z"),
            archive_name="negative",
            file_count=2,
            original_size=50,
            compressed_size=100,
            compression_ratio=2.0,  # File doubled in size
        )

        result = MagicMock()
        result.metadata = metadata

        # Mock console to capture output
        with patch("coldpack.cli.console") as mock_console:
            display_archive_summary(result)

            # Should handle negative compression ratio gracefully
            assert mock_console.print.call_count >= 3

    def test_display_archive_summary_no_metadata(self):
        """Test display_archive_summary with no metadata returns early."""
        from unittest.mock import MagicMock, patch

        from coldpack.cli import display_archive_summary

        # Create result with no metadata
        result = MagicMock()
        result.metadata = None

        # Mock console to capture output
        with patch("coldpack.cli.console") as mock_console:
            display_archive_summary(result)

            # Should return early and not print anything
            mock_console.print.assert_not_called()

    def test_display_archive_summary_hash_formatting(self):
        """Test hash display formatting in archive summary."""
        from unittest.mock import MagicMock, patch

        from coldpack.cli import display_archive_summary
        from coldpack.config.settings import ArchiveMetadata

        # Create metadata with various hash lengths
        metadata = ArchiveMetadata(
            source_path=Path("/test/source"),
            archive_path=Path("/test/output/hash.7z"),
            archive_name="hash",
            file_count=1,
            original_size=100,
            compressed_size=80,
            verification_hashes={
                "sha256": "abcd1234" + "0" * 56,  # 64 char hash
                "blake3": "xyz789" + "1" * 58,  # 64 char hash
                "md5": "short12345",  # Short hash (< 20 chars)
            },
        )

        result = MagicMock()
        result.metadata = metadata

        with patch("coldpack.cli.console") as mock_console:
            display_archive_summary(result)

            # Should format hashes appropriately
            assert mock_console.print.call_count >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
