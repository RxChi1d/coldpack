"""Main cold storage archiver that coordinates the entire archiving pipeline."""

import platform
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any, Optional, Union

from loguru import logger

from ..config.constants import OUTPUT_FORMAT
from ..config.settings import (
    ArchiveMetadata,
    CompressionSettings,
    PAR2Settings,
    ProcessingOptions,
    TarSettings,
)
from ..utils.compression import ZstdCompressor, optimize_compression_settings
from ..utils.filesystem import (
    check_disk_space,
    create_temp_directory,
    filter_files_for_archive,
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
        par2_settings: Optional[PAR2Settings] = None,
        tar_settings: Optional[TarSettings] = None,
    ):
        """Initialize the cold storage archiver.

        Args:
            compression_settings: Compression configuration
            processing_options: Processing options
            par2_settings: PAR2 configuration
            tar_settings: TAR configuration
        """
        self.compression_settings = compression_settings or CompressionSettings()
        self.processing_options = processing_options or ProcessingOptions()
        self.par2_settings = par2_settings or PAR2Settings()
        self.tar_settings = tar_settings or TarSettings()

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

        # Detect an external tar/bsdtar command that supports deterministic --sort=name
        self._external_tar_cmd: Optional[list[str]] = self._detect_tar_sort_command()
        self._tar_method = self._get_tar_method_description()

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
            archive_name = self._get_clean_archive_name(source_path)

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

                # Step 7: Create final directory structure early
                archive_dir, metadata_dir = self._create_final_directory_structure(
                    archive_path, archive_name, safe_ops
                )

                # Step 8: Move archive to final location
                final_archive_path = self._move_archive_to_final_location(
                    archive_path, archive_dir, safe_ops
                )

                # Step 9: Generate dual hash files directly in metadata directory
                hash_files = self._generate_hash_files(
                    final_archive_path, metadata_dir, safe_ops
                )

                # Step 10: Verify hash files
                if self.processing_options.verify_integrity:
                    self._verify_hash_files(final_archive_path, hash_files)

                # Step 11: Generate PAR2 recovery files directly in metadata directory
                par2_files = []
                if self.processing_options.generate_par2:
                    par2_files = self._generate_par2_files(
                        final_archive_path, metadata_dir, safe_ops
                    )

                # Step 12: Final verification with files in final locations
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

                # Step 13: Create comprehensive metadata
                metadata = self._create_metadata(
                    source_path,
                    final_archive_path,
                    extracted_dir,
                    hash_files,
                    par2_files,
                    processing_start_time,
                )

                # Step 14: Generate metadata.toml file
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

                logger.success(
                    f"Cold storage archive created successfully: {final_archive_path}"
                )

                return ArchiveResult(
                    success=True,
                    metadata=metadata,
                    message=f"Archive created: {final_archive_path.name}",
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

    # ---------------------------------------------------------------------
    # External tar detection helpers
    # ---------------------------------------------------------------------
    def _detect_tar_sort_command(self) -> Optional[list[str]]:
        """Detect a platform‑appropriate tar/bsdtar command that supports deterministic sorted output.

        Only returns commands that support sorting to ensure consistent hash generation.

        Returns:
            A command list (program plus required sort arguments) suitable for subprocess,
            or ``None`` if no such command is available (falls back to Python tarfile with sorting).
        """
        system = platform.system().lower()

        # Linux ── try GNU tar with --sort=name only
        if system == "linux":
            tar_path = shutil.which("tar")
            if tar_path and self._supports_gnu_sort(tar_path):
                return [tar_path, "--sort=name"]

        # macOS ── prefer gtar, then bsdtar (only if they support sorting)
        if system == "darwin":
            # First try: gtar (GNU tar with --sort=name)
            gtar_path = shutil.which("gtar")
            if gtar_path and self._supports_gnu_sort(gtar_path):
                return [gtar_path, "--sort=name"]

            # Second try: bsdtar with sorting
            bsdtar_path = shutil.which("bsdtar")
            if bsdtar_path and self._supports_bsdtar_sort(bsdtar_path):
                return [bsdtar_path, "--options", "sort=name"]

        # Windows 或其他系統：嘗試檢測支援排序的 tar
        tar_path = shutil.which("tar")
        if tar_path and self._supports_gnu_sort(tar_path):
            return [tar_path, "--sort=name"]

        # 沒有找到支援排序的外部 tar，回退到 Python tarfile（Python 確保排序）
        logger.debug(
            "No external tar with sorting support found, using Python tarfile with deterministic sorting"
        )
        return None

    def _get_tar_method_description(self) -> str:
        """Get a description of the TAR method that will be used.

        Returns:
            Human-readable description of the TAR creation method
        """
        if self._external_tar_cmd is None:
            return "Python tarfile"

        base_exe = Path(self._external_tar_cmd[0]).name.lower()
        if "gtar" in base_exe:
            return "GNU tar"
        elif "bsdtar" in base_exe:
            return "BSD tar"
        elif "tar" in base_exe:
            return "GNU tar"
        else:
            return "External tar"

    @staticmethod
    def _supports_gnu_sort(tar_exe: str) -> bool:
        """Return ``True`` if *tar_exe* understands ``--sort=name``."""
        try:
            test_cmd = [tar_exe, "--sort=name", "-cf", "/dev/null", "/dev/null"]
            return (
                subprocess.run(
                    test_cmd, capture_output=True, text=True, timeout=5
                ).returncode
                == 0
            )
        except Exception:
            return False

    @staticmethod
    def _supports_bsdtar_sort(bsdtar_exe: str) -> bool:
        """Return ``True`` if *bsdtar_exe* understands ``--options sort=name``."""
        try:
            test_cmd = [
                bsdtar_exe,
                "--options",
                "sort=name",
                "-cf",
                "/dev/null",
                "/dev/null",
            ]
            return (
                subprocess.run(
                    test_cmd, capture_output=True, text=True, timeout=5
                ).returncode
                == 0
            )
        except Exception:
            return False

    # ---------------------------------------------------------------------
    # External tar execution helper
    # ---------------------------------------------------------------------
    def _create_tar_with_external(self, source_dir: Path, tar_path: Path) -> None:
        """Create a TAR archive using the detected external command with deterministic sorting and system file filtering.

        Args:
            source_dir: Directory whose contents will be archived
            tar_path: Destination TAR file path
        """
        assert self._external_tar_cmd is not None, "_external_tar_cmd must not be None"
        assert len(self._external_tar_cmd) > 1, (
            "External tar command must include sorting arguments"
        )

        # Get filtered file list
        files_to_archive = filter_files_for_archive(source_dir)

        if not files_to_archive:
            logger.warning("No files to archive after filtering")
            # Create empty tar file
            with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT):
                pass
            return

        # Create temporary file list for tar
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            files_list_path = Path(f.name)
            for file_path in files_to_archive:
                # Calculate relative path from source_dir
                rel_path = file_path.relative_to(source_dir)
                f.write(f"{rel_path}\n")

        try:
            # Decide on a POSIX‑compliant format flag
            base_exe = Path(self._external_tar_cmd[0]).name.lower()
            sort_args = self._external_tar_cmd[1:]  # Required sorting arguments

            if "bsdtar" in base_exe:
                format_args = ["--format", "pax"]  # bsdtar syntax
            else:
                # GNU tar / gtar syntax
                format_args = ["--format=posix"]

            # Build command with file list and guaranteed sorting
            cmd = [
                self._external_tar_cmd[0],
                *sort_args,  # Required sorting args (--sort=name or --options sort=name)
                *format_args,
                "-cf",
                str(tar_path),
                "--directory",
                str(source_dir),
                "-T",  # Read file list from file
                str(files_list_path),
            ]

            logger.debug(
                f"Running deterministic tar with filtered file list: {' '.join(cmd)}"
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if result.returncode != 0:
                raise ArchivingError(f"tar command failed: {result.stderr}")

        finally:
            # Clean up temporary file list
            from contextlib import suppress

            with suppress(OSError):
                files_list_path.unlink()

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
        logger.info(f"Step 2: Creating deterministic TAR archive ({self._tar_method})")

        tar_path = output_dir / f"{archive_name}.tar"
        safe_ops.track_file(tar_path)

        try:
            # Prefer external tar (GNU tar / bsdtar) if we found one; otherwise fall back to Python tarfile.
            if self._external_tar_cmd:
                self._create_tar_with_external(source_dir, tar_path)
            else:
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

    def _create_tar_with_python(self, source_dir: Path, tar_path: Path) -> None:
        """Create TAR using Python tarfile (POSIX/PAX format) with system file filtering."""
        with tarfile.open(tar_path, "w", format=tarfile.PAX_FORMAT) as tar:
            # Use filtered file list to exclude system files
            files_to_add = filter_files_for_archive(source_dir)

            for file_path in files_to_add:
                # Calculate relative path from source_dir (archive contents, not directory itself)
                arcname = file_path.relative_to(source_dir)
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
        logger.info("Step 6: Generating dual hash files (SHA-256 + BLAKE3)")

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

            logger.success(f"Generated {len(hash_files)} hash files in {metadata_dir}")
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
            f"Step 8: Generating PAR2 recovery files ({self.processing_options.par2_redundancy}%)"
        )

        try:
            par2_manager = PAR2Manager(self.processing_options.par2_redundancy)
            par2_files = par2_manager.create_recovery_files(
                archive_path, output_dir=metadata_dir
            )

            # Track files for cleanup on error
            for par2_file in par2_files:
                safe_ops.track_file(par2_file)

            logger.success(
                f"Generated {len(par2_files)} PAR2 recovery files in {metadata_dir}"
            )
            return par2_files

        except Exception as e:
            raise ArchivingError(f"PAR2 generation failed: {e}") from e

    def _create_final_directory_structure(
        self, archive_path: Path, archive_name: str, safe_ops: Any
    ) -> tuple[Path, Path]:
        """Create the final directory structure early in the process.

        Args:
            archive_path: Current archive file path
            archive_name: Name of the archive
            safe_ops: Safe file operations context

        Returns:
            Tuple of (archive_dir, metadata_dir) paths
        """
        logger.info("Step 7: Creating final directory structure")

        # Create directory structure
        output_base = archive_path.parent
        archive_dir = output_base / archive_name
        metadata_dir = archive_dir / "metadata"

        archive_dir.mkdir(exist_ok=True)
        metadata_dir.mkdir(exist_ok=True)
        safe_ops.track_directory(archive_dir)
        safe_ops.track_directory(metadata_dir)

        logger.success(f"Created directory structure: {archive_dir}")
        return archive_dir, metadata_dir

    def _move_archive_to_final_location(
        self, archive_path: Path, archive_dir: Path, safe_ops: Any
    ) -> Path:
        """Move archive file to its final location.

        Args:
            archive_path: Current archive file path
            archive_dir: Target archive directory
            safe_ops: Safe file operations context

        Returns:
            Final archive path
        """
        logger.info("Step 8: Moving archive to final location")

        final_archive_path = archive_dir / archive_path.name
        archive_path.rename(final_archive_path)
        safe_ops.track_file(final_archive_path)

        logger.success(f"Moved archive to: {final_archive_path}")
        return final_archive_path

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
            Complete archive metadata object
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

            # Get archive name (without .tar.zst extension)
            archive_name = archive_path.stem
            if archive_name.endswith(".tar"):
                archive_name = archive_name[:-4]

            # Update TAR settings with detected method
            tar_method = self._get_tar_method_description().lower()
            # Map method descriptions to valid enum values
            method_mapping = {
                "python tarfile": "python",
                "gnu tar": "gnu",
                "bsd tar": "bsd",
                "external tar": "auto",
            }
            valid_method = method_mapping.get(tar_method, "auto")

            tar_settings = TarSettings(
                method=valid_method,
                sort_files=self.tar_settings.sort_files,
                preserve_permissions=self.tar_settings.preserve_permissions,
            )

            # Create comprehensive metadata
            metadata = ArchiveMetadata(
                # Core identification
                source_path=source_path,
                archive_path=archive_path,
                archive_name=archive_name,
                # Version and creation (will be auto-populated by model_post_init)
                coldpack_version="1.0.0-dev",
                # Processing settings
                compression_settings=self.compression_settings,
                par2_settings=self.par2_settings,
                tar_settings=tar_settings,
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
                archive_name=archive_path.stem.replace(".tar", ""),
                compression_settings=self.compression_settings,
                par2_settings=self.par2_settings,
                tar_settings=TarSettings(),
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
