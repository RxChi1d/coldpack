"""Archive content listing functionality using py7zz."""

import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import py7zz
from loguru import logger

from ..config.constants import SUPPORTED_INPUT_FORMATS


class ListingError(Exception):
    """Base exception for listing operations."""

    pass


class UnsupportedFormatError(ListingError):
    """Raised when the archive format is not supported for listing."""

    pass


class ArchiveFile:
    """Represents a file in an archive with metadata."""

    def __init__(
        self,
        path: str,
        size: int = 0,
        compressed_size: int = 0,
        modified: Optional[datetime] = None,
        is_directory: bool = False,
        crc: Optional[str] = None,
    ) -> None:
        """Initialize archive file metadata.

        Args:
            path: File path within the archive
            size: Uncompressed file size in bytes
            compressed_size: Compressed file size in bytes
            modified: Last modification time
            is_directory: Whether this is a directory entry
            crc: CRC checksum if available
        """
        self.path = path.replace("\\", "/")  # Normalize path separators
        self.name = Path(self.path).name
        self.size = size
        self.compressed_size = compressed_size
        self.modified = modified
        self.is_directory = is_directory
        self.crc = crc

        # Calculate directory level (depth)
        self.level = len([p for p in self.path.split("/") if p]) - 1

    def __str__(self) -> str:
        """String representation of the file."""
        return self.path

    def __repr__(self) -> str:
        """Detailed representation of the file."""
        return f"ArchiveFile(path='{self.path}', size={self.size}, is_dir={self.is_directory})"


class ArchiveLister:
    """Archive content lister with filtering and formatting capabilities."""

    def __init__(self) -> None:
        """Initialize the archive lister."""
        logger.debug("ArchiveLister initialized")

    def list_archive(
        self,
        archive_path: Union[str, Path],
        limit: Optional[int] = None,
        offset: int = 0,
        filter_pattern: Optional[str] = None,
        dirs_only: bool = False,
        files_only: bool = False,
        summary_only: bool = False,
    ) -> dict[str, Any]:
        """List archive contents with filtering and pagination.

        Args:
            archive_path: Path to the archive file
            limit: Maximum number of entries to return (None = no limit)
            offset: Number of entries to skip
            filter_pattern: Glob pattern to filter entries
            dirs_only: Show only directories
            files_only: Show only files (not directories)
            summary_only: Return only summary statistics

        Returns:
            Dictionary containing file list and metadata

        Raises:
            FileNotFoundError: If archive doesn't exist
            UnsupportedFormatError: If format is not supported for listing
            ListingError: If listing fails
        """
        archive_obj = Path(archive_path)

        if not archive_obj.exists():
            raise FileNotFoundError(f"Archive not found: {archive_obj}")

        if not self._is_supported_format(archive_obj):
            raise UnsupportedFormatError(
                f"Format {archive_obj.suffix} is not supported for listing. "
                f"Supported formats for direct listing: {', '.join(self._get_supported_formats())}"
            )

        try:
            logger.info(f"Listing archive contents: {archive_obj}")

            # Get file list from archive
            files = self._extract_file_list(archive_obj)

            # Apply filters
            if dirs_only:
                files = [f for f in files if f.is_directory]
            elif files_only:
                files = [f for f in files if not f.is_directory]

            if filter_pattern:
                files = self._apply_filter(files, filter_pattern)

            # Sort files by path to maintain consistent ordering before pagination
            files = sorted(files, key=lambda f: f.path.lower())

            # Calculate statistics
            total_count = len(files)
            total_size = sum(f.size for f in files if not f.is_directory)
            total_compressed_size = sum(
                f.compressed_size for f in files if not f.is_directory
            )

            # Handle summary-only mode
            if summary_only:
                return {
                    "archive_path": str(archive_obj),
                    "format": archive_obj.suffix,
                    "total_files": len([f for f in files if not f.is_directory]),
                    "total_directories": len([f for f in files if f.is_directory]),
                    "total_entries": total_count,
                    "total_size": total_size,
                    "total_compressed_size": total_compressed_size,
                    "compression_ratio": (
                        100.0 * (1 - total_compressed_size / total_size)
                        if total_size > 0
                        else 0.0
                    ),
                    "files": [],  # Empty for summary mode
                    "showing_range": None,
                    "has_more": False,
                }

            # Apply pagination
            paginated_files = files[offset : offset + limit if limit else None]

            # Determine if there are more entries
            # - With limit: check if we have more after current page
            # - With offset only: check if we skipped any entries (offset > 0)
            # - With both: standard pagination check
            if limit is not None:
                # Standard pagination with limit
                has_more = (offset + len(paginated_files)) < total_count
            elif offset > 0:
                # Offset only: indicate there were skipped entries
                has_more = True
            else:
                # No pagination at all
                has_more = False

            return {
                "archive_path": str(archive_obj),
                "format": archive_obj.suffix,
                "total_files": len([f for f in files if not f.is_directory]),
                "total_directories": len([f for f in files if f.is_directory]),
                "total_entries": total_count,
                "total_size": total_size,
                "total_compressed_size": total_compressed_size,
                "compression_ratio": (
                    100.0 * (1 - total_compressed_size / total_size)
                    if total_size > 0
                    else 0.0
                ),
                "files": paginated_files,
                "showing_range": (
                    f"{offset + 1}-{offset + len(paginated_files)} of {total_count}"
                    if limit is not None or offset > 0
                    else f"All {total_count} entries"
                ),
                "has_more": has_more,
            }

        except Exception as e:
            raise ListingError(f"Failed to list archive contents: {e}") from e

    def _extract_file_list(self, archive_path: Path) -> list[ArchiveFile]:
        """Extract file list from archive using py7zz improved API.

        Args:
            archive_path: Path to the archive

        Returns:
            List of ArchiveFile objects with detailed metadata

        Raises:
            ListingError: If extraction fails
        """
        try:
            files = []

            # Use py7zz.SevenZipFile for detailed file information
            # py7zz v1.0.0 removed file list from get_archive_info, use SevenZipFile instead
            with py7zz.SevenZipFile(str(archive_path), "r") as archive:
                # Get detailed information about each file
                for info in archive.infolist():
                    try:
                        # Create ArchiveFile object from ArchiveInfo
                        file_obj = self._create_archive_file_from_info(info)
                        if file_obj:
                            files.append(file_obj)
                    except Exception as e:
                        logger.debug(f"Error processing file info: {e}")
                        continue

            logger.debug(f"Extracted {len(files)} entries from archive")
            return files

        except py7zz.FileNotFoundError as e:
            raise ListingError(f"Archive file not found: {archive_path}") from e
        except py7zz.CorruptedArchiveError as e:
            raise ListingError(f"Archive is corrupted: {archive_path}") from e
        except py7zz.UnsupportedFormatError as e:
            raise ListingError(f"Unsupported archive format: {archive_path}") from e
        except py7zz.Py7zzError as e:
            raise ListingError(f"py7zz error: {e}") from e
        except Exception as e:
            raise ListingError(f"Failed to extract file list from archive: {e}") from e

    def _create_archive_file_from_info(self, info: Any) -> Optional[ArchiveFile]:
        """Create ArchiveFile from py7zz ArchiveInfo object.

        Args:
            info: py7zz ArchiveInfo object

        Returns:
            ArchiveFile object or None if creation fails
        """
        try:
            # Get filename from ArchiveInfo
            path = info.filename.replace("\\", "/")

            # Determine if it's a directory using py7zz API methods
            is_directory = False

            # Try multiple approaches to detect directories
            if hasattr(info, "is_dir") and callable(info.is_dir):
                # Use is_dir() method (recommended py7zz API)
                is_directory = info.is_dir()
            elif hasattr(info, "isdir") and callable(info.isdir):
                # Use isdir() method (zipfile compatible)
                is_directory = info.isdir()
            elif hasattr(info, "type"):
                # Check type attribute
                is_directory = info.type == "dir"
            elif path.endswith("/"):
                # Fallback: directories often end with /
                is_directory = True

            # Extract size information using correct py7zz attribute names
            size = getattr(info, "file_size", 0)
            compressed_size = getattr(info, "compress_size", 0)

            # Additional fallback for size attributes with alternative names
            if size == 0 and hasattr(info, "uncompressed_size"):
                size = getattr(info, "uncompressed_size", 0)
            if compressed_size == 0 and hasattr(info, "compressed_size"):
                compressed_size = getattr(info, "compressed_size", 0)

            # Try to get modification time if available
            modified = None
            if hasattr(info, "date_time"):
                try:
                    from datetime import datetime

                    modified = datetime(*info.date_time)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse modification time from info.date_time={getattr(info, 'date_time', None)}: {e}"
                    )

            # Try to get CRC if available
            crc = None
            if hasattr(info, "CRC"):
                crc = f"{info.CRC:08x}"

            logger.debug(
                f"Created ArchiveFile: path='{path}', is_dir={is_directory}, size={size}, compressed={compressed_size}"
            )

            return ArchiveFile(
                path=path,
                size=size,
                compressed_size=compressed_size,
                modified=modified,
                is_directory=is_directory,
                crc=crc,
            )

        except Exception as e:
            logger.debug(f"Error creating ArchiveFile from info: {e}")
            # Log available attributes for debugging
            if hasattr(info, "__dict__"):
                logger.debug(f"Available attributes: {list(info.__dict__.keys())}")
            elif hasattr(info, "__slots__"):
                logger.debug(f"Available slots: {info.__slots__}")
            return None

    def _apply_filter(
        self, files: list[ArchiveFile], pattern: str
    ) -> list[ArchiveFile]:
        """Apply glob pattern filter to file list.

        Args:
            files: List of files to filter
            pattern: Glob pattern to match against file paths

        Returns:
            Filtered list of files
        """
        try:
            # Convert glob pattern to match both full paths and filenames
            filtered_files = []

            for file in files:
                # Match against full path
                if fnmatch.fnmatch(file.path, pattern) or fnmatch.fnmatch(
                    file.name, pattern
                ):
                    filtered_files.append(file)

            logger.debug(
                f"Filter '{pattern}' matched {len(filtered_files)} of {len(files)} entries"
            )
            return filtered_files

        except Exception as e:
            logger.warning(f"Filter pattern '{pattern}' failed: {e}")
            return files  # Return unfiltered list on filter error

    def _is_supported_format(self, file_path: Path) -> bool:
        """Check if file format is supported for direct listing.

        Args:
            file_path: Path to the file

        Returns:
            True if format is supported for listing
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

    def _get_supported_formats(self) -> list[str]:
        """Get list of supported formats for listing.

        Returns:
            List of supported format extensions
        """
        return sorted(SUPPORTED_INPUT_FORMATS)

    def get_quick_info(self, archive_path: Union[str, Path]) -> dict[str, Any]:
        """Get quick archive information without listing all files.

        Args:
            archive_path: Path to the archive

        Returns:
            Dictionary with basic archive information

        Raises:
            FileNotFoundError: If archive doesn't exist
            UnsupportedFormatError: If format is not supported
            ListingError: If info extraction fails
        """
        archive_obj = Path(archive_path)

        if not archive_obj.exists():
            raise FileNotFoundError(f"Archive not found: {archive_obj}")

        if not self._is_supported_format(archive_obj):
            raise UnsupportedFormatError(f"Unsupported format: {archive_obj.suffix}")

        try:
            logger.debug(f"Getting quick info for: {archive_obj}")

            with py7zz.SevenZipFile(str(archive_obj), "r") as archive:
                name_list = archive.namelist()

                # Quick statistics
                total_entries = len(name_list)
                directories = sum(1 for name in name_list if name.endswith("/"))
                files = total_entries - directories

                # Get archive file size
                archive_size = archive_obj.stat().st_size

                return {
                    "archive_path": str(archive_obj),
                    "format": archive_obj.suffix,
                    "archive_size": archive_size,
                    "total_entries": total_entries,
                    "total_files": files,
                    "total_directories": directories,
                }

        except Exception as e:
            raise ListingError(f"Failed to get archive info: {e}") from e


def list_archive_contents(
    archive_path: Union[str, Path],
    limit: Optional[int] = None,
    offset: int = 0,
    filter_pattern: Optional[str] = None,
    dirs_only: bool = False,
    files_only: bool = False,
    summary_only: bool = False,
) -> dict[str, Any]:
    """Convenience function to list archive contents.

    Args:
        archive_path: Path to the archive
        limit: Maximum number of entries to return
        offset: Number of entries to skip
        filter_pattern: Glob pattern to filter entries
        dirs_only: Show only directories
        files_only: Show only files
        summary_only: Return only summary statistics

    Returns:
        Dictionary containing file list and metadata

    Raises:
        ListingError: If listing fails
    """
    lister = ArchiveLister()
    return lister.list_archive(
        archive_path=archive_path,
        limit=limit,
        offset=offset,
        filter_pattern=filter_pattern,
        dirs_only=dirs_only,
        files_only=files_only,
        summary_only=summary_only,
    )
