"""Windows compatibility utilities for coldpack.

This module provides Windows-specific compatibility checks and utilities,
primarily focused on addressing limitations of Windows versions of certain tools.
"""

import platform
import sys
from pathlib import Path
from typing import Optional, Union

from loguru import logger
from rich.console import Console

from .console import create_windows_compatible_console


def check_windows_par2_unicode_compatibility(
    path: Union[str, Path], console: Optional[Console] = None
) -> None:
    """Check if the given path contains non-ASCII characters on Windows with PAR2.

    Windows version of par2cmdline-turbo does not support Unicode (non-ASCII)
    characters in file paths. This function checks for this limitation and
    raises an appropriate error if incompatible paths are detected.

    Args:
        path: File or directory path to check
        console: Rich console for output (optional)

    Raises:
        SystemExit: If Windows PAR2 Unicode incompatibility is detected
    """
    if not console:
        console = create_windows_compatible_console()

    # Only check on Windows
    if platform.system().lower() != "windows":
        return

    # Convert to Path object if string
    if isinstance(path, str):
        path = Path(path)

    # Get absolute path string for checking
    abs_path_str = str(path.resolve())

    # Check if path contains non-ASCII characters
    try:
        abs_path_str.encode("ascii")
        # If we get here, the path is ASCII-only, so it's safe
        logger.debug(f"Path ASCII compatibility check passed: {abs_path_str}")
        return
    except UnicodeEncodeError:
        # Path contains non-ASCII characters
        pass

    # Display detailed error message
    console.print("[red]ERROR: Windows PAR2 Unicode Path Compatibility[/red]")
    console.print()

    # Try to display path safely, encoding issues with Chinese characters
    try:
        console.print(f"[yellow]Path:[/yellow] {abs_path_str}")
    except UnicodeEncodeError:
        # If path display fails, show a safe version
        safe_path = abs_path_str.encode("ascii", errors="replace").decode("ascii")
        console.print(
            f"[yellow]Path:[/yellow] {safe_path} [dim](contains Unicode chars)[/dim]"
        )

    console.print()
    console.print(
        "[red]The specified path contains non-ASCII characters, but the[/red]"
    )
    console.print(
        "[red]Windows version of par2cmdline-turbo does not support Unicode paths.[/red]"
    )
    console.print()
    console.print(
        "[yellow]This is a known limitation of the Windows par2cmdline-turbo package.[/yellow]"
    )
    console.print()
    console.print("[cyan]Recommended solutions:[/cyan]")
    console.print("  1. Move your files to a path with only ASCII characters")
    console.print("     (A-Z, a-z, 0-9, and basic punctuation)")
    console.print("  2. Use coldpack on Linux or macOS instead")
    console.print("  3. Use Windows Subsystem for Linux (WSL)")
    console.print()
    console.print(
        "[dim]Example ASCII-safe path: C:\\Users\\Username\\Documents\\archive\\[/dim]"
    )

    # Show non-ASCII characters found, safely
    try:
        non_ascii_info = _get_non_ascii_chars(abs_path_str)
        console.print(f"[dim]Non-ASCII characters found: {non_ascii_info}[/dim]")
    except UnicodeEncodeError:
        console.print("[dim]Non-ASCII characters found in path[/dim]")

    # Exit with error code
    sys.exit(1)


def _get_non_ascii_chars(text: str) -> str:
    """Get the non-ASCII characters found in the text for display purposes.

    Args:
        text: Text to analyze

    Returns:
        String showing the non-ASCII characters found
    """
    non_ascii_chars = []
    for char in text:
        try:
            char.encode("ascii")
        except UnicodeEncodeError:
            if char not in non_ascii_chars:
                non_ascii_chars.append(char)

    if non_ascii_chars:
        char_list = ", ".join(f"'{char}'" for char in non_ascii_chars[:5])
        if len(non_ascii_chars) > 5:
            char_list += f" (and {len(non_ascii_chars) - 5} more)"
        return char_list
    return "unknown Unicode characters"


def check_par2_related_paths_compatibility(
    source_path: Union[str, Path],
    output_dir: Union[str, Path],
    console: Optional[Console] = None,
) -> None:
    """Check PAR2 compatibility for both source and output paths.

    This function checks both the source file/directory path and the output
    directory path for Windows PAR2 Unicode compatibility issues.

    Args:
        source_path: Source file or directory path
        output_dir: Output directory path
        console: Rich console for output (optional)

    Raises:
        SystemExit: If Windows PAR2 Unicode incompatibility is detected
    """
    if not console:
        console = create_windows_compatible_console()

    # Only check on Windows
    if platform.system().lower() != "windows":
        return

    logger.debug("Performing Windows PAR2 Unicode compatibility check")

    # Check source path
    check_windows_par2_unicode_compatibility(source_path, console)

    # Check output directory
    check_windows_par2_unicode_compatibility(output_dir, console)

    logger.debug("Windows PAR2 Unicode compatibility check passed")
