"""Rich Console utilities with Windows compatibility.

This module provides Windows-compatible Rich Console instances that handle
Unicode characters properly across different terminal environments.
"""

import io
import os
import platform
import sys
import threading
import warnings
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

    .. deprecated:: 0.4.0
        Use `get_console().print()` instead for better Unicode handling.

    Args:
        console: Rich Console instance (ignored, uses global console)
        message: Message to print
        fallback_chars: Dictionary mapping problematic chars to safe alternatives
    """
    warnings.warn(
        "safe_print is deprecated and will be removed in v0.5.0. "
        "Use get_console().print() instead for better Unicode handling.",
        DeprecationWarning,
        stacklevel=2,
    )

    global_console = get_console()
    if fallback_chars:
        # Apply custom fallback if provided
        original_fallbacks = global_console._fallback_chars.copy()
        global_console.set_fallback_chars(fallback_chars)
        try:
            global_console.print(message)
        finally:
            # Restore original fallbacks
            global_console._fallback_chars = original_fallbacks
    else:
        global_console.print(message)


# Default fallback character mappings
DEFAULT_FALLBACK_CHARS = {
    "✓": "[OK]",
    "✗": "[FAIL]",
    "⚠": "[WARN]",
    "ℹ": "[INFO]",
    "→": "->",
    "←": "<-",
    "📁": "[FOLDER]",
    "📄": "[FILE]",
    "🔍": "[SEARCH]",
    "⏳": "[WAIT]",
    "🚀": "[START]",
    "🎯": "[TARGET]",
    "•": "*",
}

# Global console instance management
_global_console: Optional["SafeConsole"] = None
_global_console_lock = threading.Lock()


class SafeConsole:
    """Unicode-safe console wrapper with intelligent capability detection."""

    def __init__(self, **console_kwargs: Any) -> None:
        """Initialize SafeConsole with intelligent Unicode detection.

        Args:
            **console_kwargs: Arguments passed to create_windows_compatible_console
        """
        self._console = create_windows_compatible_console(**console_kwargs)
        self._unicode_supported = self._detect_unicode_support()
        self._fallback_chars = DEFAULT_FALLBACK_CHARS.copy()
        self._debug_mode = os.environ.get("COLDPACK_DEBUG_CONSOLE", "").lower() in (
            "1",
            "true",
            "yes",
        )

    def _detect_unicode_support(self) -> bool:
        """Detect terminal Unicode support using multiple methods."""
        # Method 1: Direct encoding test
        try:
            test_chars = "✓✗⚠ℹ→"
            if hasattr(sys.stdout, "encoding") and sys.stdout.encoding:
                test_chars.encode(sys.stdout.encoding)
                return True
        except (UnicodeEncodeError, LookupError, AttributeError):
            # Encoding test failed, fall back to other detection methods
            pass

        # Method 2: Modern terminal detection
        if self._detect_modern_terminal():
            return True

        # Method 3: Silent output test
        return self._test_unicode_output()

    def _detect_modern_terminal(self) -> bool:
        """Detect modern terminal environments."""
        if platform.system().lower() == "windows":
            # Windows Terminal, PowerShell Core, or WSL
            return (
                bool(os.environ.get("WT_SESSION"))  # Windows Terminal
                or os.environ.get("TERM_PROGRAM") == "vscode"  # VS Code
                or "microsoft" in platform.release().lower()  # WSL
            )
        # Assume modern terminals on non-Windows platforms
        return True

    def _test_unicode_output(self) -> bool:
        """Test Unicode output capability using silent test."""
        try:
            # Create a string buffer to capture output
            test_buffer = io.StringIO()
            test_console = Console(file=test_buffer, force_terminal=False)
            test_console.print("✓")
            output = test_buffer.getvalue()
            return "✓" in output
        except (UnicodeEncodeError, Exception):
            return False

    def _apply_fallbacks(self, text: str) -> str:
        """Apply fallback characters to text."""
        result = text
        for unicode_char, replacement in self._fallback_chars.items():
            result = result.replace(unicode_char, replacement)
        return result

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print with automatic Unicode/fallback handling."""
        if not args:
            self._console.print(*args, **kwargs)
            return

        # Convert all positional arguments to strings and process them
        processed_args = []
        for arg in args:
            if isinstance(arg, str):
                if self._unicode_supported:
                    processed_args.append(arg)
                else:
                    processed_args.append(self._apply_fallbacks(arg))
            else:
                processed_args.append(arg)

        try:
            self._console.print(*processed_args, **kwargs)
        except UnicodeEncodeError as e:
            if self._debug_mode:
                sys.stderr.write(
                    f"Unicode encoding failed: {e}. "
                    f"Terminal: {os.environ.get('TERM', 'unknown')}. "
                    f"Encoding: {getattr(sys.stdout, 'encoding', 'unknown')}. "
                    f"Falling back...\n"
                )
            # Apply fallbacks and retry
            fallback_args = []
            for arg in args:
                if isinstance(arg, str):
                    fallback_args.append(self._apply_fallbacks(arg))
                else:
                    fallback_args.append(arg)

            try:
                self._console.print(*fallback_args, **kwargs)
            except UnicodeEncodeError:
                # Last resort: ASCII-only
                ascii_args = []
                for arg in fallback_args:
                    if isinstance(arg, str):
                        ascii_arg = arg.encode("ascii", errors="replace").decode(
                            "ascii"
                        )
                        ascii_args.append(ascii_arg)
                    else:
                        ascii_args.append(arg)  # type: ignore[unreachable]
                self._console.print(*ascii_args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Delegate all other methods to underlying Rich Console."""
        return getattr(self._console, name)

    def set_fallback_chars(self, fallback_chars: dict[str, str]) -> None:
        """Set custom fallback character mappings.

        Args:
            fallback_chars: Dictionary mapping Unicode chars to ASCII alternatives
        """
        self._fallback_chars.update(fallback_chars)


def get_console() -> SafeConsole:
    """Get the global SafeConsole instance (singleton pattern).

    Returns:
        Global SafeConsole instance
    """
    global _global_console

    if _global_console is None:
        with _global_console_lock:
            # Double-check locking pattern
            if _global_console is None:
                _global_console = SafeConsole()

    return _global_console


def set_console(console: SafeConsole) -> None:
    """Set a custom global SafeConsole instance.

    Args:
        console: SafeConsole instance to use globally
    """
    global _global_console

    with _global_console_lock:
        _global_console = console
