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

    def test_create_archive_nonexistent_source(self, archiver, temp_output_dir):
        """Test create_archive with non-existent source."""
        nonexistent_source = Path("/nonexistent/source")

        with pytest.raises(FileNotFoundError, match="Source not found"):
            archiver.create_archive(nonexistent_source, temp_output_dir)

    def test_create_archive_nonexistent_output_dir(self, archiver, temp_source_dir):
        """Test create_archive with non-existent output directory."""
        nonexistent_output = Path("/nonexistent/output")

        with pytest.raises(FileNotFoundError, match="Output directory not found"):
            archiver.create_archive(temp_source_dir, nonexistent_output)

    @patch("coldpack.core.archiver.check_disk_space")
    def test_create_archive_insufficient_disk_space(
        self, mock_check_disk, archiver, temp_source_dir, temp_output_dir
    ):
        """Test create_archive with insufficient disk space."""
        # Mock insufficient disk space
        mock_check_disk.return_value = False

        with pytest.raises(ArchivingError, match="Insufficient disk space"):
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

    @patch("coldpack.core.archiver.safe_file_operations")
    @patch("coldpack.core.archiver.ColdStorageArchiver._extract_source")
    @patch("coldpack.core.archiver.ColdStorageArchiver._create_7z_archive")
    @patch("coldpack.core.archiver.ColdStorageArchiver._verify_7z_integrity")
    @patch(
        "coldpack.core.archiver.ColdStorageArchiver._generate_and_verify_single_hash"
    )
    @patch("coldpack.core.archiver.ColdStorageArchiver._generate_and_verify_par2_files")
    @patch("coldpack.core.archiver.ColdStorageArchiver._organize_output_files")
    @patch("coldpack.core.archiver.ColdStorageArchiver._create_metadata")
    @patch("coldpack.core.archiver.check_disk_space")
    def test_create_archive_success_minimal(
        self,
        mock_check_disk,
        mock_create_metadata,
        mock_organize,
        mock_par2,
        mock_hash,
        mock_verify,
        mock_create_7z,
        mock_extract,
        mock_safe_ops,
        archiver,
        temp_source_dir,
        temp_output_dir,
    ):
        """Test successful archive creation with minimal verification."""
        # Mock all dependencies
        mock_check_disk.return_value = True
        mock_safe_ops_instance = MagicMock()
        mock_safe_ops.return_value.__enter__.return_value = mock_safe_ops_instance

        # Mock extraction
        mock_extract.return_value = temp_source_dir

        # Mock 7z creation
        archive_path = temp_output_dir / f"{temp_source_dir.name}.7z"
        mock_create_7z.return_value = archive_path

        # Mock hash generation (return empty lists for no hashes)
        mock_hash.return_value = []

        # Mock PAR2 generation (return empty list)
        mock_par2.return_value = []

        # Mock organization
        mock_organize.return_value = []

        # Mock metadata creation
        mock_metadata = MagicMock()
        mock_create_metadata.return_value = mock_metadata

        # Set minimal processing options
        archiver.processing_options.verify_integrity = False
        archiver.processing_options.generate_par2 = False
        archiver.processing_options.verify_sha256 = False
        archiver.processing_options.verify_blake3 = False

        result = archiver.create_archive(temp_source_dir, temp_output_dir)

        # Verify result
        assert isinstance(result, ArchiveResult)
        assert result.success is True
        assert result.metadata == mock_metadata

        # Verify methods were called
        mock_extract.assert_called_once()
        mock_create_7z.assert_called_once()
        mock_organize.assert_called_once()
        mock_create_metadata.assert_called_once()

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

    @patch("coldpack.core.archiver.MultiFormatExtractor")
    def test_extract_source_archive_file(
        self, mock_extractor, archiver, temp_output_dir
    ):
        """Test _extract_source with archive file input."""
        # Create temporary archive file
        archive_file = temp_output_dir / "test.7z"
        archive_file.write_bytes(b"dummy archive content")

        mock_safe_ops = MagicMock()
        mock_safe_ops.temp_dir = temp_output_dir / "temp"
        mock_safe_ops.temp_dir.mkdir()

        # Mock extractor
        mock_extractor_instance = MagicMock()
        mock_extractor.return_value = mock_extractor_instance
        extracted_dir = mock_safe_ops.temp_dir / "extracted"
        mock_extractor_instance.extract.return_value = extracted_dir

        result = archiver._extract_source(archive_file, mock_safe_ops)

        assert result == extracted_dir
        mock_extractor_instance.extract.assert_called_once()

    @patch("coldpack.core.archiver.SevenZipCompressor")
    def test_create_7z_archive_success(
        self, mock_compressor_class, archiver, temp_source_dir, temp_output_dir
    ):
        """Test successful 7z archive creation."""
        # Mock compressor
        mock_compressor = MagicMock()
        mock_compressor_class.return_value = mock_compressor

        archive_path = temp_output_dir / "test.7z"
        progress_tracker = MagicMock()

        result = archiver._create_7z_archive(
            source_path=temp_source_dir,
            archive_path=archive_path,
            progress_tracker=progress_tracker,
        )

        assert result == archive_path
        mock_compressor.compress_directory.assert_called_once()

    @patch("coldpack.core.archiver.SevenZipCompressor")
    def test_create_7z_archive_failure(
        self, mock_compressor_class, archiver, temp_source_dir, temp_output_dir
    ):
        """Test 7z archive creation failure."""
        # Mock compressor to raise exception
        mock_compressor = MagicMock()
        mock_compressor_class.return_value = mock_compressor
        mock_compressor.compress_directory.side_effect = Exception("Compression failed")

        archive_path = temp_output_dir / "test.7z"
        progress_tracker = MagicMock()

        with pytest.raises(ArchivingError, match="Failed to create 7z archive"):
            archiver._create_7z_archive(
                source_path=temp_source_dir,
                archive_path=archive_path,
                progress_tracker=progress_tracker,
            )

    @patch("coldpack.core.archiver.SevenZipCompressor")
    def test_verify_7z_integrity_success(
        self, mock_compressor_class, archiver, temp_output_dir
    ):
        """Test successful 7z integrity verification."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Mock compressor
        mock_compressor = MagicMock()
        mock_compressor_class.return_value = mock_compressor
        mock_compressor.test_integrity.return_value = True

        # Should not raise exception
        archiver._verify_7z_integrity(archive_path)

        mock_compressor.test_integrity.assert_called_once_with(archive_path)

    @patch("coldpack.core.archiver.SevenZipCompressor")
    def test_verify_7z_integrity_failure(
        self, mock_compressor_class, archiver, temp_output_dir
    ):
        """Test 7z integrity verification failure."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Mock compressor
        mock_compressor = MagicMock()
        mock_compressor_class.return_value = mock_compressor
        mock_compressor.test_integrity.return_value = False

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

        # Mock hasher
        mock_hasher = MagicMock()
        mock_hasher_class.return_value = mock_hasher
        mock_hasher.compute_file_hash.return_value = "dummy_hash"

        # Mock verifier
        mock_verifier = MagicMock()
        mock_verifier_class.return_value = mock_verifier
        mock_verifier.verify_file_hash.return_value = True

        progress_tracker = MagicMock()

        result_files = archiver._generate_and_verify_single_hash(
            archive_path=archive_path,
            algorithm="sha256",
            progress_tracker=progress_tracker,
        )

        assert len(result_files) == 1
        assert result_files[0].suffix == ".sha256"

        mock_hasher.compute_file_hash.assert_called_once()
        mock_verifier.verify_file_hash.assert_called_once()

    @patch("coldpack.utils.hashing.DualHasher")
    def test_generate_and_verify_single_hash_failure(
        self, mock_hasher_class, archiver, temp_output_dir
    ):
        """Test hash generation failure."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Mock hasher to raise exception
        mock_hasher = MagicMock()
        mock_hasher_class.return_value = mock_hasher
        mock_hasher.compute_file_hash.side_effect = Exception("Hash computation failed")

        progress_tracker = MagicMock()

        with pytest.raises(ArchivingError, match="Failed to generate sha256 hash"):
            archiver._generate_and_verify_single_hash(
                archive_path=archive_path,
                algorithm="sha256",
                progress_tracker=progress_tracker,
            )

    @patch("coldpack.core.archiver.PAR2Manager")
    def test_generate_and_verify_par2_files_success(
        self, mock_par2_manager_class, archiver, temp_output_dir
    ):
        """Test successful PAR2 file generation and verification."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Mock PAR2 manager
        mock_par2_manager = MagicMock()
        mock_par2_manager_class.return_value = mock_par2_manager

        par2_files = [
            temp_output_dir / "test.par2",
            temp_output_dir / "test.vol000+01.par2",
        ]
        mock_par2_manager.create_recovery_files.return_value = par2_files
        mock_par2_manager.verify_recovery_data.return_value = True

        progress_tracker = MagicMock()

        result_files = archiver._generate_and_verify_par2_files(
            archive_path=archive_path, progress_tracker=progress_tracker
        )

        assert result_files == par2_files
        mock_par2_manager.create_recovery_files.assert_called_once()
        mock_par2_manager.verify_recovery_data.assert_called_once()

    @patch("coldpack.core.archiver.PAR2Manager")
    def test_generate_and_verify_par2_files_failure(
        self, mock_par2_manager_class, archiver, temp_output_dir
    ):
        """Test PAR2 file generation failure."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive")

        # Mock PAR2 manager to raise exception
        mock_par2_manager = MagicMock()
        mock_par2_manager_class.return_value = mock_par2_manager
        mock_par2_manager.create_recovery_files.side_effect = Exception(
            "PAR2 creation failed"
        )

        progress_tracker = MagicMock()

        with pytest.raises(
            ArchivingError, match="Failed to generate PAR2 recovery files"
        ):
            archiver._generate_and_verify_par2_files(
                archive_path=archive_path, progress_tracker=progress_tracker
            )

    def test_create_metadata_basic(self, archiver, temp_source_dir, temp_output_dir):
        """Test basic metadata creation."""
        archive_path = temp_output_dir / "test.7z"
        archive_path.write_bytes(b"dummy archive content")

        created_files = [archive_path]
        original_size = 1000
        compressed_size = 500

        metadata = archiver._create_metadata(
            source_path=temp_source_dir,
            archive_path=archive_path,
            created_files=created_files,
            original_size=original_size,
            compressed_size=compressed_size,
        )

        assert metadata is not None
        assert metadata.source_path == temp_source_dir
        assert metadata.archive_path == archive_path
        assert metadata.original_size == original_size
        assert metadata.compressed_size == compressed_size

    def test_organize_output_files_creates_structure(self, archiver, temp_output_dir):
        """Test that organize_output_files creates proper directory structure."""
        archive_name = "test_archive"
        all_files = [
            temp_output_dir / "test.7z",
            temp_output_dir / "test.sha256",
            temp_output_dir / "test.par2",
        ]

        # Create the files
        for file_path in all_files:
            file_path.write_text("dummy content")

        result_files = archiver._organize_output_files(
            output_dir=temp_output_dir, archive_name=archive_name, all_files=all_files
        )

        # Should create organized structure
        archive_dir = temp_output_dir / archive_name
        assert archive_dir.exists()

        # All files should be moved to archive directory
        assert len(result_files) == len(all_files)
        for result_file in result_files:
            assert result_file.parent == archive_dir
            assert result_file.exists()


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
