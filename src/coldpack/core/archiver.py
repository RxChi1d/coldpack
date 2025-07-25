"""Main cold storage archiver that coordinates the entire archiving pipeline."""

from pathlib import Path
from typing import Any, Optional, Union

from loguru import logger

from ..config.constants import (
    DEFAULT_OUTPUT_FORMAT,
    SUPPORTED_OUTPUT_FORMATS,
)
from ..config.settings import (
    ArchiveMetadata,
    PAR2Settings,
    ProcessingOptions,
    SevenZipSettings,
)
from ..utils.filesystem import (
    check_disk_space,
    create_temp_directory,
    format_file_size,
    get_file_size,
    safe_file_operations,
)
from ..utils.hashing import compute_file_hashes, generate_hash_files
from ..utils.par2 import PAR2Manager
from ..utils.progress import ProgressTracker
from ..utils.sevenzip import SevenZipCompressor, optimize_7z_compression_settings
from .extractor import MultiFormatExtractor
from .repairer import ArchiveRepairer
from .verifier import ArchiveVerifier


class ArchivingError(Exception):
    """Base exception for archiving operations."""

    pass


class ArchiveResult:
    """Result of an archive operation."""

    def __init__(
        self,
        success: bool,
        metadata: Optional[ArchiveMetadata] = None,
        message: str = "",
        created_files: Optional[list[Path]] = None,
        error_details: Optional[str] = None,
    ):
        """Initialize archive result.

        Args:
            success: Whether operation was successful
            metadata: Archive metadata
            message: Result message
            created_files: List of files created during operation
            error_details: Detailed error information
        """
        self.success = success
        self.metadata = metadata
        self.message = message
        self.created_files = created_files or []
        self.error_details = error_details

    def __str__(self) -> str:
        """String representation of the result."""
        status = "SUCCESS" if self.success else "FAILED"
        return f"Archive {status}: {self.message}"


class ColdStorageArchiver:
    """Main cold storage archiver implementing the complete pipeline."""

    def __init__(
        self,
        processing_options: Optional[ProcessingOptions] = None,
        par2_settings: Optional[PAR2Settings] = None,
        sevenzip_settings: Optional[SevenZipSettings] = None,
    ):
        """Initialize the cold storage archiver.

        Args:
            processing_options: Processing options
            par2_settings: PAR2 configuration
            sevenzip_settings: 7z compression configuration
        """
        self.sevenzip_settings = sevenzip_settings or SevenZipSettings()
        self.processing_options = processing_options or ProcessingOptions()
        self.par2_settings = par2_settings or PAR2Settings()

        # Initialize components
        self.extractor = MultiFormatExtractor()
        self.verifier = ArchiveVerifier()
        self.repairer = ArchiveRepairer()

        # Initialize 7z compressor
        self.sevenzip_compressor = SevenZipCompressor(self.sevenzip_settings)

        # Progress tracking
        self.progress_tracker: Optional[ProgressTracker] = None

        # Log initialization
        sevenzip_level = (
            self.sevenzip_settings.level if self.sevenzip_settings else "N/A"
        )
        logger.debug(f"ColdStorageArchiver initialized with 7z level {sevenzip_level}")

    def create_archive(
        self,
        source: Union[str, Path],
        output_dir: Union[str, Path],
        archive_name: Optional[str] = None,
        format: str = DEFAULT_OUTPUT_FORMAT,
    ) -> ArchiveResult:
        """Create a complete cold storage archive with comprehensive verification.

        Args:
            source: Path to source file/directory/archive
            output_dir: Directory to create archive in
            archive_name: Custom archive name (defaults to source name)
            format: Archive format (7z only)

        Returns:
            Archive result with metadata and created files

        Raises:
            FileNotFoundError: If source doesn't exist
            ArchivingError: If archiving fails
            ValueError: If format is not supported
        """
        source_path = Path(source)
        output_path = Path(output_dir)

        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")

        # Validate format
        if format not in SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(
                f"Unsupported format: {format}. Supported formats: {SUPPORTED_OUTPUT_FORMATS}"
            )

        # Determine archive name
        if archive_name is None:
            archive_name = self._get_clean_archive_name(source_path)

        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)

        # Check for existing archive directory (not just the archive file)
        # The complete archive structure is: output_path/archive_name/
        archive_dir = output_path / archive_name

        if archive_dir.exists():
            if not self.processing_options.force_overwrite:
                raise ArchivingError(
                    f"Archive directory already exists: {archive_dir}. Use --force to overwrite."
                )
            else:
                # Force overwrite: remove existing directory structure
                logger.info(f"Removing existing archive directory: {archive_dir}")
                import shutil

                shutil.rmtree(archive_dir)
                logger.success("Successfully removed existing archive directory")

        # Check disk space
        try:
            check_disk_space(output_path)
        except Exception as e:
            raise ArchivingError(f"Insufficient disk space: {e}") from e

        logger.info(f"Creating cold storage archive: {archive_name}")
        # logger.info(f"Format: {format}")
        logger.info(f"Source: {source_path}")
        logger.info(f"Output: {output_path}")

        # Record processing start time for metadata
        import time

        processing_start_time = time.time()

        with safe_file_operations(self.processing_options.cleanup_on_error) as safe_ops:
            try:
                # Create progress tracker
                if self.processing_options.progress_callback:
                    self.progress_tracker = ProgressTracker()
                    self.progress_tracker.start()

                # Step 1: Extract/prepare source content
                extracted_dir = self._extract_source(source_path, safe_ops)

                # Step 2: Create archive based on format
                if format == "7z":
                    # Step 2a: Create final directory structure first for 7z
                    archive_dir, metadata_dir = (
                        self._create_final_directory_structure_early(
                            output_path, archive_name, safe_ops
                        )
                    )

                    # Step 2b: Create 7z archive directly in final location
                    archive_path = self._create_7z_archive(
                        extracted_dir, archive_dir, archive_name, safe_ops
                    )

                # Step 3: Directory structure was already created and file is in final location
                final_archive_path = archive_path

                # Step 5: Generate dual hash files directly in metadata directory
                hash_files = self._generate_hash_files(
                    final_archive_path, metadata_dir, safe_ops
                )

                # Step 6: Verify hash files
                if self.processing_options.verify_integrity:
                    self._verify_hash_files(final_archive_path, hash_files)

                # Step 7: Generate PAR2 recovery files directly in metadata directory
                par2_files = []
                if self.processing_options.generate_par2:
                    par2_files = self._generate_par2_files(
                        final_archive_path, metadata_dir, safe_ops
                    )

                # Step 8: Final verification with files in final locations
                if self.processing_options.verify_integrity:
                    self._perform_final_verification(
                        final_archive_path, hash_files, par2_files
                    )

                # Prepare organized files info for metadata creation
                organized_files = {
                    "archive": final_archive_path,
                    "hash_files": hash_files,
                    "par2_files": par2_files,
                    "archive_dir": archive_dir,
                    "metadata_dir": metadata_dir,
                }

                # Step 9: Create comprehensive metadata
                metadata = self._create_metadata(
                    source_path,
                    final_archive_path,
                    extracted_dir,
                    hash_files,
                    par2_files,
                    processing_start_time,
                )

                # Step 10: Generate metadata.toml file
                metadata_file = metadata_dir / "metadata.toml"
                metadata.save_to_toml(metadata_file)
                safe_ops.track_file(metadata_file)
                organized_files["metadata_file"] = metadata_file

                # Collect all created files
                created_files = (
                    [final_archive_path]
                    + list(hash_files.values())
                    + par2_files
                    + [metadata_file]
                )

                logger.success("Cold storage archive created successfully")

                return ArchiveResult(
                    success=True,
                    metadata=metadata,
                    message=f"Archive created: {final_archive_path.name}",
                    created_files=created_files,
                )

            except ArchivingError:
                # Re-raise ArchivingError for proper error handling
                raise
            except Exception as e:
                logger.error(f"Archive creation failed: {e}")
                return ArchiveResult(
                    success=False,
                    message=f"Archive creation failed: {e}",
                    error_details=str(e),
                )

            finally:
                if self.progress_tracker:
                    self.progress_tracker.stop()

    # ---------------------------------------------------------------------
    # Archive naming helpers
    # ---------------------------------------------------------------------
    def _get_clean_archive_name(self, source_path: Path) -> str:
        """Get clean archive name by removing known archive extensions.

        Handles compound extensions like .tar.xz, .tar.bz2, .tar.gz correctly
        to avoid duplicate .tar in the final archive name.

        Args:
            source_path: Path to source file or directory

        Returns:
            Clean archive name without archive extensions

        Examples:
            source-name.tar.xz → source-name
            source-name.tar.bz2 → source-name
            source-name.7z → source-name
            source-name/ → source-name
        """
        if source_path.is_dir():
            return source_path.name

        # Known compound archive extensions that should be fully stripped
        compound_extensions = [
            ".tar.gz",
            ".tar.bz2",
            ".tar.xz",
            ".tar.lz",
            ".tar.lzma",
            ".tar.Z",
            ".tar.zst",
            ".tar.lz4",
        ]

        # Check for compound extensions first
        name_lower = source_path.name.lower()
        for ext in compound_extensions:
            if name_lower.endswith(ext):
                return source_path.name[: -len(ext)]

        # Single archive extensions
        single_extensions = [
            ".7z",
            ".zip",
            ".rar",
            ".gz",
            ".bz2",
            ".xz",
            ".lz",
            ".lzma",
            ".Z",
            ".zst",
            ".lz4",
            ".tar",
        ]

        # Check for single extensions
        for ext in single_extensions:
            if name_lower.endswith(ext):
                return source_path.name[: -len(ext)]

        # No known archive extension, use stem
        return source_path.stem

    def _extract_source(self, source_path: Path, safe_ops: Any) -> Path:
        """Extract source content to temporary directory.

        Args:
            source_path: Path to source
            safe_ops: Safe file operations context

        Returns:
            Path to extracted content directory
        """
        logger.info("Step 1: Extracting/preparing source content")

        if source_path.is_dir():
            # Source is already a directory
            logger.debug(f"Source is directory: {source_path}")
            return source_path
        else:
            # Source is an archive, extract it
            temp_dir = create_temp_directory(suffix="_extract")
            safe_ops.track_directory(temp_dir)

            logger.debug(f"Extracting {source_path} to {temp_dir}")
            extracted_dir = self.extractor.extract(source_path, temp_dir)

            # Extraction already logged in extractor
            logger.debug(f"Extraction complete: {extracted_dir}")
            return extracted_dir

    def _create_7z_archive(
        self, source_dir: Path, archive_dir: Path, archive_name: str, safe_ops: Any
    ) -> Path:
        """Create 7z archive using SevenZipCompressor directly in final location.

        Args:
            source_dir: Directory to archive
            archive_dir: Final archive directory where 7z file will be created
            archive_name: Archive name
            safe_ops: Safe file operations context

        Returns:
            Path to created 7z archive
        """
        logger.info("Step 2b: Creating 7z archive with dynamic optimization")

        # Calculate source directory size for optimization
        source_size = sum(
            f.stat().st_size for f in source_dir.rglob("*") if f.is_file()
        )
        logger.debug(f"Source directory size: {format_file_size(source_size)}")

        # Check if settings are manually configured
        if self.sevenzip_settings.manual_settings:
            # Use manual settings without optimization
            threads_display = (
                "all"
                if self.sevenzip_settings.threads == 0
                else str(self.sevenzip_settings.threads)
            )
            logger.info(
                f"Using manual 7z settings: level={self.sevenzip_settings.level}, "
                f"dict={self.sevenzip_settings.dictionary_size}, threads={threads_display}"
            )
            # Keep existing settings and compressor
        else:
            # Optimize 7z compression settings based on source size
            optimized_settings = optimize_7z_compression_settings(
                source_size, self.sevenzip_settings.threads
            )
            # Note: the optimize function already logs the optimized settings

            # Update sevenzip_compressor with optimized settings
            self.sevenzip_compressor = SevenZipCompressor(optimized_settings)
            self.sevenzip_settings = optimized_settings

        # Create 7z archive path directly in final location
        archive_path = archive_dir / f"{archive_name}.7z"

        # Check if archive file already exists
        if archive_path.exists() and not self.processing_options.force_overwrite:
            raise ArchivingError(
                f"Archive already exists: {archive_path}. Use --force to overwrite."
            )

        safe_ops.track_file(archive_path)

        try:
            # Create progress callback if needed
            progress_callback = None
            if self.progress_tracker:

                def progress_update(percentage: int, current_file: str) -> None:
                    if self.progress_tracker is not None:
                        self.progress_tracker.update_task(
                            "compression",
                            completed=percentage,
                            current_file=current_file,
                        )

                progress_callback = progress_update

            # Perform 7z compression using py7zz
            self.sevenzip_compressor.compress_directory(
                source_dir, archive_path, progress_callback
            )

            # Verify 7z archive was created
            if not archive_path.exists():
                raise ArchivingError("7z archive file was not created")

            archive_size = get_file_size(archive_path)
            logger.success(
                f"Successfully compressed to {archive_path} ({format_file_size(archive_size)})"
            )

            # Verify 7z integrity
            if self.processing_options.verify_integrity:
                self._verify_7z_integrity(archive_path)

            return archive_path

        except Exception as e:
            raise ArchivingError(f"7z archive creation failed: {e}") from e

    def _verify_7z_integrity(self, archive_path: Path) -> None:
        """Verify 7z archive integrity.

        Args:
            archive_path: Path to 7z archive
        """
        logger.debug("Step 2a: Verifying 7z integrity")

        try:
            result = self.verifier.verify_7z_integrity(archive_path)
            if not result.success:
                raise ArchivingError(f"7z verification failed: {result.message}")

            logger.success("7z integrity verification passed")

        except Exception as e:
            raise ArchivingError(f"7z integrity verification failed: {e}") from e

    def _generate_hash_files(
        self, archive_path: Path, metadata_dir: Path, safe_ops: Any
    ) -> dict[str, Path]:
        """Generate dual hash files directly in metadata directory.

        Args:
            archive_path: Path to archive
            metadata_dir: Path to metadata directory where hash files should be created
            safe_ops: Safe file operations context

        Returns:
            Dictionary of algorithm names to hash file paths
        """
        logger.info("Step 5: Generating dual hash files (SHA-256 + BLAKE3)")

        try:
            # Compute hashes
            hashes = compute_file_hashes(archive_path)

            # Generate hash files directly in metadata directory
            hash_files = generate_hash_files(
                archive_path, hashes, output_dir=metadata_dir
            )

            # Track files for cleanup on error
            for hash_file in hash_files.values():
                safe_ops.track_file(hash_file)

            logger.success(f"Generated {len(hash_files)} hash files")
            return hash_files

        except Exception as e:
            raise ArchivingError(f"Hash file generation failed: {e}") from e

    def _verify_hash_files(
        self, archive_path: Path, hash_files: dict[str, Path]
    ) -> None:
        """Verify hash files against archive.

        Args:
            archive_path: Path to archive
            hash_files: Dictionary of hash files
        """
        logger.info("Step 6: Verifying hash files")

        try:
            results = self.verifier.verify_hash_files(archive_path, hash_files)

            # Check if all hash verifications passed
            failed_results = [r for r in results if not r.success]
            if failed_results:
                failed_algorithms = [
                    r.layer.replace("_hash", "").upper() for r in failed_results
                ]
                raise ArchivingError(
                    f"Hash verification failed for: {', '.join(failed_algorithms)}"
                )

            # Log success for individual algorithms
            for result in results:
                algorithm = result.layer.replace("_hash", "").upper()
                logger.success(f"{algorithm} hash verification passed")

        except Exception as e:
            raise ArchivingError(f"Hash verification failed: {e}") from e

    def _generate_par2_files(
        self, archive_path: Path, metadata_dir: Path, safe_ops: Any
    ) -> list[Path]:
        """Generate PAR2 recovery files directly in metadata directory.

        Args:
            archive_path: Path to archive
            metadata_dir: Path to metadata directory where PAR2 files should be created
            safe_ops: Safe file operations context

        Returns:
            List of created PAR2 file paths
        """
        logger.info(
            f"Step 7: Generating PAR2 recovery files ({self.processing_options.par2_redundancy}%)"
        )

        try:
            par2_manager = PAR2Manager(self.processing_options.par2_redundancy)
            par2_files = par2_manager.create_recovery_files(
                archive_path, output_dir=metadata_dir
            )

            # Track files for cleanup on error
            for par2_file in par2_files:
                safe_ops.track_file(par2_file)

            logger.success(f"Generated {len(par2_files)} PAR2 recovery files")
            return par2_files

        except Exception as e:
            raise ArchivingError(f"PAR2 generation failed: {e}") from e

    def _create_final_directory_structure_early(
        self, output_base: Path, archive_name: str, safe_ops: Any
    ) -> tuple[Path, Path]:
        """Create the final directory structure early for 7z format.

        Args:
            output_base: Base output directory
            archive_name: Name of the archive
            safe_ops: Safe file operations context

        Returns:
            Tuple of (archive_dir, metadata_dir) paths
        """
        logger.info("Step 2a: Creating final directory structure")

        # Create directory structure
        archive_dir = output_base / archive_name
        metadata_dir = archive_dir / "metadata"

        archive_dir.mkdir(exist_ok=True)
        metadata_dir.mkdir(exist_ok=True)
        safe_ops.track_directory(archive_dir)
        safe_ops.track_directory(metadata_dir)

        logger.success(f"Created directory structure: {archive_dir}")
        return archive_dir, metadata_dir

    def _perform_final_verification(
        self, archive_path: Path, hash_files: dict[str, Path], par2_files: list[Path]
    ) -> None:
        """Perform final 5-layer verification.

        Args:
            archive_path: Path to archive
            hash_files: Dictionary of hash files
            par2_files: List of PAR2 files
        """
        logger.info("Step 8: Performing final 5-layer verification")

        try:
            results = self.verifier.verify_auto(archive_path)

            # Check if all layers passed
            failed_layers = [r for r in results if not r.success]
            if failed_layers:
                failed_names = [r.layer for r in failed_layers]
                raise ArchivingError(
                    f"Final verification failed for layers: {', '.join(failed_names)}"
                )

            logger.success("Final 4-layer verification passed")

        except Exception as e:
            raise ArchivingError(f"Final verification failed: {e}") from e

    def _organize_output_files(
        self,
        archive_path: Path,
        hash_files: dict[str, Path],
        par2_files: list[Path],
        archive_name: str,
        safe_ops: Any,
    ) -> dict:
        """Organize output files into proper directory structure.

        Creates structure:
        output_dir/
        └── archive_name/
            ├── archive_name.tar.zst
            └── metadata/
                ├── archive_name.tar.zst.sha256
                ├── archive_name.tar.zst.blake3
                ├── archive_name.tar.zst.par2
                └── archive_name.tar.zst.vol000+xxx.par2

        Args:
            archive_path: Current archive file path
            hash_files: Dictionary of hash files
            par2_files: List of PAR2 files
            archive_name: Name of the archive
            safe_ops: Safe file operations context

        Returns:
            Dictionary with organized file paths
        """
        logger.info("Step 11: Organizing files into proper structure")

        # Create directory structure
        output_base = archive_path.parent
        archive_dir = output_base / archive_name
        metadata_dir = archive_dir / "metadata"

        archive_dir.mkdir(exist_ok=True)
        metadata_dir.mkdir(exist_ok=True)
        safe_ops.track_directory(archive_dir)
        safe_ops.track_directory(metadata_dir)

        # Move archive file to archive directory
        new_archive_path = archive_dir / archive_path.name
        archive_path.rename(new_archive_path)
        safe_ops.track_file(new_archive_path)

        # Move hash files to metadata directory
        new_hash_files = {}
        for algorithm, hash_file_path in hash_files.items():
            new_hash_path = metadata_dir / hash_file_path.name
            hash_file_path.rename(new_hash_path)
            safe_ops.track_file(new_hash_path)
            new_hash_files[algorithm] = new_hash_path

        # Move PAR2 files to metadata directory
        new_par2_files = []
        for par2_file in par2_files:
            new_par2_path = metadata_dir / par2_file.name
            par2_file.rename(new_par2_path)
            safe_ops.track_file(new_par2_path)
            new_par2_files.append(new_par2_path)

        logger.success(f"Files organized into: {archive_dir}")
        logger.info(f"Archive: {new_archive_path}")
        logger.info(
            f"Metadata: {metadata_dir} ({len(new_hash_files) + len(new_par2_files)} files)"
        )

        return {
            "archive": new_archive_path,
            "hash_files": new_hash_files,
            "par2_files": new_par2_files,
            "archive_dir": archive_dir,
            "metadata_dir": metadata_dir,
        }

    def _create_metadata(
        self,
        source_path: Path,
        archive_path: Path,
        extracted_dir: Path,
        hash_files: dict[str, Path],
        par2_files: list[Path],
        processing_start_time: Optional[float] = None,
    ) -> ArchiveMetadata:
        """Create comprehensive archive metadata with complete configuration preservation.

        Args:
            source_path: Original source path
            archive_path: Created archive path
            extracted_dir: Extracted content directory
            hash_files: Dictionary of hash files {algorithm: path}
            par2_files: List of PAR2 files
            processing_start_time: Start time for calculating processing duration

        Returns:
            Complete archive metadata object with format-aware settings
        """
        import time

        try:
            # Calculate sizes
            if source_path.is_file():
                original_size = get_file_size(source_path)
            else:
                original_size = sum(
                    f.stat().st_size for f in extracted_dir.rglob("*") if f.is_file()
                )
            compressed_size = get_file_size(archive_path)

            # Count files and directories
            file_count = sum(1 for f in extracted_dir.rglob("*") if f.is_file())
            directory_count = sum(1 for f in extracted_dir.rglob("*") if f.is_dir())

            # Analyze directory structure
            has_single_root = False
            root_directory = None
            top_level_items = list(extracted_dir.iterdir())
            if len(top_level_items) == 1 and top_level_items[0].is_dir():
                has_single_root = True
                root_directory = top_level_items[0].name

            # Create verification hashes dictionary
            verification_hashes = {}
            for algorithm, hash_file_path in hash_files.items():
                try:
                    with open(hash_file_path, encoding="utf-8") as f:
                        hash_line = f.readline().strip()
                        # Handle different hash file formats
                        if "  " in hash_line:
                            hash_value = hash_line.split("  ")[0]
                        else:
                            hash_value = hash_line.split()[0]
                        verification_hashes[algorithm] = hash_value
                except Exception as e:
                    logger.warning(f"Could not read {algorithm} hash file: {e}")

            # Create hash files mapping (algorithm -> filename)
            hash_files_dict = {
                algorithm: str(hash_file_path.name)
                for algorithm, hash_file_path in hash_files.items()
            }

            # Calculate processing time
            processing_time = 0.0
            if processing_start_time:
                processing_time = time.time() - processing_start_time

            # Determine archive format and name (7z only)
            archive_format = "7z"

            # Get archive name (without extension)
            archive_name = archive_path.stem

            # Set 7z settings
            sevenzip_settings = self.sevenzip_settings

            # Create comprehensive metadata
            metadata = ArchiveMetadata(
                # Core identification
                source_path=source_path,
                archive_path=archive_path,
                archive_name=archive_name,
                # Archive format
                archive_format=archive_format,
                # Version and creation (will be auto-populated by model_post_init)
                coldpack_version="1.0.0-dev",
                # Processing settings
                sevenzip_settings=sevenzip_settings,
                par2_settings=self.par2_settings,
                # Content statistics
                file_count=file_count,
                directory_count=directory_count,
                original_size=original_size,
                compressed_size=compressed_size,
                # Archive structure
                has_single_root=has_single_root,
                root_directory=root_directory,
                # Integrity verification
                verification_hashes=verification_hashes,
                hash_files=hash_files_dict,
                par2_files=[str(f.name) for f in par2_files],
                # Processing details
                processing_time_seconds=processing_time,
                temp_directory_used=str(extracted_dir.parent)
                if extracted_dir.parent
                else None,
            )

            logger.info(f"Created comprehensive metadata for {archive_name}")
            logger.info(
                f"Files: {file_count}, Directories: {directory_count}, Size: {format_file_size(original_size)}"
            )

            return metadata

        except Exception as e:
            logger.warning(f"Could not create complete metadata: {e}")
            # Return minimal metadata for backward compatibility
            return ArchiveMetadata(
                source_path=source_path,
                archive_path=archive_path,
                archive_name=archive_path.stem,
                sevenzip_settings=self.sevenzip_settings,
                par2_settings=self.par2_settings,
            )


def create_cold_storage_archive(
    source: Union[str, Path],
    output_dir: Union[str, Path],
    archive_name: Optional[str] = None,
    compression_level: int = 5,
    verify: bool = True,
    generate_par2: bool = True,
) -> ArchiveResult:
    """Convenience function to create a cold storage archive.

    Args:
        source: Path to source file/directory/archive
        output_dir: Directory to create archive in
        archive_name: Custom archive name
        compression_level: 7z compression level (1-9)
        verify: Whether to perform verification
        generate_par2: Whether to generate PAR2 recovery files

    Returns:
        Archive result
    """
    sevenzip_settings = SevenZipSettings(level=compression_level)
    processing_options = ProcessingOptions(
        verify_integrity=verify, generate_par2=generate_par2
    )

    archiver = ColdStorageArchiver(
        processing_options, sevenzip_settings=sevenzip_settings
    )
    return archiver.create_archive(source, output_dir, archive_name)
