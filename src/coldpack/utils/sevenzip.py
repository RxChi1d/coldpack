"""7z compression utilities using py7zz library."""

from pathlib import Path
from typing import Any, Callable, Optional, Union

import py7zz  # type: ignore
from loguru import logger

from ..config.settings import SevenZipSettings


class SevenZipError(Exception):
    """Base exception for 7z operations."""

    pass


class CompressionError(SevenZipError):
    """Raised when 7z compression fails."""

    pass


class SevenZipCompressor:
    """7z compressor using py7zz library with progress tracking support."""

    def __init__(self, settings: Optional[SevenZipSettings] = None) -> None:
        """Initialize the 7z compressor.

        Args:
            settings: 7z compression settings
        """
        self.settings = settings or SevenZipSettings()
        self._config_dict = self.settings.to_py7zz_config()
        # Create py7zz Config object
        self._py7zz_config = py7zz.Config(**self._config_dict)
        logger.debug(
            f"SevenZipCompressor initialized with settings: {self._config_dict}"
        )

    def compress_directory(
        self,
        source_dir: Union[str, Path],
        archive_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        """Compress directory to 7z archive.

        Args:
            source_dir: Source directory to compress
            archive_path: Path to output 7z archive
            progress_callback: Optional progress callback function

        Raises:
            CompressionError: If compression fails
            FileNotFoundError: If source directory doesn't exist
        """
        source_path = Path(source_dir)
        archive_obj = Path(archive_path)

        if not source_path.exists():
            raise FileNotFoundError(f"Source directory not found: {source_path}")

        if not source_path.is_dir():
            raise ValueError(f"Source must be a directory: {source_path}")

        # Ensure parent directory exists
        archive_obj.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Compressing directory {source_path} to {archive_obj}")
        logger.debug(f"Using compression settings: {self._config_dict}")

        try:
            # Use SevenZipFile for compression with Config
            with py7zz.SevenZipFile(
                str(archive_obj), mode="w", config=self._py7zz_config
            ) as archive:
                # Add the source directory to the archive
                archive.add(str(source_path))

            logger.success(f"Successfully compressed to {archive_obj}")

        except py7zz.CompressionError as e:
            raise CompressionError(f"7z compression failed: {e}") from e
        except py7zz.FileNotFoundError as e:
            raise FileNotFoundError(
                f"Source file not found during compression: {e}"
            ) from e
        except py7zz.InsufficientSpaceError as e:
            raise CompressionError(
                f"Insufficient disk space for compression: {e}"
            ) from e
        except Exception as e:
            raise CompressionError(
                f"Unexpected error during 7z compression: {e}"
            ) from e

    def compress_files(
        self,
        files: list[Union[str, Path]],
        archive_path: Union[str, Path],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        """Compress list of files to 7z archive.

        Args:
            files: List of files to compress
            archive_path: Path to output 7z archive
            progress_callback: Optional progress callback function

        Raises:
            CompressionError: If compression fails
            FileNotFoundError: If any source file doesn't exist
        """
        if not files:
            raise ValueError("No files provided for compression")

        # Convert to Path objects and validate
        file_paths = [Path(f) for f in files]
        for file_path in file_paths:
            if not file_path.exists():
                raise FileNotFoundError(f"Source file not found: {file_path}")

        archive_obj = Path(archive_path)
        archive_obj.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Compressing {len(files)} files to {archive_obj}")
        logger.debug(f"Files: {[str(p) for p in file_paths]}")

        try:
            # Use SevenZipFile for compression with Config
            with py7zz.SevenZipFile(
                str(archive_obj), mode="w", config=self._py7zz_config
            ) as archive:
                # Add each file to the archive
                for file_path in file_paths:
                    archive.add(str(file_path))

            logger.success(
                f"Successfully compressed {len(files)} files to {archive_obj}"
            )

        except py7zz.CompressionError as e:
            raise CompressionError(f"7z compression failed: {e}") from e
        except py7zz.FileNotFoundError as e:
            raise FileNotFoundError(
                f"Source file not found during compression: {e}"
            ) from e
        except py7zz.InsufficientSpaceError as e:
            raise CompressionError(
                f"Insufficient disk space for compression: {e}"
            ) from e
        except Exception as e:
            raise CompressionError(
                f"Unexpected error during 7z compression: {e}"
            ) from e

    def test_integrity(self, archive_path: Union[str, Path]) -> bool:
        """Test 7z archive integrity.

        Args:
            archive_path: Path to 7z archive

        Returns:
            True if archive is valid, False otherwise
        """
        archive_obj = Path(archive_path)

        if not archive_obj.exists():
            logger.warning(f"Archive not found for integrity test: {archive_obj}")
            return False

        try:
            logger.debug(f"Testing 7z archive integrity: {archive_obj}")
            # py7zz expects string paths
            result = py7zz.test_archive(str(archive_obj))

            if result:
                logger.debug(f"7z integrity test passed: {archive_obj}")
            else:
                logger.warning(f"7z integrity test failed: {archive_obj}")

            return bool(result)

        except Exception as e:
            logger.error(f"Error during 7z integrity test: {e}")
            return False

    def _create_progress_adapter(
        self, coldpack_callback: Callable[[int, str], None]
    ) -> Callable[[Any], None]:
        """Create adapter to convert py7zz progress to coldpack format.

        Args:
            coldpack_callback: Coldpack progress callback function

        Returns:
            py7zz compatible progress callback
        """

        def py7zz_progress_adapter(progress_info: Any) -> None:
            """Adapter function for py7zz progress callbacks.

            Args:
                progress_info: py7zz ProgressInfo object
            """
            try:
                # Extract percentage and current file from py7zz ProgressInfo
                if hasattr(progress_info, "percentage"):
                    percentage = int(progress_info.percentage)
                else:
                    percentage = 0

                if hasattr(progress_info, "current_file"):
                    current_file = str(progress_info.current_file)
                else:
                    current_file = "Processing..."

                # Call coldpack callback with converted values
                coldpack_callback(percentage, current_file)

            except Exception as e:
                logger.debug(f"Error in progress callback adapter: {e}")
                # Continue without progress updates if adapter fails

        return py7zz_progress_adapter


def optimize_7z_compression_settings(source_size: int) -> SevenZipSettings:
    """Optimize 7z compression settings based on source directory size.

    Args:
        source_size: Size of source directory in bytes

    Returns:
        Optimized SevenZipSettings
    """
    # Size thresholds (in bytes)
    SMALL_SIZE = 100 * 1024 * 1024  # 100MB
    MEDIUM_SIZE = 1024 * 1024 * 1024  # 1GB
    LARGE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB

    logger.debug(f"Optimizing 7z settings for source size: {source_size:,} bytes")

    if source_size < SMALL_SIZE:
        # Small files: Fast compression, small dictionary
        settings = SevenZipSettings(
            level=3,
            dictionary_size="4m",
            threads=0,  # Auto-detect
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using small file optimization")

    elif source_size < MEDIUM_SIZE:
        # Medium files: Balanced compression
        settings = SevenZipSettings(
            level=5,
            dictionary_size="16m",
            threads=0,  # Auto-detect
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using medium file optimization")

    elif source_size < LARGE_SIZE:
        # Large files: Higher compression, larger dictionary
        settings = SevenZipSettings(
            level=7,
            dictionary_size="32m",
            threads=0,  # Auto-detect
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using large file optimization")

    else:
        # Very large files: Maximum compression with largest dictionary
        settings = SevenZipSettings(
            level=9,
            dictionary_size="64m",
            threads=0,  # Auto-detect
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using very large file optimization")

    logger.info(
        f"Optimized 7z settings: level={settings.level}, dict={settings.dictionary_size}"
    )
    return settings


def get_7z_info(archive_path: Union[str, Path]) -> dict[str, Any]:
    """Get information about a 7z archive.

    Args:
        archive_path: Path to 7z archive

    Returns:
        Dictionary with archive information

    Raises:
        FileNotFoundError: If archive doesn't exist
        SevenZipError: If archive cannot be read
    """
    archive_obj = Path(archive_path)

    if not archive_obj.exists():
        raise FileNotFoundError(f"Archive not found: {archive_obj}")

    try:
        logger.debug(f"Getting 7z archive info: {archive_obj}")

        with py7zz.SevenZipFile(str(archive_obj), "r") as archive:
            file_list = archive.namelist()

            # Calculate basic statistics
            file_count = len(file_list)
            archive_size = archive_obj.stat().st_size

            # Check for single root directory
            has_single_root = False
            root_name = None

            if file_list:
                # Extract first-level items
                first_level_items = set()
                for item in file_list:
                    normalized_path = item.replace("\\", "/")
                    parts = normalized_path.split("/")
                    if parts[0]:
                        first_level_items.add(parts[0])

                if len(first_level_items) == 1:
                    root_name = next(iter(first_level_items))
                    has_single_root = True

            return {
                "path": str(archive_obj),
                "format": ".7z",
                "size": archive_size,
                "file_count": file_count,
                "has_single_root": has_single_root,
                "root_name": root_name,
            }

    except Exception as e:
        raise SevenZipError(f"Failed to get 7z archive info: {e}") from e


def validate_7z_archive(archive_path: Union[str, Path]) -> bool:
    """Validate 7z archive integrity.

    Args:
        archive_path: Path to 7z archive

    Returns:
        True if archive is valid, False otherwise
    """
    try:
        compressor = SevenZipCompressor()
        return compressor.test_integrity(archive_path)
    except Exception as e:
        logger.debug(f"7z validation failed: {e}")
        return False
