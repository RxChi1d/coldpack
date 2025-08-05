"""End-to-end integration tests for memory_limit parameter functionality.

This module tests the complete flow of memory_limit parameter from CLI input
through archiver processing to final py7zz configuration.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from coldpack.cli import app
from coldpack.config.constants import ExitCodes
from coldpack.config.settings import SevenZipSettings
from coldpack.core.archiver import ColdStorageArchiver


class TestMemoryLimitEndToEndFlow:
    """Test complete memory_limit flow from CLI to compression."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_source_dir(self):
        """Create temporary source directory with test content."""
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

    def test_cli_memory_limit_to_py7zz_config_flow(self, runner, temp_source_dir):
        """Test complete flow: CLI --memory-limit → SevenZipSettings → py7zz config."""
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
                        "2g",
                        "--level",
                        "7",
                        "--dict",
                        "64m",
                        "--threads",
                        "4",
                    ],
                )

                # Should succeed
                assert result.exit_code == 0

                # Verify archiver was initialized with correct settings
                mock_archiver.assert_called_once()
                archiver_call_args = mock_archiver.call_args

                # Extract sevenzip_settings from the call
                sevenzip_settings = None
                if (
                    archiver_call_args[1]
                    and "sevenzip_settings" in archiver_call_args[1]
                ):
                    sevenzip_settings = archiver_call_args[1]["sevenzip_settings"]
                elif len(archiver_call_args[0]) > 1:
                    # positional argument
                    sevenzip_settings = archiver_call_args[0][1]

                # Verify settings contain memory_limit
                assert sevenzip_settings is not None
                assert sevenzip_settings.memory_limit == "2g"
                assert sevenzip_settings.level == 7
                assert sevenzip_settings.dictionary_size == "64m"
                assert sevenzip_settings.threads == 4

                # Verify py7zz config conversion
                py7zz_config = sevenzip_settings.to_py7zz_config()
                assert py7zz_config["memory_limit"] == "2g"
                assert py7zz_config["level"] == 7
                assert py7zz_config["dictionary_size"] == "64m"
                assert py7zz_config["threads"] == 4

    def test_memory_limit_error_propagation_chain(self, runner, temp_source_dir):
        """Test error propagation from CLI validation through archiver."""
        # Test invalid memory_limit format
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--memory-limit", "invalid_format"]
        )

        # Should fail at CLI validation level
        assert result.exit_code == ExitCodes.INVALID_FORMAT
        assert "memory-limit must be in format" in result.stdout

        # Test exceeding 64GB limit
        result = runner.invoke(
            app, ["create", str(temp_source_dir), "--memory-limit", "100g"]
        )

        # Should fail at CLI validation level
        assert result.exit_code == ExitCodes.INVALID_FORMAT
        assert "memory-limit cannot exceed 64GB" in result.stdout

    @patch("coldpack.utils.sevenzip.py7zz")
    def test_memory_limit_reaches_py7zz_compression(self, mock_py7zz, temp_source_dir):
        """Test that memory_limit actually reaches the py7zz compression layer."""
        # Create archiver with memory_limit
        sevenzip_settings = SevenZipSettings(
            level=6, dictionary_size="16m", threads=2, memory_limit="1g"
        )

        archiver = ColdStorageArchiver(sevenzip_settings=sevenzip_settings)

        with tempfile.TemporaryDirectory() as output_dir:
            archive_dir = Path(output_dir) / "test_archive"
            archive_dir.mkdir()

            with patch(
                "coldpack.utils.filesystem.safe_file_operations"
            ) as mock_safe_ops_ctx:
                mock_safe_ops = MagicMock()
                mock_safe_ops_ctx.return_value.__enter__.return_value = mock_safe_ops

                import contextlib

                with contextlib.suppress(Exception):
                    # Expected to fail due to mocking, but verify py7zz was called correctly
                    archiver._create_7z_archive(
                        temp_source_dir, archive_dir, "test_archive", mock_safe_ops
                    )

                # Verify py7zz.SevenZipFile was called with memory_limit in config
                mock_py7zz.SevenZipFile.assert_called_once()
                call_args = mock_py7zz.SevenZipFile.call_args

                # Extract config from the call
                config = call_args[1]["config"]
                assert hasattr(config, "memory_limit")

    def test_memory_limit_with_optimization_integration(self):
        """Test memory_limit preservation during dynamic optimization."""
        from coldpack.utils.sevenzip import optimize_7z_compression_settings

        # Test that optimize function preserves memory_limit
        source_size = 100 * 1024 * 1024  # 100MB
        memory_limit = "512m"

        optimized_settings = optimize_7z_compression_settings(
            source_size, threads=4, memory_limit=memory_limit
        )

        # Verify memory_limit is preserved
        assert optimized_settings.memory_limit == memory_limit
        # Verify other settings are optimized based on size
        assert optimized_settings.level == 7  # Large file optimization
        assert optimized_settings.dictionary_size == "64m"
        assert optimized_settings.threads == 4

    def test_multiple_memory_limit_formats_end_to_end(self, runner, temp_source_dir):
        """Test various memory_limit formats work end-to-end."""
        from coldpack.core.archiver import ArchiveResult

        test_formats = [
            ("1g", "1g"),
            ("512m", "512m"),
            ("256k", "256k"),
            ("1024", "1024"),
            ("2G", "2G"),  # Case insensitive
            ("64g", "64g"),  # Boundary case
        ]

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
                success=True, message="Archive created successfully", created_files=[]
            )
            mock_archiver_instance.create_archive.return_value = success_result

            for input_format, expected_format in test_formats:
                mock_archiver.reset_mock()

                with tempfile.TemporaryDirectory() as output_dir:
                    result = runner.invoke(
                        app,
                        [
                            "create",
                            str(temp_source_dir),
                            "--output-dir",
                            output_dir,
                            "--memory-limit",
                            input_format,
                        ],
                    )

                    # Should succeed
                    assert result.exit_code == 0, f"Failed for format: {input_format}"

                    # Verify archiver was called with correct memory_limit
                    mock_archiver.assert_called_once()
                    archiver_call_args = mock_archiver.call_args

                    # Extract sevenzip_settings
                    sevenzip_settings = None
                    if (
                        archiver_call_args[1]
                        and "sevenzip_settings" in archiver_call_args[1]
                    ):
                        sevenzip_settings = archiver_call_args[1]["sevenzip_settings"]
                    elif len(archiver_call_args[0]) > 1:
                        sevenzip_settings = archiver_call_args[0][1]

                    assert sevenzip_settings is not None
                    assert (
                        sevenzip_settings.memory_limit.lower()
                        == expected_format.lower()
                    )


class TestMemoryLimitErrorHandling:
    """Test error handling across the memory_limit pipeline."""

    def test_sevenzip_settings_validation_errors(self):
        """Test SevenZipSettings validation catches memory_limit errors."""
        # Test invalid format
        with pytest.raises(ValueError, match="memory_limit must be in format"):
            SevenZipSettings(memory_limit="invalid")

        # Test zero value
        with pytest.raises(ValueError, match="memory_limit must be a positive number"):
            SevenZipSettings(memory_limit="0g")

        # Test exceeding 64GB
        with pytest.raises(ValueError, match="memory_limit cannot exceed 64GB"):
            SevenZipSettings(memory_limit="65g")

    def test_archiver_handles_sevenzip_settings_errors(self):
        """Test that archiver properly handles SevenZipSettings validation errors."""
        # Test that invalid settings are caught before archiver initialization
        with pytest.raises(ValueError):
            invalid_settings = SevenZipSettings(memory_limit="invalid_format")
            ColdStorageArchiver(sevenzip_settings=invalid_settings)

    def test_memory_limit_boundary_conditions(self):
        """Test memory_limit boundary conditions."""
        # Test minimum valid values
        settings = SevenZipSettings(memory_limit="1k")
        assert settings.memory_limit == "1k"

        settings = SevenZipSettings(memory_limit="1m")
        assert settings.memory_limit == "1m"

        settings = SevenZipSettings(memory_limit="1g")
        assert settings.memory_limit == "1g"

        # Test maximum valid value (64GB)
        settings = SevenZipSettings(memory_limit="64g")
        assert settings.memory_limit == "64g"

        # Test just over the limit should fail
        with pytest.raises(ValueError):
            SevenZipSettings(memory_limit="65g")


class TestMemoryLimitMetadataIntegration:
    """Test memory_limit integration with metadata system."""

    def test_memory_limit_in_archive_metadata(self):
        """Test that memory_limit is properly stored in archive metadata."""
        from coldpack.config.settings import ArchiveMetadata

        # Create sevenzip_settings with memory_limit
        sevenzip_settings = SevenZipSettings(
            level=8, dictionary_size="64m", threads=6, memory_limit="3g"
        )

        # Create metadata with memory_limit settings
        metadata = ArchiveMetadata(
            source_path=Path("/test/source"),
            archive_path=Path("/test/archive.7z"),
            archive_name="test_archive",
            sevenzip_settings=sevenzip_settings,
        )

        # Verify memory_limit is preserved in metadata
        assert metadata.sevenzip_settings.memory_limit == "3g"
        assert metadata.sevenzip_settings.level == 8
        assert metadata.sevenzip_settings.dictionary_size == "64m"
        assert metadata.sevenzip_settings.threads == 6

    def test_memory_limit_metadata_serialization(self):
        """Test memory_limit settings can be serialized to/from TOML."""
        from coldpack.config.settings import ArchiveMetadata

        # Create settings with memory_limit
        sevenzip_settings = SevenZipSettings(
            level=9, dictionary_size="256m", threads=8, memory_limit="4g"
        )

        metadata = ArchiveMetadata(
            source_path=Path("/test/source"),
            archive_path=Path("/test/archive.7z"),
            archive_name="test_archive",
            sevenzip_settings=sevenzip_settings,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            toml_path = Path(f.name)

        try:
            # Save to TOML
            metadata.save_to_toml(toml_path)

            # Load from TOML
            loaded_metadata = ArchiveMetadata.load_from_toml(toml_path)

            # Verify memory_limit is preserved
            assert loaded_metadata.sevenzip_settings.memory_limit == "4g"
            assert loaded_metadata.sevenzip_settings.level == 9
            assert loaded_metadata.sevenzip_settings.dictionary_size == "256m"
            assert loaded_metadata.sevenzip_settings.threads == 8
        finally:
            toml_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
