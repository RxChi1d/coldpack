"""Multi-format extractor using py7zz with intelligent directory structure detection."""

from pathlib import Path
from typing import Any, Optional, Union

import py7zz
from loguru import logger

from ..config.constants import SUPPORTED_INPUT_FORMATS
from ..utils.filesystem import (
    safe_file_operations,
)


class ExtractionError(Exception):
    """Base exception for extraction operations."""

    pass


class UnsupportedFormatError(ExtractionError):
    """Raised when the archive format is not supported."""

    pass


class MultiFormatExtractor:
    """Multi-format extractor with intelligent directory structure handling."""

    def __init__(self) -> None:
        """Initialize the extractor."""
        logger.debug("Multi-format extractor initialized")

    def _get_clean_archive_name(self, source_path: Path) -> str:
        """Get clean archive name by removing known archive extensions.

        Handles compound extensions like .tar.xz, .tar.bz2, .tar.gz correctly
        to avoid duplicate .tar in the final archive name.

        Args:
            source_path: Path to source file or directory

        Returns:
            Clean archive name without archive extensions
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

    def extract(
        self,
        source: Union[str, Path],
        output_dir: Union[str, Path],
        preserve_structure: bool = True,
        force_overwrite: bool = False,
        metadata: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
    ) -> Path:
        """Extract archive to output directory with intelligent structure detection.

        Args:
            source: Path to source archive or directory
            output_dir: Directory to extract to
            preserve_structure: Whether to preserve archive structure
            force_overwrite: Force overwrite existing files
            metadata: Optional metadata for parameter recovery
            progress_callback: Optional progress callback for extraction progress

        Returns:
            Path to the extracted content directory

        Raises:
            FileNotFoundError: If source doesn't exist
            UnsupportedFormatError: If format is not supported
            ExtractionError: If extraction fails
        """
        source_path = Path(source)
        output_path = Path(output_dir)

        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")

        # Handle directory input (no extraction needed)
        if source_path.is_dir():
            return self._handle_directory_input(source_path, output_path)

        # Handle archive files
        return self._extract_archive(
            source_path,
            output_path,
            preserve_structure,
            force_overwrite,
            metadata,
            progress_callback,
        )

    def _handle_directory_input(self, source_dir: Path, output_dir: Path) -> Path:
        """Handle directory input by returning the source path.

        Args:
            source_dir: Source directory path
            output_dir: Output directory path (unused for directories)

        Returns:
            Path to the source directory
        """
        logger.info(f"Using directory directly: {source_dir}")
        return source_dir

    def _extract_archive(
        self,
        archive_path: Path,
        output_dir: Path,
        preserve_structure: bool,
        force_overwrite: bool,
        metadata: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
    ) -> Path:
        """Extract archive file using py7zz with enhanced 7z support.

        Args:
            archive_path: Path to archive file
            output_dir: Directory to extract to
            preserve_structure: Whether to preserve archive structure
            force_overwrite: Force overwrite existing files
            metadata: Optional metadata for parameter recovery
            progress_callback: Optional progress callback for extraction progress

        Returns:
            Path to extracted content

        Raises:
            UnsupportedFormatError: If format is not supported
            ExtractionError: If extraction fails
        """
        # Check if format is supported
        if not self._is_supported_format(archive_path):
            raise UnsupportedFormatError(
                f"Unsupported format: {archive_path.suffix}. "
                f"Supported formats: {', '.join(SUPPORTED_INPUT_FORMATS)}"
            )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Check if this is a 7z archive (coldpack 7z format)
            if self._is_7z_format(archive_path):
                return self._extract_7z_archive(
                    archive_path,
                    output_dir,
                    preserve_structure,
                    force_overwrite,
                    metadata,
                    progress_callback,
                )

            # Check if this is a compound tar archive (tar.gz, tar.bz2, tar.xz, etc.)
            if self._is_compound_tar_format(archive_path):
                return self._extract_compound_tar_archive(
                    archive_path, output_dir, preserve_structure, force_overwrite
                )

            # Check archive structure to determine extraction strategy
            # py7zz: get_archive_info no longer provides file list
            try:
                has_single_root = self._check_archive_structure(archive_path)
            except Exception as e:
                logger.debug(f"Archive structure check failed: {e}")
                # Fallback: assume no single root (safer to create directory)
                has_single_root = False

            if has_single_root and preserve_structure:
                # Archive has single root directory, extract directly
                return self._extract_with_structure(
                    archive_path, output_dir, force_overwrite, progress_callback
                )
            else:
                # Archive has multiple root items or flat structure
                return self._extract_to_named_directory(
                    archive_path, output_dir, force_overwrite, progress_callback
                )

        except Exception as e:
            raise ExtractionError(f"Failed to extract {archive_path}: {e}") from e

    def _is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported.

        Args:
            file_path: Path to the file

        Returns:
            True if format is supported
        """
        # Check single extension
        if file_path.suffix.lower() in SUPPORTED_INPUT_FORMATS:
            return True

        # Check compound extensions (e.g., .tar.gz)
        if len(file_path.suffixes) >= 2:
            compound_suffix = "".join(file_path.suffixes[-2:]).lower()
            if compound_suffix in SUPPORTED_INPUT_FORMATS:
                return True

        return False

    def _is_7z_format(self, file_path: Path) -> bool:
        """Check if file is a 7z archive (coldpack 7z format).

        Args:
            file_path: Path to the file

        Returns:
            True if file is 7z format
        """
        return file_path.suffix.lower() == ".7z"

    def _is_compound_tar_format(self, file_path: Path) -> bool:
        """Check if file is a compound tar archive (tar.gz, tar.bz2, tar.xz, etc.).

        Args:
            file_path: Path to the file

        Returns:
            True if file is a compound tar format
        """
        if len(file_path.suffixes) >= 2:
            compound_suffix = "".join(file_path.suffixes[-2:]).lower()
            compound_tar_formats = [
                ".tar.gz",
                ".tar.bz2",
                ".tar.xz",
                ".tar.lz",
                ".tar.lzma",
                ".tar.Z",
                ".tar.lz4",
            ]
            return compound_suffix in compound_tar_formats
        return False

    def _extract_7z_archive(
        self,
        archive_path: Path,
        output_dir: Path,
        preserve_structure: bool,
        force_overwrite: bool,
        metadata: Optional[Any] = None,
        progress_callback: Optional[Any] = None,
    ) -> Path:
        """Extract 7z archive with enhanced progress tracking and structure detection.

        Args:
            archive_path: Path to the 7z archive
            output_dir: Directory to extract to
            preserve_structure: Whether to preserve archive structure
            force_overwrite: Force overwrite existing files
            metadata: Optional metadata containing original compression parameters
            progress_callback: Optional progress callback function

        Returns:
            Path to the extracted content directory

        Raises:
            ExtractionError: If extraction fails
        """
        logger.info(f"Extracting 7z archive: {archive_path.name}")

        if (
            metadata
            and hasattr(metadata, "sevenzip_settings")
            and metadata.sevenzip_settings
        ):
            logger.debug("Using 7z settings from metadata")
            logger.debug(f"  Level: {metadata.sevenzip_settings.level}")
            logger.debug(f"  Dictionary: {metadata.sevenzip_settings.dictionary_size}")
            logger.debug(f"  Method: {metadata.sevenzip_settings.method}")

        try:
            # Create progress callback adapter if needed
            py7zz_callback = None
            if progress_callback:

                def progress_adapter(progress_info: Any) -> None:
                    """Adapter for py7zz progress callbacks."""
                    try:
                        if hasattr(progress_info, "percentage"):
                            percentage = int(progress_info.percentage)
                        else:
                            percentage = 0

                        if hasattr(progress_info, "current_file"):
                            current_file = str(progress_info.current_file)
                        else:
                            current_file = "Extracting..."

                        progress_callback(percentage, current_file)
                    except Exception as e:
                        logger.debug(f"Progress callback error: {e}")

                py7zz_callback = progress_adapter

            # Check for existing directory if not forcing overwrite
            if not force_overwrite:
                existing_items = (
                    list(output_dir.iterdir()) if output_dir.exists() else []
                )
                if existing_items:
                    raise ExtractionError(
                        f"Target directory not empty: {output_dir}. Use --force to overwrite."
                    )

            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # Extract 7z archive using py7zz
            # New py7zz version automatically handles Windows filename compatibility
            with py7zz.SevenZipFile(archive_path, "r") as archive:
                self._extract_normally(archive, output_dir, py7zz_callback)

            # Determine extracted structure
            extracted_items = list(output_dir.iterdir())

            if len(extracted_items) == 1 and extracted_items[0].is_dir():
                # Single directory was extracted - return it directly
                result_path = extracted_items[0]
            elif len(extracted_items) >= 1:
                # Multiple items extracted - they are already in output_dir
                result_path = output_dir
            else:
                # No items extracted - error
                raise ExtractionError("No content found after 7z extraction")

            logger.success(f"7z archive extracted: {archive_path.name}")
            return result_path

        except py7zz.Py7zzError as e:
            raise ExtractionError(f"7z extraction failed: {e}") from e
        except Exception as e:
            raise ExtractionError(f"Failed to extract 7z archive: {e}") from e

    def _extract_normally(
        self,
        archive: py7zz.SevenZipFile,
        output_dir: Path,
        progress_callback: Optional[Any] = None,
    ) -> None:
        """Extract archive normally without filename modifications.

        Args:
            archive: Opened py7zz archive object
            output_dir: Directory to extract to
            progress_callback: Optional progress callback function
        """
        if progress_callback:
            # Use extract_all with progress callback if supported
            try:
                archive.extractall(
                    path=str(output_dir), progress_callback=progress_callback
                )
            except (TypeError, AttributeError):
                # Fallback if progress callback not supported
                logger.debug(
                    "Progress callback not supported, extracting without progress"
                )
                archive.extractall(path=str(output_dir))
        else:
            archive.extractall(path=str(output_dir))

    def _check_archive_structure_from_filelist(
        self, file_list: list, archive_name: str
    ) -> bool:
        """Check if archive has a single root directory structure from file list.

        Args:
            file_list: List of files in the archive
            archive_name: Name of the archive (without extension)

        Returns:
            True if archive has single root directory matching the archive name
        """
        if not file_list:
            logger.warning("Archive contains no files")
            return False

        # Extract first-level items (no path separators)
        first_level_items = set()
        for item in file_list:
            # Normalize path separators
            normalized_path = item.replace("\\", "/")

            # Get first component
            parts = normalized_path.split("/")
            if parts[0]:  # Skip empty parts
                first_level_items.add(parts[0])

        # Check if there's exactly one first-level item
        if len(first_level_items) == 1:
            root_name = next(iter(first_level_items))

            # Check if root directory name matches archive name
            if root_name == archive_name:
                # Verify it's actually a directory (has subdirectories/files)
                has_subdirectories = any(
                    item.replace("\\", "/").startswith(f"{root_name}/")
                    for item in file_list
                )

                if has_subdirectories:
                    logger.debug(
                        f"Archive has matching single root directory: {root_name}"
                    )
                    return True

        logger.debug(f"Archive structure: {len(first_level_items)} root items")
        return False

    def _extract_tar_with_structure(
        self,
        tar_archive: py7zz.SevenZipFile,
        archive_path: Path,
        output_dir: Path,
        force_overwrite: bool,
    ) -> Path:
        """Extract tar archive preserving its internal structure.

        Args:
            tar_archive: Opened py7zz archive object
            archive_path: Path to the tar archive
            output_dir: Output directory
            force_overwrite: Force overwrite existing files

        Returns:
            Path to the extracted root directory
        """
        logger.debug(f"Extracting tar with preserved structure: {archive_path.name}")

        # Check for existing files if not forcing overwrite
        archive_name = self._get_clean_archive_name(archive_path)
        extracted_root = output_dir / archive_name
        if extracted_root.exists() and not force_overwrite:
            raise ExtractionError(
                f"Target directory already exists: {extracted_root}. Use --force to overwrite."
            )

        with safe_file_operations():
            try:
                tar_archive.extractall(path=str(output_dir))

                # Find the extracted root directory
                archive_name = self._get_clean_archive_name(archive_path)
                extracted_root = output_dir / archive_name

                if extracted_root.exists() and extracted_root.is_dir():
                    logger.success(f"Archive extracted to: {extracted_root.name}")
                    return extracted_root
                else:
                    # Fallback: find the first directory in output
                    for item in output_dir.iterdir():
                        if item.is_dir():
                            logger.success(f"Archive extracted to: {item.name}")
                            return item

                    raise ExtractionError("No directory found after extraction")

            except Exception as e:
                raise ExtractionError(f"Tar extraction failed: {e}") from e

    def _extract_tar_to_named_directory(
        self,
        tar_archive: py7zz.SevenZipFile,
        archive_path: Path,
        output_dir: Path,
        force_overwrite: bool,
    ) -> Path:
        """Extract tar archive to a directory named after the archive.

        Args:
            tar_archive: Opened py7zz archive object
            archive_path: Path to the tar archive
            output_dir: Output directory
            force_overwrite: Force overwrite existing files

        Returns:
            Path to the created target directory
        """
        archive_name = self._get_clean_archive_name(archive_path)
        target_dir = output_dir / archive_name

        # Check for existing directory if not forcing overwrite
        if target_dir.exists() and not force_overwrite:
            raise ExtractionError(
                f"Target directory already exists: {target_dir}. Use --force to overwrite."
            )

        logger.debug(f"Extracting tar to named directory: {target_dir.name}")

        with safe_file_operations() as safe_ops:
            try:
                # Create target directory
                target_dir.mkdir(parents=True, exist_ok=True)
                safe_ops.track_directory(target_dir)

                # Extract to target directory
                tar_archive.extractall(path=str(target_dir))

                # Verify extraction
                if not any(target_dir.iterdir()):
                    raise ExtractionError("Target directory is empty after extraction")

                logger.success(f"Archive extracted to: {target_dir.name}")
                return target_dir

            except Exception as e:
                raise ExtractionError(
                    f"Tar extraction to named directory failed: {e}"
                ) from e

    def _check_archive_structure(self, archive_path: Path) -> bool:
        """Check if archive has a single root directory structure.

        Args:
            archive_path: Path to the archive

        Returns:
            True if archive has single root directory matching the archive name

        Raises:
            ExtractionError: If structure cannot be determined
        """
        try:
            logger.debug(f"Checking archive structure: {archive_path}")

            with py7zz.SevenZipFile(archive_path, "r") as archive:
                file_list = archive.namelist()

                if not file_list:
                    logger.warning(f"Archive contains no files: {archive_path.name}")
                    return False

                # Extract first-level items (no path separators)
                first_level_items = set()
                for item in file_list:
                    # Normalize path separators
                    normalized_path = item.replace("\\", "/")

                    # Get first component
                    parts = normalized_path.split("/")
                    if parts[0]:  # Skip empty parts
                        first_level_items.add(parts[0])

                # Check if there's exactly one first-level item
                if len(first_level_items) == 1:
                    root_name = next(iter(first_level_items))
                    archive_name = self._get_clean_archive_name(archive_path)

                    # Check if root directory name matches archive name
                    if root_name == archive_name:
                        # Verify it's actually a directory (has subdirectories/files)
                        has_subdirectories = any(
                            item.replace("\\", "/").startswith(f"{root_name}/")
                            for item in file_list
                        )

                        if has_subdirectories:
                            logger.debug(
                                f"Archive has matching single root directory: {root_name}"
                            )
                            return True

                logger.debug(f"Archive structure: {len(first_level_items)} root items")
                return False

        except Exception as e:
            logger.error(f"Failed to check archive structure: {e}")
            # On error, assume no single root (safer to create directory)
            return False

    def _extract_with_structure(
        self,
        archive_path: Path,
        output_dir: Path,
        force_overwrite: bool,
        progress_callback: Optional[Any] = None,
    ) -> Path:
        """Extract archive preserving its internal structure.

        Args:
            archive_path: Path to the archive
            output_dir: Output directory
            force_overwrite: Force overwrite existing files
            progress_callback: Optional progress callback function

        Returns:
            Path to the extracted root directory
        """
        logger.debug(f"Extracting with preserved structure: {archive_path.name}")

        # Check for existing files if not forcing overwrite
        archive_name = self._get_clean_archive_name(archive_path)
        extracted_root = output_dir / archive_name
        if extracted_root.exists() and not force_overwrite:
            raise ExtractionError(
                f"Target directory already exists: {extracted_root}. Use --force to overwrite."
            )

        with safe_file_operations():
            try:
                with py7zz.SevenZipFile(archive_path, "r") as archive:
                    # py7zz automatically handles Windows filename compatibility
                    archive.extractall(path=str(output_dir))

                # Find the extracted root directory
                archive_name = self._get_clean_archive_name(archive_path)
                extracted_root = output_dir / archive_name

                if extracted_root.exists() and extracted_root.is_dir():
                    logger.success(f"Archive extracted to: {extracted_root.name}")
                    return extracted_root
                else:
                    # Fallback: find the first directory in output
                    for item in output_dir.iterdir():
                        if item.is_dir():
                            logger.success(f"Archive extracted to: {item.name}")
                            return item

                    raise ExtractionError("No directory found after extraction")

            except Exception as e:
                raise ExtractionError(f"Extraction failed: {e}") from e

    def _extract_to_named_directory(
        self,
        archive_path: Path,
        output_dir: Path,
        force_overwrite: bool,
        progress_callback: Optional[Any] = None,
    ) -> Path:
        """Extract archive to a directory named after the archive.

        Args:
            archive_path: Path to the archive
            output_dir: Output directory
            force_overwrite: Force overwrite existing files
            progress_callback: Optional progress callback function

        Returns:
            Path to the created target directory
        """
        archive_name = self._get_clean_archive_name(archive_path)
        target_dir = output_dir / archive_name

        # Check for existing directory if not forcing overwrite
        if target_dir.exists() and not force_overwrite:
            raise ExtractionError(
                f"Target directory already exists: {target_dir}. Use --force to overwrite."
            )

        logger.debug(f"Extracting to named directory: {target_dir.name}")

        with safe_file_operations() as safe_ops:
            try:
                # Create target directory
                target_dir.mkdir(parents=True, exist_ok=True)
                safe_ops.track_directory(target_dir)

                # Extract to target directory
                with py7zz.SevenZipFile(archive_path, "r") as archive:
                    # py7zz automatically handles Windows filename compatibility
                    archive.extractall(path=str(target_dir))

                # Verify extraction
                if not any(target_dir.iterdir()):
                    raise ExtractionError("Target directory is empty after extraction")

                logger.success(f"Archive extracted to: {target_dir.name}")
                return target_dir

            except Exception as e:
                raise ExtractionError(
                    f"Extraction to named directory failed: {e}"
                ) from e

    def get_archive_info(self, archive_path: Union[str, Path]) -> dict:
        """Get information about an archive without extracting it.

        Uses py7zz API for efficient information retrieval.

        Args:
            archive_path: Path to the archive

        Returns:
            Dictionary with archive information including structure analysis

        Raises:
            FileNotFoundError: If archive doesn't exist
            UnsupportedFormatError: If format is not supported
            ExtractionError: If info cannot be obtained
        """
        archive_obj = Path(archive_path)

        if not archive_obj.exists():
            raise FileNotFoundError(f"Archive not found: {archive_obj}")

        if not self._is_supported_format(archive_obj):
            raise UnsupportedFormatError(f"Unsupported format: {archive_obj.suffix}")

        try:
            # Use py7zz.get_archive_info for basic statistics
            # py7zz: get_archive_info only returns statistical information
            py7zz_info = py7zz.get_archive_info(str(archive_obj))

            # For structure analysis, use SevenZipFile to get file list
            has_single_root = False
            root_name = None

            try:
                with py7zz.SevenZipFile(str(archive_obj), "r") as archive:
                    file_list = archive.namelist()

                    if file_list:
                        # Analyze archive structure
                        has_single_root, root_name = self._analyze_archive_structure(
                            file_list, archive_obj
                        )
            except Exception as e:
                logger.debug(f"Could not analyze archive structure: {e}")
                # Fallback: use archive name as root name
                archive_stem = archive_obj.stem
                if archive_stem.endswith(".tar"):
                    archive_stem = archive_stem[:-4]
                has_single_root = True
                root_name = archive_stem

            return {
                "path": str(archive_obj),
                "format": archive_obj.suffix,
                "size": py7zz_info.get("compressed_size", archive_obj.stat().st_size),
                "file_count": py7zz_info.get("file_count", 0),
                "uncompressed_size": py7zz_info.get("uncompressed_size", 0),
                "compression_ratio": py7zz_info.get("compression_ratio", 0.0),
                "has_single_root": has_single_root,
                "root_name": root_name,
            }

        except Exception as e:
            raise ExtractionError(f"Failed to get archive info: {e}") from e

    def _analyze_archive_structure(
        self, file_list: list[str], archive_path: Path
    ) -> tuple[bool, Optional[str]]:
        """Analyze archive structure to determine extraction strategy.

        This method replaces the previous _check_archive_structure with improved
        logic that properly handles py7zz file lists and fixes the statistical
        information filtering bug.

        Args:
            file_list: List of files in the archive (pre-filtered)
            archive_path: Path to the archive for name matching

        Returns:
            Tuple of (has_single_root, root_name)
            - has_single_root: True if archive has single root directory
            - root_name: Name of root directory if has_single_root is True
        """
        if not file_list:
            logger.warning(f"Archive contains no files: {archive_path.name}")
            return False, None

        # Extract first-level items (no path separators)
        first_level_items = set()
        for item in file_list:
            if item:
                # Normalize path separators and get first component
                normalized_path = item.replace("\\", "/")
                parts = normalized_path.split("/")
                if parts[0]:  # Skip empty parts
                    first_level_items.add(parts[0])

        # Check if there's exactly one first-level item
        if len(first_level_items) == 1:
            root_name = next(iter(first_level_items))
            archive_name = self._get_clean_archive_name(archive_path)

            # Check if root directory name matches archive name (coldpack convention)
            if root_name == archive_name:
                # Verify it's actually a directory structure (has subdirectories/files)
                has_subdirectories = any(
                    item.replace("\\", "/").startswith(f"{root_name}/")
                    for item in file_list
                )

                if has_subdirectories:
                    logger.debug(
                        f"Archive has matching single root directory: {root_name}"
                    )
                    return True, root_name

        logger.debug(f"Archive structure: {len(first_level_items)} root items")
        return False, None

    def validate_archive(self, archive_path: Union[str, Path]) -> bool:
        """Validate archive integrity without extracting.

        Args:
            archive_path: Path to the archive

        Returns:
            True if archive is valid

        Raises:
            FileNotFoundError: If archive doesn't exist
            UnsupportedFormatError: If format is not supported
        """
        archive_obj = Path(archive_path)

        if not archive_obj.exists():
            raise FileNotFoundError(f"Archive not found: {archive_obj}")

        if not self._is_supported_format(archive_obj):
            raise UnsupportedFormatError(f"Unsupported format: {archive_obj.suffix}")

        try:
            logger.debug(f"Validating archive: {archive_obj}")

            with py7zz.SevenZipFile(archive_obj, "r") as archive:
                # Try to read the file list - this will fail if archive is corrupted
                file_list = archive.namelist()

                # Basic validation: archive should have files
                if not file_list:
                    logger.warning(f"Archive contains no files: {archive_obj.name}")
                    return False

                logger.debug(f"Archive validation passed: {len(file_list)} files")
                return True

        except Exception as e:
            logger.error(f"Archive validation failed: {e}")
            return False

    def _extract_compound_tar_archive(
        self,
        archive_path: Path,
        output_dir: Path,
        preserve_structure: bool,
        force_overwrite: bool,
    ) -> Path:
        """Extract compound tar archive (tar.gz, tar.bz2, tar.xz, etc.) by two-stage extraction.

        Args:
            archive_path: Path to the compound tar archive
            output_dir: Directory to extract to
            preserve_structure: Whether to preserve archive structure
            force_overwrite: Force overwrite existing files

        Returns:
            Path to the extracted content directory

        Raises:
            ExtractionError: If extraction fails at any stage
        """
        logger.info(f"Extracting compound tar archive: {archive_path.name}")

        # Use a temporary directory for the intermediate tar file
        temp_dir = None

        try:
            # Create temporary directory for intermediate tar file with enhanced cleanup
            from ..utils.temp_manager import (
                create_temp_directory as create_enhanced_temp_dir,
            )

            temp_dir = create_enhanced_temp_dir(prefix="coldpack_extract_")
            logger.debug(f"Using temporary directory: {temp_dir}")

            # Step 1: Extract outer compression to get .tar file
            logger.debug("Step 1: Extracting outer compression")
            with py7zz.SevenZipFile(archive_path, "r") as compressed_archive:
                compressed_archive.extractall(path=str(temp_dir))

                # Find the intermediate tar file
                extracted_files = list(temp_dir.iterdir())
                tar_file = None
                for f in extracted_files:
                    if f.is_file() and f.name.lower().endswith(".tar"):
                        tar_file = f
                        break

                if not tar_file:
                    raise ExtractionError(
                        "No .tar file found after extracting outer compression"
                    )

                logger.debug(f"Found intermediate tar file: {tar_file}")

            # Step 2: Extract tar file to final destination
            logger.debug(f"Step 2: Extracting tar file to {output_dir}")

            # For compound tar files, extract tar contents directly to output_dir
            with py7zz.SevenZipFile(tar_file, "r") as tar_archive:
                # Extract tar contents directly to the output directory
                tar_archive.extractall(path=str(output_dir))

                # Check what was extracted and determine final structure
                extracted_items = list(output_dir.iterdir())

                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    # Single directory was extracted - this should be the content
                    result_path = extracted_items[0]
                elif len(extracted_items) >= 1:
                    # Multiple items or special case - wrap them in a named directory
                    archive_name = self._get_clean_archive_name(archive_path)

                    # Use a unique wrapper directory name to avoid conflicts
                    wrapper_dir = output_dir / archive_name
                    counter = 1
                    while wrapper_dir.exists():
                        wrapper_dir = output_dir / f"{archive_name}_{counter}"
                        counter += 1

                    wrapper_dir.mkdir(exist_ok=True)

                    # Move all extracted items into the wrapper directory
                    for item in extracted_items:
                        target = wrapper_dir / item.name
                        item.rename(target)

                    result_path = wrapper_dir
                else:
                    # No items extracted - error
                    raise ExtractionError("No content found after tar extraction")

            logger.success(f"Compound tar extracted: {archive_path.name}")
            return result_path

        except Exception as e:
            raise ExtractionError(f"Failed to extract compound tar archive: {e}") from e
        finally:
            # Enhanced temp manager handles cleanup automatically
            # No manual cleanup needed - temp_dir is tracked globally
            pass


def extract_archive(source: Union[str, Path], output_dir: Union[str, Path]) -> Path:
    """Convenience function to extract an archive.

    Args:
        source: Path to source archive or directory
        output_dir: Directory to extract to

    Returns:
        Path to extracted content

    Raises:
        ExtractionError: If extraction fails
    """
    extractor = MultiFormatExtractor()
    return extractor.extract(source, output_dir)


def get_supported_formats() -> set[str]:
    """Get set of supported archive formats.

    Returns:
        Set of supported file extensions
    """
    return SUPPORTED_INPUT_FORMATS.copy()
