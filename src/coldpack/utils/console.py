"""Rich Console utilities with Windows compatibility.

This module provides Windows-compatible Rich Console instances that handle
Unicode characters properly across different terminal environments.
"""

import os
import platform
from typing import Any, Optional

from rich.console import Console


def create_windows_compatible_console(**kwargs: Any) -> Console:
    """Create a Rich Console instance with Windows compatibility.

    This function creates a Console instance that handles Unicode characters
    properly on Windows systems, avoiding cp950 encoding issues.

    Args:
        **kwargs: Additional arguments passed to Console constructor

    Returns:
        Rich Console instance with Windows compatibility
    """
    # Set default arguments for Windows compatibility
    console_args = {
        "force_terminal": True,
        "legacy_windows": False,  # Force modern terminal mode
        **kwargs,
    }

    # On Windows, try to ensure UTF-8 handling
    if platform.system().lower() == "windows":
        # Always set UTF-8 encoding for Windows
        os.environ["PYTHONIOENCODING"] = "utf-8"
        # Also try to set console output encoding
        try:
            import sys

            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            # Fallback for older Python versions or unsupported terminals
            pass

    console = Console(**console_args)

    return console


def safe_print(
    console: Console, message: str, fallback_chars: Optional[dict[str, str]] = None
) -> None:
    """Safely print a message with fallback for encoding issues.

    Args:
        console: Rich Console instance
        message: Message to print
        fallback_chars: Dictionary mapping problematic chars to safe alternatives
    """
    if fallback_chars is None:
        fallback_chars = {
            "✓": "[OK]",
            "✗": "[FAIL]",
            "→": "->",
            "←": "<-",
            "⚠": "[WARN]",
            "🔍": "[SEARCH]",
            "📁": "[FOLDER]",
            "📄": "[FILE]",
        }

    # On Windows, always use safe message first to avoid encoding issues
    if platform.system().lower() == "windows":
        safe_message = message
        for unicode_char, replacement in fallback_chars.items():
            safe_message = safe_message.replace(unicode_char, replacement)
        try:
            console.print(safe_message)
            return
        except UnicodeEncodeError:
            # If even the safe message fails, strip all non-ASCII
            ascii_message = safe_message.encode("ascii", errors="replace").decode(
                "ascii"
            )
            console.print(ascii_message)
            return

    # Non-Windows systems: try original first, then fallback
    try:
        console.print(message)
    except UnicodeEncodeError:
        # Replace problematic Unicode characters with safe alternatives
        safe_message = message
        for unicode_char, replacement in fallback_chars.items():
            safe_message = safe_message.replace(unicode_char, replacement)
        try:
            console.print(safe_message)
        except UnicodeEncodeError:
            # Last resort: strip all non-ASCII
            ascii_message = safe_message.encode("ascii", errors="replace").decode(
                "ascii"
            )
            console.print(ascii_message)
