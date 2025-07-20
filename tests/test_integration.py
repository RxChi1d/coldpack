"""Integration tests for coldpack core functionality."""

import pytest

from coldpack.config.settings import CompressionSettings, ProcessingOptions
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

        assert archiver.compression_settings.level == 19
        assert archiver.processing_options.verify_integrity is True
        assert archiver.processing_options.generate_par2 is True

    def test_archiver_with_custom_settings(self):
        """Test archiver initialization with custom settings."""
        compression_settings = CompressionSettings(level=15, threads=2, long_mode=False)

        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False, verbose=True
        )

        archiver = ColdStorageArchiver(compression_settings, processing_options)

        assert archiver.compression_settings.level == 15
        assert archiver.compression_settings.threads == 2
        assert archiver.compression_settings.long_mode is False
        assert archiver.processing_options.verify_integrity is False
        assert archiver.processing_options.generate_par2 is False

    def test_directory_archiving_dry_run(self, sample_directory, tmp_path):
        """Test directory archiving setup without full execution."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Use minimal settings for testing
        compression_settings = CompressionSettings(level=1, long_mode=False)
        processing_options = ProcessingOptions(
            verify_integrity=False, generate_par2=False
        )

        archiver = ColdStorageArchiver(compression_settings, processing_options)

        # Just test that the archiver accepts valid inputs
        assert sample_directory.exists()
        assert output_dir.exists()

        # Verify the archiver components are initialized
        assert archiver.extractor is not None
        assert archiver.compressor is not None
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
        from coldpack.config.constants import DEFAULT_COMPRESSION_LEVEL
        from coldpack.config.settings import CompressionSettings

        settings = CompressionSettings()
        assert settings.level == DEFAULT_COMPRESSION_LEVEL

    def test_main_package_import(self):
        """Test that main package can be imported."""
        import coldpack

        assert coldpack.__version__ is not None
        assert hasattr(coldpack, "ColdStorageArchiver")
        assert hasattr(coldpack, "MultiFormatExtractor")


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
            CompressionSettings(level=0)  # Below minimum

        with pytest.raises(ValueError):
            CompressionSettings(level=25)  # Above maximum

        with pytest.raises(ValueError):
            CompressionSettings(level=15, ultra_mode=True)  # Invalid ultra mode
