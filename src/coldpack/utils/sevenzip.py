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
        logger.debug(f"7z compressor initialized: {self._config_dict}")

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

        logger.debug(f"Compressing directory: {source_path.name} → {archive_obj.name}")
        logger.debug(f"7z settings: {self._config_dict}")

        try:
            # Use SevenZipFile for compression with Config
            with py7zz.SevenZipFile(
                str(archive_obj), mode="w", config=self._py7zz_config
            ) as archive:
                # Add the source directory to the archive
                archive.add(str(source_path))

            # Success will be logged in archiver with file size info
            logger.debug(f"7z compression completed: {archive_obj.name}")

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

        logger.debug(f"Compressing {len(files)} files to {archive_obj.name}")
        logger.debug(
            f"File list: {[p.name for p in file_paths[:10]]}{' (+more)' if len(file_paths) > 10 else ''}"
        )

        try:
            # Use SevenZipFile for compression with Config
            with py7zz.SevenZipFile(
                str(archive_obj), mode="w", config=self._py7zz_config
            ) as archive:
                # Add each file to the archive
                for file_path in file_paths:
                    archive.add(str(file_path))

            logger.debug(f"7z archive created: {archive_obj.name} ({len(files)} files)")

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
            logger.warning(f"Archive not found for integrity test: {archive_obj.name}")
            return False

        try:
            logger.debug(f"Testing 7z integrity: {archive_obj.name}")
            # py7zz expects string paths
            result = py7zz.test_archive(str(archive_obj))

            if result:
                logger.debug(f"7z integrity test passed: {archive_obj}")
            else:
                logger.warning(f"7z integrity test failed: {archive_obj.name}")

            return bool(result)

        except Exception as e:
            logger.error(f"7z integrity test error: {e}")
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


def optimize_7z_compression_settings(
    source_size: int, threads: int = 0
) -> SevenZipSettings:
    """Optimize 7z compression settings based on precise source directory size.

    Uses the precise dynamic parameter table for optimal 7z compression:
    - < 256 KiB: level=1, dict=128k
    - 256 KiB – 1 MiB: level=3, dict=1m
    - 1 – 8 MiB: level=5, dict=4m
    - 8 – 64 MiB: level=6, dict=16m
    - 64 – 512 MiB: level=7, dict=64m
    - 512 MiB – 2 GiB: level=9, dict=256m
    - > 2 GiB: level=9, dict=512m

    Args:
        source_size: Size of source directory in bytes
        threads: Number of threads to use (0=auto-detect)

    Returns:
        Optimized SevenZipSettings based on precise size thresholds
    """
    # Precise size thresholds (in bytes) based on the provided table
    SIZE_256K = 256 * 1024
    SIZE_1M = 1024 * 1024
    SIZE_8M = 8 * 1024 * 1024
    SIZE_64M = 64 * 1024 * 1024
    SIZE_512M = 512 * 1024 * 1024
    SIZE_2G = 2 * 1024 * 1024 * 1024

    logger.debug(f"Optimizing 7z settings for source size: {source_size:,} bytes")

    if source_size < SIZE_256K:
        # < 256 KiB: Minimal compression, tiny dictionary
        settings = SevenZipSettings(
            level=1,
            dictionary_size="128k",
            threads=threads,
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using tiny file optimization (< 256 KiB)")

    elif source_size < SIZE_1M:
        # 256 KiB – 1 MiB: Light compression, small dictionary
        settings = SevenZipSettings(
            level=3,
            dictionary_size="1m",
            threads=threads,
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using small file optimization (256 KiB – 1 MiB)")

    elif source_size < SIZE_8M:
        # 1 – 8 MiB: Balanced compression
        settings = SevenZipSettings(
            level=5,
            dictionary_size="4m",
            threads=threads,
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using small-medium file optimization (1 – 8 MiB)")

    elif source_size < SIZE_64M:
        # 8 – 64 MiB: Good compression, medium dictionary
        settings = SevenZipSettings(
            level=6,
            dictionary_size="16m",
            threads=threads,
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using medium file optimization (8 – 64 MiB)")

    elif source_size < SIZE_512M:
        # 64 – 512 MiB: Higher compression, large dictionary
        settings = SevenZipSettings(
            level=7,
            dictionary_size="64m",
            threads=threads,
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using large file optimization (64 – 512 MiB)")

    elif source_size < SIZE_2G:
        # 512 MiB – 2 GiB: Maximum compression, very large dictionary
        settings = SevenZipSettings(
            level=9,
            dictionary_size="256m",
            threads=threads,
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using very large file optimization (512 MiB – 2 GiB)")

    else:
        # > 2 GiB: Maximum compression, maximum dictionary
        settings = SevenZipSettings(
            level=9,
            dictionary_size="512m",
            threads=threads,
            solid=True,
            method="LZMA2",
        )
        logger.debug("Using huge file optimization (> 2 GiB)")

    # Format threads display in a more user-friendly way
    threads_display = "all" if threads == 0 else str(threads)
    logger.info(
        f"Optimized 7z settings: level={settings.level}, dict={settings.dictionary_size}, threads={threads_display}"
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
