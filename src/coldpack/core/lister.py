"""Archive content listing functionality using py7zz."""

import fnmatch
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import py7zz  # type: ignore
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
            has_more = (
                limit is not None and (offset + len(paginated_files)) < total_count
            )

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
                    if limit is not None
                    else f"All {total_count} entries"
                ),
                "has_more": has_more,
            }

        except Exception as e:
            raise ListingError(f"Failed to list archive contents: {e}") from e

    def _extract_file_list(self, archive_path: Path) -> list[ArchiveFile]:
        """Extract file list from archive using py7zz run_7z with detailed info.

        Args:
            archive_path: Path to the archive

        Returns:
            List of ArchiveFile objects with detailed metadata

        Raises:
            ListingError: If extraction fails
        """
        try:
            files = []

            # Use 7zz l -slt to get detailed technical listing
            result = py7zz.run_7z(["l", "-slt", str(archive_path)])

            if result.returncode != 0:
                raise ListingError(
                    f"7zz command failed with code {result.returncode}: {result.stderr}"
                )

            # Parse the technical format output
            files = self._parse_slt_output(result.stdout)

            logger.debug(f"Extracted {len(files)} entries from archive")
            return files

        except subprocess.CalledProcessError as e:
            raise ListingError(f"Failed to run 7zz command: {e}") from e
        except Exception as e:
            raise ListingError(f"Failed to extract file list from archive: {e}") from e

    def _parse_slt_output(self, output: str) -> list[ArchiveFile]:
        """Parse 7zz l -slt technical format output.

        Args:
            output: The stdout from 7zz l -slt command

        Returns:
            List of ArchiveFile objects with detailed metadata
        """
        files: list[ArchiveFile] = []

        # Find the data section (after "----------")
        sections = output.split("----------")
        if len(sections) < 2:
            return files

        data_section = sections[1]

        # Split into individual file entries - each entry starts with "Path = "
        file_entries: list[str] = []
        current_entry: list[str] = []

        for line in data_section.split("\n"):
            line = line.strip()
            if line.startswith("Path = "):
                # Start of a new file entry
                if current_entry:
                    file_entries.append("\n".join(current_entry))
                current_entry = [line]
            elif line and current_entry:
                # Continue current entry
                current_entry.append(line)

        # Don't forget the last entry
        if current_entry:
            file_entries.append("\n".join(current_entry))

        # Parse each file entry
        for entry in file_entries:
            try:
                file_info = self._parse_file_section(entry.strip())
                if file_info:
                    files.append(file_info)
            except Exception as e:
                logger.debug(f"Error parsing file entry: {e}")
                continue

        return files

    def _parse_file_section(self, section: str) -> Optional[ArchiveFile]:
        """Parse a single file section from 7zz -slt output.

        Args:
            section: A single file section from the output

        Returns:
            ArchiveFile object or None if parsing fails
        """
        if not section.strip():
            return None

        # Parse key-value pairs
        properties = {}
        for line in section.split("\n"):
            line = line.strip()
            if not line:
                continue
            if " = " in line:
                key, value = line.split(" = ", 1)
                properties[key.strip()] = value.strip()

        # Extract required fields
        path = properties.get("Path", "")
        if not path:
            return None

        # Normalize path separators
        path = path.replace("\\", "/")

        # Parse size (default to 0 if empty or invalid)
        try:
            size = int(properties.get("Size", "0") or "0")
        except ValueError:
            size = 0

        # Parse compressed size (default to 0 if empty or invalid)
        try:
            compressed_size = int(properties.get("Packed Size", "0") or "0")
        except ValueError:
            compressed_size = 0

        # Parse modification time
        modified = None
        modified_str = properties.get("Modified", "")
        if modified_str:
            try:
                # Format: "2025-07-22 00:05:10.3517944"
                # Remove microseconds part for simpler parsing
                if "." in modified_str:
                    modified_str = modified_str.split(".")[0]
                modified = datetime.strptime(modified_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.debug(f"Failed to parse modification time: {modified_str}")

        # Determine if it's a directory from attributes
        attributes = properties.get("Attributes", "")
        is_directory = attributes.startswith("D ")

        # Extract CRC if available
        crc = properties.get("CRC", "") or None
        if crc == "":
            crc = None

        return ArchiveFile(
            path=path,
            size=size,
            compressed_size=compressed_size,
            modified=modified,
            is_directory=is_directory,
            crc=crc,
        )

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
