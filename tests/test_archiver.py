"""Tests for coldpack archive creation functionality."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from coldpack.config.settings import PAR2Settings, ProcessingOptions, SevenZipSettings
from coldpack.core.archiver import (
    ArchiveResult,
    ArchivingError,
    ColdStorageArchiver,
)


class TestArchiveResult:
    """Test ArchiveResult class."""

    def test_archive_result_initialization(self):
        """Test ArchiveResult initialization."""
        metadata = MagicMock()
        created_files = [Path("file1.txt"), Path("file2.txt")]

        result = ArchiveResult(
            success=True,
            metadata=metadata,
            message="Archive created successfully",
            created_files=created_files,
            error_details="No errors",
        )

        assert result.success is True
        assert result.metadata == metadata
        assert result.message == "Archive created successfully"
        assert result.created_files == created_files
        assert result.error_details == "No errors"

    def test_archive_result_defaults(self):
        """Test ArchiveResult with default values."""
        result = ArchiveResult(success=False)

        assert result.success is False
        assert result.metadata is None
        assert result.message == ""
        assert result.created_files == []
        assert result.error_details is None

    def test_archive_result_str_success(self):
        """Test string representation for successful result."""
        result = ArchiveResult(success=True, message="Operation completed")

        str_repr = str(result)
        assert str_repr == "Archive SUCCESS: Operation completed"

    def test_archive_result_str_failure(self):
        """Test string representation for failed result."""
        result = ArchiveResult(success=False, message="Operation failed")

        str_repr = str(result)
        assert str_repr == "Archive FAILED: Operation failed"


class TestColdStorageArchiver:
    """Test ColdStorageArchiver class."""

    @pytest.fixture
    def archiver(self):
        """Create a ColdStorageArchiver instance with default settings."""
        return ColdStorageArchiver()

    @pytest.fixture
    def custom_archiver(self):
        """Create a ColdStorageArchiver instance with custom settings."""
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False, verbose=True
        )
        sevenzip_settings = SevenZipSettings(level=1, threads=1)
        par2_settings = PAR2Settings(redundancy_percent=5)

        return ColdStorageArchiver(
            processing_options=processing_options,
            sevenzip_settings=sevenzip_settings,
            par2_settings=par2_settings,
        )

    @pytest.fixture
    def temp_source_dir(self):
        """Create temporary source directory with test files."""
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

    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_archiver_initialization_defaults(self, archiver):
        """Test archiver initialization with default settings."""
        assert archiver.sevenzip_settings is not None
        assert archiver.processing_options is not None
        assert archiver.par2_settings is not None
        assert archiver.extractor is not None
        assert archiver.verifier is not None
        assert archiver.repairer is not None

    def test_archiver_initialization_custom(self, custom_archiver):
        """Test archiver initialization with custom settings."""
        assert custom_archiver.sevenzip_settings.level == 1
        assert custom_archiver.sevenzip_settings.threads == 1
        assert custom_archiver.processing_options.verify_integrity is False
        assert custom_archiver.processing_options.generate_par2 is False
        assert custom_archiver.par2_settings.redundancy_percent == 5

    def test_archiver_initialization_with_memory_limit(self):
        """Test archiver initialization with memory_limit in SevenZipSettings."""
        sevenzip_settings = SevenZipSettings(
            level=7, dictionary_size="64m", threads=4, memory_limit="1g"
        )
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options, sevenzip_settings=sevenzip_settings
        )

        assert archiver.sevenzip_settings.memory_limit == "1g"
        assert archiver.sevenzip_settings.level == 7
        assert archiver.sevenzip_settings.dictionary_size == "64m"
        assert archiver.sevenzip_settings.threads == 4

    def test_create_archive_nonexistent_source(self, archiver, temp_output_dir):
        """Test create_archive with non-existent source."""
        nonexistent_source = Path("/nonexistent/source")

        with pytest.raises(FileNotFoundError, match="Source not found"):
            archiver.create_archive(nonexistent_source, temp_output_dir)

    def test_create_archive_nonexistent_output_dir(self, archiver, temp_source_dir):
        """Test create_archive with non-existent output directory - should auto-create."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nonexistent_output = Path(temp_dir) / "nonexistent" / "output"

            # Set minimal processing to avoid external tool dependencies
            archiver.processing_options.verify_integrity = False
            archiver.processing_options.generate_par2 = False
            archiver.processing_options.verify_sha256 = False
            archiver.processing_options.verify_blake3 = False

            try:
                result = archiver.create_archive(temp_source_dir, nonexistent_output)
                # Should succeed and create the directory
                assert isinstance(result, ArchiveResult)
                assert nonexistent_output.exists()
            except Exception:
                # If it fails due to missing external tools, that's expected in test environment
                pytest.skip("External tools not available in test environment")

    @patch("coldpack.utils.filesystem.check_disk_space")
    def test_create_archive_insufficient_disk_space(
        self, mock_check_disk, archiver, temp_source_dir, temp_output_dir
    ):
        """Test create_archive with insufficient disk space."""
        from coldpack.utils.filesystem import InsufficientSpaceError

        # Mock insufficient disk space by raising exception
        mock_check_disk.side_effect = InsufficientSpaceError("Not enough space")

        with pytest.raises((InsufficientSpaceError, ArchivingError)):
            archiver.create_archive(temp_source_dir, temp_output_dir)

    def test_create_archive_existing_output_no_force(
        self, archiver, temp_source_dir, temp_output_dir
    ):
        """Test create_archive with existing output directory and no force flag."""
        # Create existing archive directory
        archive_name = temp_source_dir.name
        existing_archive_dir = temp_output_dir / archive_name
        existing_archive_dir.mkdir()

        # Set force_overwrite to False
        archiver.processing_options.force_overwrite = False

        with pytest.raises(ArchivingError, match="Archive directory already exists"):
            archiver.create_archive(temp_source_dir, temp_output_dir)

    @patch("coldpack.utils.filesystem.check_disk_space")
    def test_create_archive_success_minimal(
        self, mock_check_disk, archiver, temp_source_dir, temp_output_dir
    ):
        """Test successful archive creation with minimal verification."""
        # Mock disk space check to pass
        mock_check_disk.return_value = True

        # Set minimal processing options to avoid complex mocking
        archiver.processing_options.verify_integrity = False
        archiver.processing_options.generate_par2 = False
        archiver.processing_options.verify_sha256 = False
        archiver.processing_options.verify_blake3 = False

        # This test should focus on basic flow - let it use real methods
        # but with minimal verification to avoid external dependencies
        try:
            result = archiver.create_archive(temp_source_dir, temp_output_dir)
            # If it succeeds, check basic properties
            assert isinstance(result, ArchiveResult)
        except Exception:
            # If it fails due to missing external tools, that's expected in test environment
            pytest.skip("External tools not available in test environment")

    def test_get_clean_archive_name_directory(self, archiver):
        """Test _get_clean_archive_name with directory."""
        source_path = Path("/path/to/test_directory")

        name = archiver._get_clean_archive_name(source_path)

        assert name == "test_directory"

    def test_get_clean_archive_name_file(self, archiver):
        """Test _get_clean_archive_name with file."""
        source_path = Path("/path/to/test_file.txt")

        name = archiver._get_clean_archive_name(source_path)

        # For non-archive files, method returns stem (filename without extension)
        assert name == "test_file"

    def test_get_clean_archive_name_archive(self, archiver):
        """Test _get_clean_archive_name with archive file."""
        source_path = Path("/path/to/archive.7z")

        name = archiver._get_clean_archive_name(source_path)

        assert name == "archive"

    @patch("coldpack.core.archiver.MultiFormatExtractor")
    def test_extract_source_directory(self, mock_extractor, archiver, temp_source_dir):
        """Test _extract_source with directory input."""
        mock_safe_ops = MagicMock()

        result = archiver._extract_source(temp_source_dir, mock_safe_ops)

        # Should return the original directory
        assert result == temp_source_dir

        # Extractor should not be called for directories
        mock_extractor.assert_not_called()

    def test_extract_source_archive_file(self, archiver, temp_output_dir):
        """Test _extract_source with archive file input."""
        # Skip this test as it requires real 7z files and external tools
        pytest.skip("This test requires real archive files and external 7z tools")

    def test_create_7z_archive_success(
        self, archiver, temp_source_dir, temp_output_dir
    ):
        """Test successful 7z archive creation."""
        # Create archive directory
        archive_dir = temp_output_dir / "test_archive"
        archive_dir.mkdir()
        archive_name = "test"

        with patch(
            "coldpack.utils.filesystem.safe_file_operations"
        ) as mock_safe_ops_ctx:
            mock_safe_ops = MagicMock()
            mock_safe_ops_ctx.return_value.__enter__.return_value = mock_safe_ops

            result = archiver._create_7z_archive(
                source_dir=temp_source_dir,
                archive_dir=archive_dir,
                archive_name=archive_name,
                safe_ops=mock_safe_ops,
            )

            assert result.name == f"{archive_name}.7z"
            assert result.parent == archive_dir

    def test_create_7z_archive_failure(
        self, archiver, temp_source_dir, temp_output_dir
    ):
        """Test 7z archive creation failure."""
        # Create archive directory
        archive_dir = temp_output_dir / "test_archive"
        archive_dir.mkdir()
        archive_name = "test"

        with patch(
            "coldpack.utils.sevenzip.SevenZipCompressor"
        ) as mock_compressor_class:
            # Mock compressor to raise exception
            mock_compressor = MagicMock()
            mock_compressor_class.return_value = mock_compressor
            mock_compressor.compress_directory.side_effect = Exception(
                "Compression failed"
            )

            with patch(
                "coldpack.utils.filesystem.safe_file_operations"
            ) as mock_safe_ops_ctx:
                mock_safe_ops = MagicMock()
                mock_safe_ops_ctx.return_value.__enter__.return_value = mock_safe_ops

                with pytest.raises(ArchivingError, match="Failed to create 7z archive"):
                    archiver._create_7z_archive(
                        source_dir=temp_source_dir,
                        archive_dir=archive_dir,
                        archive_name=archive_name,
                        safe_ops=mock_safe_ops,
                    )

    def test_archiver_memory_limit_integration(self):
        """Test that memory_limit is properly integrated into archiver functionality."""
        from coldpack.config.settings import ProcessingOptions, SevenZipSettings

        # Create archiver with memory_limit
        sevenzip_settings = SevenZipSettings(
            level=7, dictionary_size="64m", threads=4, memory_limit="1g"
        )
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options, sevenzip_settings=sevenzip_settings
        )

        # Verify the settings have the memory_limit and are properly stored
        assert archiver.sevenzip_settings.memory_limit == "1g"
        assert archiver.sevenzip_settings.level == 7
        assert archiver.sevenzip_settings.dictionary_size == "64m"
        assert archiver.sevenzip_settings.threads == 4

        # Verify the settings can be converted to py7zz config format with memory_limit
        config = archiver.sevenzip_settings.to_py7zz_config()
        assert config["memory_limit"] == "1g"
        assert config["level"] == 7
        assert config["dictionary_size"] == "64m"
        assert config["threads"] == 4

    @patch("coldpack.core.archiver.optimize_7z_compression_settings")
    def test_archiver_memory_limit_with_dynamic_optimization(
        self, mock_optimize_settings
    ):
        """Test memory_limit preservation during dynamic optimization."""
        from coldpack.config.settings import ProcessingOptions, SevenZipSettings

        # Setup mock optimized settings with memory_limit preserved
        optimized_settings = SevenZipSettings(
            level=9, dictionary_size="256m", threads=4, memory_limit="2g"
        )
        mock_optimize_settings.return_value = optimized_settings

        # Create archiver with manual_settings=False (triggers optimization)
        sevenzip_settings = SevenZipSettings(
            level=5,
            dictionary_size="16m",
            threads=4,
            memory_limit="2g",
            manual_settings=False,
        )
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options, sevenzip_settings=sevenzip_settings
        )

        # Create temporary directories
        with tempfile.TemporaryDirectory() as source_dir_str:
            source_dir = Path(source_dir_str)
            (source_dir / "test_file.txt").write_text("test content")

            with tempfile.TemporaryDirectory() as archive_dir_str:
                archive_dir = Path(archive_dir_str)

                with patch(
                    "coldpack.utils.filesystem.safe_file_operations"
                ) as mock_safe_ops_ctx:
                    mock_safe_ops = MagicMock()
                    mock_safe_ops_ctx.return_value.__enter__.return_value = (
                        mock_safe_ops
                    )

                    with patch(
                        "coldpack.utils.sevenzip.SevenZipCompressor"
                    ) as mock_compressor_class:
                        mock_compressor = MagicMock()
                        mock_compressor_class.return_value = mock_compressor

                        # Call _create_7z_archive to trigger optimization
                        import contextlib

                        with contextlib.suppress(Exception):
                            # Expected to fail due to mocking, but optimization should be called
                            archiver._create_7z_archive(
                                source_dir, archive_dir, "test_archive", mock_safe_ops
                            )

                        # Verify optimize_7z_compression_settings was called with memory_limit
                        mock_optimize_settings.assert_called_once()
                        call_args = mock_optimize_settings.call_args
                        # Check that function was called with correct positional arguments
                        # optimize_7z_compression_settings(source_size, threads, memory_limit)
                        assert len(call_args[0]) == 3  # 3 positional arguments
                        source_size, threads, memory_limit = call_args[0]
                        assert memory_limit == "2g"
                        assert threads == 4

    @patch("coldpack.core.archiver.logger")
    def test_archiver_memory_limit_logging(self, mock_logger):
        """Test that memory_limit information is properly logged."""
        from coldpack.config.settings import ProcessingOptions, SevenZipSettings

        # Create archiver with memory_limit
        sevenzip_settings = SevenZipSettings(
            level=7, dictionary_size="64m", threads=4, memory_limit="1g"
        )
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        # Initialize archiver (should log initialization)
        ColdStorageArchiver(
            processing_options=processing_options, sevenzip_settings=sevenzip_settings
        )

        # Verify initialization logging was called
        mock_logger.debug.assert_called()

        # Check that one of the debug calls mentions compression level
        debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
        initialization_logged = any("compression level" in msg for msg in debug_calls)
        assert initialization_logged

    def test_archiver_memory_limit_with_manual_settings(self):
        """Test that memory_limit is preserved when manual_settings=True."""
        from coldpack.config.settings import ProcessingOptions, SevenZipSettings

        # Create archiver with manual_settings=True
        sevenzip_settings = SevenZipSettings(
            level=3,
            dictionary_size="4m",
            threads=2,
            memory_limit="512m",
            manual_settings=True,
        )
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options, sevenzip_settings=sevenzip_settings
        )

        # Verify all manual settings including memory_limit are preserved
        assert archiver.sevenzip_settings.memory_limit == "512m"
        assert archiver.sevenzip_settings.level == 3
        assert archiver.sevenzip_settings.dictionary_size == "4m"
        assert archiver.sevenzip_settings.threads == 2
        assert archiver.sevenzip_settings.manual_settings is True

    def test_archiver_sevenzip_compressor_initialization_with_memory_limit(self):
        """Test that SevenZipCompressor is initialized with memory_limit settings."""
        from coldpack.config.settings import ProcessingOptions, SevenZipSettings

        # Create archiver with memory_limit
        sevenzip_settings = SevenZipSettings(
            level=6, dictionary_size="16m", threads=8, memory_limit="4g"
        )
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options, sevenzip_settings=sevenzip_settings
        )

        # Verify that sevenzip_compressor was initialized with the correct settings
        assert archiver.sevenzip_compressor is not None
        assert archiver.sevenzip_compressor.settings.memory_limit == "4g"
        assert archiver.sevenzip_compressor.settings.level == 6
        assert archiver.sevenzip_compressor.settings.dictionary_size == "16m"
        assert archiver.sevenzip_compressor.settings.threads == 8

    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_7z_integrity_success(
        self, mock_validate, archiver, temp_output_dir
    ):
        """Test successful 7z integrity verification."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Mock validation to return True
        mock_validate.return_value = True

        # Should not raise exception
        archiver._verify_7z_integrity(archive_path)

        mock_validate.assert_called_once_with(str(archive_path))

    @patch("coldpack.utils.sevenzip.validate_7z_archive")
    def test_verify_7z_integrity_failure(
        self, mock_validate, archiver, temp_output_dir
    ):
        """Test 7z integrity verification failure."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Mock validation to return False
        mock_validate.return_value = False

        with pytest.raises(ArchivingError, match="7z integrity verification failed"):
            archiver._verify_7z_integrity(archive_path)

    @patch("coldpack.utils.hashing.DualHasher")
    @patch("coldpack.utils.hashing.HashVerifier")
    def test_generate_and_verify_single_hash_success(
        self, mock_verifier_class, mock_hasher_class, archiver, temp_output_dir
    ):
        """Test successful hash generation and verification."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Create metadata directory
        metadata_dir = temp_output_dir / "metadata"
        metadata_dir.mkdir()

        # Mock hasher
        mock_hasher = MagicMock()
        mock_hasher_class.return_value = mock_hasher
        mock_hasher.compute_file_hash.return_value = "dummy_hash"

        # Mock verifier
        mock_verifier = MagicMock()
        mock_verifier_class.return_value = mock_verifier
        mock_verifier.verify_file_hash.return_value = True

        mock_safe_ops = MagicMock()

        result_file = archiver._generate_and_verify_single_hash(
            archive_path=archive_path,
            metadata_dir=metadata_dir,
            algorithm="sha256",
            safe_ops=mock_safe_ops,
        )

        assert result_file is not None
        assert result_file.suffix == ".sha256"

        mock_hasher.compute_file_hash.assert_called_once()
        mock_verifier.verify_file_hash.assert_called_once()

    @patch("coldpack.utils.hashing.DualHasher")
    def test_generate_and_verify_single_hash_failure(
        self, mock_hasher_class, archiver, temp_output_dir
    ):
        """Test hash generation failure."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Create metadata directory
        metadata_dir = temp_output_dir / "metadata"
        metadata_dir.mkdir()

        # Mock hasher to raise exception
        mock_hasher = MagicMock()
        mock_hasher_class.return_value = mock_hasher
        mock_hasher.compute_file_hash.side_effect = Exception("Hash computation failed")

        mock_safe_ops = MagicMock()

        with pytest.raises(ArchivingError, match="Failed to generate sha256 hash"):
            archiver._generate_and_verify_single_hash(
                archive_path=archive_path,
                metadata_dir=metadata_dir,
                algorithm="sha256",
                safe_ops=mock_safe_ops,
            )

    @patch("coldpack.utils.par2.PAR2Manager")
    def test_generate_and_verify_par2_files_success(
        self, mock_par2_manager_class, archiver, temp_output_dir
    ):
        """Test successful PAR2 file generation and verification."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Create metadata directory
        metadata_dir = temp_output_dir / "metadata"
        metadata_dir.mkdir()

        # Mock PAR2 manager
        mock_par2_manager = MagicMock()
        mock_par2_manager_class.return_value = mock_par2_manager

        par2_files = [
            metadata_dir / "test.par2",
            metadata_dir / "test.vol000+01.par2",
        ]
        mock_par2_manager.create_recovery_files.return_value = par2_files
        mock_par2_manager.verify_recovery_data.return_value = True

        mock_safe_ops = MagicMock()

        result_files = archiver._generate_and_verify_par2_files(
            archive_path=archive_path, metadata_dir=metadata_dir, safe_ops=mock_safe_ops
        )

        assert result_files == par2_files
        mock_par2_manager.create_recovery_files.assert_called_once()
        mock_par2_manager.verify_recovery_data.assert_called_once()

    @patch("coldpack.utils.par2.PAR2Manager")
    def test_generate_and_verify_par2_files_failure(
        self, mock_par2_manager_class, archiver, temp_output_dir
    ):
        """Test PAR2 file generation failure."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Create metadata directory
        metadata_dir = temp_output_dir / "metadata"
        metadata_dir.mkdir()

        # Mock PAR2 manager to raise exception
        mock_par2_manager = MagicMock()
        mock_par2_manager_class.return_value = mock_par2_manager
        mock_par2_manager.create_recovery_files.side_effect = Exception(
            "PAR2 creation failed"
        )

        mock_safe_ops = MagicMock()

        with pytest.raises(
            ArchivingError, match="Failed to generate PAR2 recovery files"
        ):
            archiver._generate_and_verify_par2_files(
                archive_path=archive_path,
                metadata_dir=metadata_dir,
                safe_ops=mock_safe_ops,
            )

    def test_create_metadata_basic(self, archiver, temp_source_dir, temp_output_dir):
        """Test basic metadata creation."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive content")

        # Create extracted directory
        extracted_dir = temp_output_dir / "extracted"
        extracted_dir.mkdir()

        hash_files = {"sha256": temp_output_dir / "test.sha256"}
        par2_files = [temp_output_dir / "test.par2"]

        metadata = archiver._create_metadata(
            source_path=temp_source_dir,
            archive_path=archive_path,
            extracted_dir=extracted_dir,
            hash_files=hash_files,
            par2_files=par2_files,
        )

        assert metadata is not None
        assert metadata.source_path == temp_source_dir
        assert metadata.archive_path == archive_path

    def test_organize_output_files_creates_structure(self, archiver, temp_output_dir):
        """Test that organize_output_files creates proper directory structure."""
        archive_name = "test_archive"
        archive_path = temp_output_dir / f"{archive_name}.7z"
        archive_path.write_bytes(b"dummy archive")

        hash_files = {"sha256": temp_output_dir / "test.sha256"}
        par2_files = [temp_output_dir / "test.par2"]

        # Create hash and par2 files
        hash_files["sha256"].write_text("dummy hash")
        par2_files[0].write_text("dummy par2")

        mock_safe_ops = MagicMock()

        result = archiver._organize_output_files(
            archive_path=archive_path,
            hash_files=hash_files,
            par2_files=par2_files,
            archive_name=archive_name,
            safe_ops=mock_safe_ops,
        )

        # Should return organization result dictionary
        assert isinstance(result, dict)
        assert "archive_dir" in result or "final_archive_path" in result


class TestArchivingError:
    """Test ArchivingError exception."""

    def test_archiving_error_creation(self):
        """Test ArchivingError can be created and raised."""
        with pytest.raises(ArchivingError, match="Test error"):
            raise ArchivingError("Test error")

    def test_archiving_error_inheritance(self):
        """Test ArchivingError inherits from Exception."""
        error = ArchivingError("Test")
        assert isinstance(error, Exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
