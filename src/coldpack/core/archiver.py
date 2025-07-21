"""Main cold storage archiver that coordinates the entire archiving pipeline."""

import subprocess
import tarfile
from pathlib import Path
from typing import Any, Optional, Union

from loguru import logger

from ..config.constants import OUTPUT_FORMAT, TAR_FORMATS
from ..config.settings import ArchiveMetadata, CompressionSettings, ProcessingOptions
from ..utils.compression import ZstdCompressor, optimize_compression_settings
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
        compression_settings: Optional[CompressionSettings] = None,
        processing_options: Optional[ProcessingOptions] = None,
    ):
        """Initialize the cold storage archiver.

        Args:
            compression_settings: Compression configuration
            processing_options: Processing options
        """
        self.compression_settings = compression_settings or CompressionSettings()
        self.processing_options = processing_options or ProcessingOptions()

        # Initialize components
        self.extractor = MultiFormatExtractor()
        self.verifier = ArchiveVerifier()
        self.repairer = ArchiveRepairer()

        # Initialize compressor with settings
        self.compressor = ZstdCompressor(self.compression_settings)

        # Progress tracking
        self.progress_tracker: Optional[ProgressTracker] = None

        logger.debug(
            f"ColdStorageArchiver initialized with compression level {self.compression_settings.level}"
        )

    def create_archive(
        self,
        source: Union[str, Path],
        output_dir: Union[str, Path],
        archive_name: Optional[str] = None,
    ) -> ArchiveResult:
        """Create a complete cold storage archive with 5-layer verification.

        Args:
            source: Path to source file/directory/archive
            output_dir: Directory to create archive in
            archive_name: Custom archive name (defaults to source name)

        Returns:
            Archive result with metadata and created files

        Raises:
            FileNotFoundError: If source doesn't exist
            ArchivingError: If archiving fails
        """
        source_path = Path(source)
        output_path = Path(output_dir)

        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")

        # Determine archive name
        if archive_name is None:
            archive_name = source_path.stem

        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)

        # Check for existing files if not forcing overwrite
        archive_path = output_path / f"{archive_name}.tar.zst"
        if archive_path.exists() and not self.processing_options.force_overwrite:
            raise ArchivingError(
                f"Archive already exists: {archive_path}. Use --force to overwrite."
            )

        # Check disk space
        try:
            check_disk_space(output_path)
        except Exception as e:
            raise ArchivingError(f"Insufficient disk space: {e}") from e

        logger.info(f"Creating cold storage archive: {archive_name}")
        logger.info(f"Source: {source_path}")
        logger.info(f"Output: {output_path}")

        with safe_file_operations(self.processing_options.cleanup_on_error) as safe_ops:
            try:
                # Create progress tracker
                if self.processing_options.progress_callback:
                    self.progress_tracker = ProgressTracker()
                    self.progress_tracker.start()

                # Step 1: Extract/prepare source content
                extracted_dir = self._extract_source(source_path, safe_ops)

                # Step 2: Optimize compression settings based on content
                optimized_settings = self._optimize_settings(extracted_dir)
                if optimized_settings:
                    self.compression_settings = optimized_settings
                    self.compressor = ZstdCompressor(self.compression_settings)

                # Step 3: Create deterministic TAR archive
                tar_path = self._create_tar_archive(
                    extracted_dir, output_path, archive_name, safe_ops
                )

                # Step 4: Verify TAR integrity
                if self.processing_options.verify_integrity:
                    self._verify_tar_integrity(tar_path)

                # Step 5: Compress with Zstd
                archive_path = self._compress_archive(tar_path, safe_ops)

                # Step 6: Verify Zstd integrity
                if self.processing_options.verify_integrity:
                    self._verify_zstd_integrity(archive_path)

                # Step 7: Generate dual hash files
                hash_files = self._generate_hash_files(archive_path, safe_ops)

                # Step 8: Verify hash files
                if self.processing_options.verify_integrity:
                    self._verify_hash_files(archive_path, hash_files)

                # Step 9: Generate PAR2 recovery files
                par2_files = []
                if self.processing_options.generate_par2:
                    par2_files = self._generate_par2_files(archive_path, safe_ops)

                # Step 10: Final verification
                if self.processing_options.verify_integrity:
                    self._perform_final_verification(
                        archive_path, hash_files, par2_files
                    )

                # Create metadata
                metadata = self._create_metadata(
                    source_path, archive_path, extracted_dir, hash_files, par2_files
                )

                # Collect all created files
                created_files = [archive_path] + list(hash_files.values()) + par2_files

                logger.success(
                    f"Cold storage archive created successfully: {archive_path}"
                )

                return ArchiveResult(
                    success=True,
                    metadata=metadata,
                    message=f"Archive created: {archive_path.name}",
                    created_files=created_files,
                )

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

            logger.success(f"Extraction complete: {extracted_dir}")
            return extracted_dir

    def _optimize_settings(self, content_dir: Path) -> Optional[CompressionSettings]:
        """Optimize compression settings based on content.

        Args:
            content_dir: Directory containing content to analyze

        Returns:
            Optimized compression settings or None to keep current
        """
        try:
            # Estimate total size
            total_size = sum(
                f.stat().st_size for f in content_dir.rglob("*") if f.is_file()
            )

            logger.debug(f"Content analysis: {format_file_size(total_size)}")

            # Optimize settings based on size
            optimized = optimize_compression_settings(total_size)

            if optimized.level != self.compression_settings.level:
                logger.info(
                    f"Optimized compression level: {self.compression_settings.level} → {optimized.level}"
                )
                return optimized

            return None

        except Exception as e:
            logger.warning(f"Could not optimize settings: {e}")
            return None

    def _create_tar_archive(
        self, source_dir: Path, output_dir: Path, archive_name: str, safe_ops: Any
    ) -> Path:
        """Create deterministic TAR archive.

        Args:
            source_dir: Directory to archive
            output_dir: Output directory
            archive_name: Archive name
            safe_ops: Safe file operations context

        Returns:
            Path to created TAR file
        """
        logger.info("Step 2: Creating deterministic TAR archive")

        tar_path = output_dir / f"{archive_name}.tar"
        safe_ops.track_file(tar_path)

        # Try to find best TAR format
        tar_format = self._find_best_tar_format()

        try:
            if tar_format and tar_format != "python":
                # Use external tar command for better format support
                self._create_tar_with_command(source_dir, tar_path, tar_format)
            else:
                # Use Python tarfile as fallback
                self._create_tar_with_python(source_dir, tar_path)

            # Verify TAR was created
            if not tar_path.exists():
                raise ArchivingError("TAR file was not created")

            tar_size = get_file_size(tar_path)
            logger.success(
                f"TAR archive created: {tar_path} ({format_file_size(tar_size)})"
            )

            return tar_path

        except Exception as e:
            raise ArchivingError(f"TAR creation failed: {e}") from e

    def _find_best_tar_format(self) -> Optional[str]:
        """Find the best available TAR format.

        Returns:
            TAR format name or None for Python fallback
        """
        # Test external tar command availability
        try:
            result = subprocess.run(
                ["tar", "--help"], capture_output=True, text=True, timeout=5
            )

            if result.returncode == 0:
                # Check for format support
                help_text = result.stdout.lower()

                for fmt in TAR_FORMATS:
                    if fmt in help_text:
                        logger.debug(f"Using tar format: {fmt}")
                        return fmt

        except Exception:
            pass

        logger.debug("Using Python tarfile")
        return None

    def _create_tar_with_command(
        self, source_dir: Path, tar_path: Path, tar_format: str
    ) -> None:
        """Create TAR using external command.

        Args:
            source_dir: Source directory
            tar_path: Output TAR path
            tar_format: TAR format to use
        """
        cmd = [
            "tar",
            "--create",
            "--file",
            str(tar_path),
            "--format",
            tar_format,
            "--sort=name",  # Deterministic ordering
            "--directory",
            str(source_dir.parent),
            source_dir.name,
        ]

        logger.debug(f"Running: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )

        if result.returncode != 0:
            raise ArchivingError(f"tar command failed: {result.stderr}")

    def _create_tar_with_python(self, source_dir: Path, tar_path: Path) -> None:
        """Create TAR using Python tarfile.

        Args:
            source_dir: Source directory
            tar_path: Output TAR path
        """
        with tarfile.open(tar_path, "w") as tar:
            # Add files in sorted order for deterministic output
            files_to_add = sorted(source_dir.rglob("*"))

            for file_path in files_to_add:
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir.parent)
                    tar.add(file_path, arcname=arcname, recursive=False)

    def _verify_tar_integrity(self, tar_path: Path) -> None:
        """Verify TAR file integrity.

        Args:
            tar_path: Path to TAR file
        """
        logger.info("Step 3: Verifying TAR integrity")

        try:
            with tarfile.open(tar_path, "r") as tar:
                # Try to read the entire archive
                members = tar.getmembers()
                logger.debug(f"TAR contains {len(members)} members")

            logger.success("TAR integrity verification passed")

        except Exception as e:
            raise ArchivingError(f"TAR integrity verification failed: {e}") from e

    def _compress_archive(self, tar_path: Path, safe_ops: Any) -> Path:
        """Compress TAR file with Zstd.

        Args:
            tar_path: Path to TAR file
            safe_ops: Safe file operations context

        Returns:
            Path to compressed archive
        """
        logger.info("Step 4: Compressing with Zstd")

        archive_path = tar_path.with_suffix(OUTPUT_FORMAT)
        safe_ops.track_file(archive_path)

        try:
            self.compressor.compress_file(tar_path, archive_path)

            # Remove original TAR file to save space
            tar_path.unlink()

            compressed_size = get_file_size(archive_path)
            logger.success(
                f"Compression complete: {archive_path} ({format_file_size(compressed_size)})"
            )

            return archive_path

        except Exception as e:
            raise ArchivingError(f"Compression failed: {e}") from e

    def _verify_zstd_integrity(self, archive_path: Path) -> None:
        """Verify Zstd compression integrity.

        Args:
            archive_path: Path to compressed archive
        """
        logger.info("Step 5: Verifying Zstd integrity")

        try:
            result = self.verifier.verify_zstd_integrity(archive_path)
            if not result.success:
                raise ArchivingError(f"Zstd verification failed: {result.message}")

            logger.success("Zstd integrity verification passed")

        except Exception as e:
            raise ArchivingError(f"Zstd integrity verification failed: {e}") from e

    def _generate_hash_files(
        self, archive_path: Path, safe_ops: Any
    ) -> dict[str, Path]:
        """Generate dual hash files.

        Args:
            archive_path: Path to archive
            safe_ops: Safe file operations context

        Returns:
            Dictionary of algorithm names to hash file paths
        """
        logger.info("Step 6: Generating dual hash files (SHA-256 + BLAKE3)")

        try:
            # Compute hashes
            hashes = compute_file_hashes(archive_path)

            # Generate hash files
            hash_files = generate_hash_files(archive_path, hashes)

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
        logger.info("Step 7: Verifying hash files")

        try:
            result = self.verifier.verify_hash_files(archive_path, hash_files)
            if not result.success:
                raise ArchivingError(f"Hash verification failed: {result.message}")

            logger.success("Hash file verification passed")

        except Exception as e:
            raise ArchivingError(f"Hash verification failed: {e}") from e

    def _generate_par2_files(self, archive_path: Path, safe_ops: Any) -> list[Path]:
        """Generate PAR2 recovery files.

        Args:
            archive_path: Path to archive
            safe_ops: Safe file operations context

        Returns:
            List of created PAR2 file paths
        """
        logger.info(
            f"Step 8: Generating PAR2 recovery files ({self.processing_options.par2_redundancy}%)"
        )

        try:
            par2_manager = PAR2Manager(self.processing_options.par2_redundancy)
            par2_files = par2_manager.create_recovery_files(archive_path)

            # Track files for cleanup on error
            for par2_file in par2_files:
                safe_ops.track_file(par2_file)

            logger.success(f"Generated {len(par2_files)} PAR2 recovery files")
            return par2_files

        except Exception as e:
            raise ArchivingError(f"PAR2 generation failed: {e}") from e

    def _perform_final_verification(
        self, archive_path: Path, hash_files: dict[str, Path], par2_files: list[Path]
    ) -> None:
        """Perform final 5-layer verification.

        Args:
            archive_path: Path to archive
            hash_files: Dictionary of hash files
            par2_files: List of PAR2 files
        """
        logger.info("Step 9: Performing final 5-layer verification")

        try:
            par2_file = par2_files[0] if par2_files else None
            results = self.verifier.verify_complete(archive_path, hash_files, par2_file)

            # Check if all layers passed
            failed_layers = [r for r in results if not r.success]
            if failed_layers:
                failed_names = [r.layer for r in failed_layers]
                raise ArchivingError(
                    f"Final verification failed for layers: {', '.join(failed_names)}"
                )

            logger.success("Final 5-layer verification passed")

        except Exception as e:
            raise ArchivingError(f"Final verification failed: {e}") from e

    def _create_metadata(
        self,
        source_path: Path,
        archive_path: Path,
        extracted_dir: Path,
        hash_files: dict[str, Path],
        par2_files: list[Path],
    ) -> ArchiveMetadata:
        """Create archive metadata.

        Args:
            source_path: Original source path
            archive_path: Created archive path
            extracted_dir: Extracted content directory
            hash_files: Dictionary of hash files
            par2_files: List of PAR2 files

        Returns:
            Archive metadata object
        """
        try:
            # Calculate sizes
            if source_path.is_file():
                original_size = get_file_size(source_path)
            else:
                original_size = sum(
                    f.stat().st_size for f in extracted_dir.rglob("*") if f.is_file()
                )

            compressed_size = get_file_size(archive_path)

            # Count files
            file_count = sum(1 for f in extracted_dir.rglob("*") if f.is_file())

            # Create verification hashes dictionary
            verification_hashes = {}
            for algorithm, hash_file_path in hash_files.items():
                try:
                    with open(hash_file_path) as f:
                        hash_line = f.readline().strip()
                        hash_value = hash_line.split("  ")[0]
                        verification_hashes[algorithm] = hash_value
                except Exception:
                    pass

            # Create metadata
            metadata = ArchiveMetadata(
                source_path=source_path,
                archive_path=archive_path,
                compression_settings=self.compression_settings,
                file_count=file_count,
                original_size=original_size,
                compressed_size=compressed_size,
                verification_hashes=verification_hashes,
                par2_files=[str(f) for f in par2_files],
            )

            # Calculate compression ratio
            metadata.calculate_compression_ratio()

            return metadata

        except Exception as e:
            logger.warning(f"Could not create complete metadata: {e}")
            # Return minimal metadata
            return ArchiveMetadata(
                source_path=source_path,
                archive_path=archive_path,
                compression_settings=self.compression_settings,
            )


def create_cold_storage_archive(
    source: Union[str, Path],
    output_dir: Union[str, Path],
    archive_name: Optional[str] = None,
    compression_level: int = 19,
    verify: bool = True,
    generate_par2: bool = True,
) -> ArchiveResult:
    """Convenience function to create a cold storage archive.

    Args:
        source: Path to source file/directory/archive
        output_dir: Directory to create archive in
        archive_name: Custom archive name
        compression_level: Zstd compression level (1-22)
        verify: Whether to perform verification
        generate_par2: Whether to generate PAR2 recovery files

    Returns:
        Archive result
    """
    compression_settings = CompressionSettings(level=compression_level)
    processing_options = ProcessingOptions(
        verify_integrity=verify, generate_par2=generate_par2
    )

    archiver = ColdStorageArchiver(compression_settings, processing_options)
    return archiver.create_archive(source, output_dir, archive_name)
