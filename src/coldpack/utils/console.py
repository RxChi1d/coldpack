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
    if platform.system().lower() == "windows" and "PYTHONIOENCODING" not in os.environ:
        # Set environment variable to hint Python about encoding preference
        os.environ["PYTHONIOENCODING"] = "utf-8"

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

    try:
        console.print(message)
    except UnicodeEncodeError:
        # Replace problematic Unicode characters with safe alternatives
        safe_message = message
        for unicode_char, replacement in fallback_chars.items():
            safe_message = safe_message.replace(unicode_char, replacement)
        console.print(safe_message)
