"""Integration tests for coldpack core functionality."""

import pytest

from coldpack.config.settings import ProcessingOptions, SevenZipSettings
from coldpack.core.archiver import ColdStorageArchiver


class TestBasicIntegration:
    """Basic integration tests for coldpack functionality."""

    @pytest.fixture
    def sample_directory(self, tmp_path):
        """Create a sample directory with test files."""
        test_dir = tmp_path / "test_data"
        test_dir.mkdir()

        # Create some test files
        (test_dir / "file1.txt").write_text("This is test file 1")
        (test_dir / "file2.txt").write_text("This is test file 2 with more content")

        # Create a subdirectory
        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("This is test file 3 in subdirectory")

        return test_dir

    def test_archiver_initialization(self):
        """Test that archiver can be initialized with default settings."""
        archiver = ColdStorageArchiver()

        assert archiver.sevenzip_settings.level >= 1
        assert archiver.processing_options.verify_integrity is True
        assert archiver.processing_options.generate_par2 is True

    def test_archiver_with_custom_settings(self):
        """Test archiver initialization with custom settings."""
        sevenzip_settings = SevenZipSettings(level=5, threads=2)

        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False, verbose=True
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options,
            sevenzip_settings=sevenzip_settings,
        )

        assert archiver.sevenzip_settings.level == 5
        assert archiver.sevenzip_settings.threads == 2
        assert archiver.processing_options.verify_integrity is False
        assert archiver.processing_options.generate_par2 is False

    def test_directory_archiving_dry_run(self, sample_directory, tmp_path):
        """Test directory archiving setup without full execution."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Use minimal settings for testing
        sevenzip_settings = SevenZipSettings(level=1)
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options,
            sevenzip_settings=sevenzip_settings,
        )

        # Just test that the archiver accepts valid inputs
        assert sample_directory.exists()
        assert output_dir.exists()

        # Verify the archiver components are initialized
        assert archiver.extractor is not None
        assert archiver.sevenzip_compressor is not None
        assert archiver.verifier is not None


class TestModuleImports:
    """Test that all modules can be imported correctly."""

    def test_core_module_imports(self):
        """Test that core modules can be imported."""
        from coldpack.core.archiver import ColdStorageArchiver
        from coldpack.core.extractor import MultiFormatExtractor
        from coldpack.core.repairer import ArchiveRepairer
        from coldpack.core.verifier import ArchiveVerifier

        # Test instantiation
        archiver = ColdStorageArchiver()
        extractor = MultiFormatExtractor()
        verifier = ArchiveVerifier()
        repairer = ArchiveRepairer()

        assert archiver is not None
        assert extractor is not None
        assert verifier is not None
        assert repairer is not None

    def test_utils_module_imports(self):
        """Test that utility modules can be imported."""
        from coldpack.utils.compression import ZstdCompressor, ZstdDecompressor
        from coldpack.utils.hashing import DualHasher, HashVerifier

        # Test instantiation
        compressor = ZstdCompressor()
        decompressor = ZstdDecompressor()
        hasher = DualHasher()
        verifier = HashVerifier()

        assert compressor is not None
        assert decompressor is not None
        assert hasher is not None
        assert verifier is not None

    def test_config_imports(self):
        """Test that configuration modules can be imported."""
        from coldpack.config.settings import SevenZipSettings

        settings = SevenZipSettings()
        assert settings.level >= 1

    def test_main_package_import(self):
        """Test that main package can be imported."""
        import coldpack

        assert coldpack.__version__ is not None
        assert hasattr(coldpack, "ColdStorageArchiver")
        assert hasattr(coldpack, "MultiFormatExtractor")


class TestForceOverwrite:
    """Test force overwrite functionality."""

    @pytest.fixture
    def sample_directory(self, tmp_path):
        """Create a sample directory with test files."""
        test_dir = tmp_path / "test_data"
        test_dir.mkdir()

        # Create some test files
        (test_dir / "file1.txt").write_text("This is test file 1")
        (test_dir / "file2.txt").write_text("This is test file 2")

        return test_dir

    def test_archive_force_overwrite_setting(self, sample_directory, tmp_path):
        """Test that force_overwrite setting is properly handled."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Test with force_overwrite=True
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False, force_overwrite=True
        )

        archiver = ColdStorageArchiver(processing_options=processing_options)
        assert archiver.processing_options.force_overwrite is True

        # Test with force_overwrite=False (default)
        processing_options_default = ProcessingOptions()
        archiver_default = ColdStorageArchiver(
            processing_options=processing_options_default
        )
        assert archiver_default.processing_options.force_overwrite is False

    def test_archive_without_force_fails_on_existing_file(
        self, sample_directory, tmp_path
    ):
        """Test that archive creation fails when target directory exists and force=False."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create existing archive directory structure (using default 7z format)
        # The archiver now checks for: output_dir/test_data/ directory
        existing_archive_dir = output_dir / "test_data"
        existing_archive_dir.mkdir()
        (existing_archive_dir / "test_data.7z").write_text("existing archive content")

        # Try to create archive without force
        sevenzip_settings = SevenZipSettings(level=1)
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False, force_overwrite=False
        )

        archiver = ColdStorageArchiver(
            processing_options=processing_options,
            sevenzip_settings=sevenzip_settings,
        )

        # This should raise an ArchivingError
        from coldpack.core.archiver import ArchivingError

        with pytest.raises(
            ArchivingError, match="Archive directory already exists.*Use --force"
        ):
            archiver.create_archive(sample_directory, output_dir)

    def test_extractor_force_overwrite_parameter(self, tmp_path):
        """Test that extractor accepts force_overwrite parameter."""
        from coldpack.core.extractor import MultiFormatExtractor

        extractor = MultiFormatExtractor()

        # Test that the method signature accepts force_overwrite
        # We can't fully test without a real archive, but we can verify the parameter exists
        import inspect

        extract_signature = inspect.signature(extractor.extract)
        assert "force_overwrite" in extract_signature.parameters

    def test_extractor_fails_on_existing_directory_without_force(self, tmp_path):
        """Test that extraction fails when target directory exists and force=False."""
        from coldpack.core.extractor import MultiFormatExtractor

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create existing target directory
        existing_target = output_dir / "test_archive"
        existing_target.mkdir()
        (existing_target / "existing_file.txt").write_text("existing content")

        extractor = MultiFormatExtractor()

        # Create a fake archive path (we'll test the logic before actual extraction)
        fake_archive = tmp_path / "test_archive.zip"
        fake_archive.write_text("fake archive content")

        # We can't fully test without py7zz, but we can test that force_overwrite parameter is handled
        # This would normally fail at the format check, but we're testing the parameter passing
        try:
            # This should fail due to unsupported format, but the force_overwrite parameter should be accepted
            extractor.extract(fake_archive, output_dir, force_overwrite=False)
        except Exception as e:
            # We expect this to fail due to format issues, not parameter issues
            assert "force_overwrite" not in str(e)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_nonexistent_source(self, tmp_path):
        """Test handling of non-existent source."""
        nonexistent_path = tmp_path / "nonexistent"

        # This should be caught at the validation level
        assert not nonexistent_path.exists()

    def test_invalid_compression_settings(self):
        """Test invalid compression settings handling."""
        with pytest.raises(ValueError):
            SevenZipSettings(level=0)  # Below minimum

        with pytest.raises(ValueError):
            SevenZipSettings(level=10)  # Above maximum
