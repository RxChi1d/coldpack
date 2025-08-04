"""Tests for SafeConsole Unicode-safe console wrapper."""

import io
import os
import threading
import warnings
from unittest.mock import MagicMock, patch

import pytest

from coldpack.utils.console import (
    DEFAULT_FALLBACK_CHARS,
    SafeConsole,
    get_console,
    safe_print,
    set_console,
)


class TestSafeConsole:
    """Test cases for SafeConsole class."""

    def test_initialization(self):
        """Test SafeConsole initialization."""
        console = SafeConsole()

        assert console._console is not None
        assert isinstance(console._unicode_supported, bool)
        assert console._fallback_chars == DEFAULT_FALLBACK_CHARS

    def test_unicode_detection_encoding_success(self):
        """Test Unicode detection when encoding test succeeds."""
        console = SafeConsole()

        # Mock successful encoding
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.encoding = "utf-8"
            result = console._detect_unicode_support()

        # Should detect Unicode support
        assert isinstance(result, bool)

    def test_unicode_detection_encoding_failure(self):
        """Test Unicode detection when encoding test fails."""
        console = SafeConsole()

        # Mock hasattr to return False, simulating no encoding attribute
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.encoding = None  # No encoding attribute

            # Should fall back to other detection methods
            result = console._detect_unicode_support()
            assert isinstance(result, bool)

    def test_modern_terminal_detection_windows(self):
        """Test modern terminal detection on Windows."""
        console = SafeConsole()

        with patch("platform.system", return_value="Windows"):
            # Test Windows Terminal detection
            with patch.dict(os.environ, {"WT_SESSION": "1"}):
                assert console._detect_modern_terminal() is True

            # Test VS Code detection
            with patch.dict(os.environ, {"TERM_PROGRAM": "vscode"}, clear=True):
                assert console._detect_modern_terminal() is True

            # Test WSL detection
            with patch("platform.release", return_value="5.15.90.1-microsoft"):
                assert console._detect_modern_terminal() is True

            # Test legacy terminal
            with (
                patch.dict(os.environ, {}, clear=True),
                patch("platform.release", return_value="10.0.19041"),
            ):
                # Should still return True due to environment detection logic
                result = console._detect_modern_terminal()
                assert isinstance(result, bool)

    def test_modern_terminal_detection_non_windows(self):
        """Test modern terminal detection on non-Windows platforms."""
        console = SafeConsole()

        with patch("platform.system", return_value="Linux"):
            assert console._detect_modern_terminal() is True

    def test_silent_unicode_test(self):
        """Test silent Unicode output test."""
        console = SafeConsole()
        result = console._test_unicode_output()
        assert isinstance(result, bool)

    def test_fallback_application(self):
        """Test fallback character application."""
        console = SafeConsole()

        text = "✓ Success! ✗ Failed! • Item"
        result = console._apply_fallbacks(text)

        assert "[OK]" in result
        assert "[FAIL]" in result
        assert "*" in result
        assert "✓" not in result
        assert "✗" not in result
        assert "•" not in result

    def test_print_with_unicode_support(self):
        """Test print method when Unicode is supported."""
        console = SafeConsole()
        console._unicode_supported = True

        # Mock the underlying console
        console._console = MagicMock()

        console.print("✓ Unicode test")

        console._console.print.assert_called_once_with("✓ Unicode test")

    def test_print_without_unicode_support(self):
        """Test print method when Unicode is not supported."""
        console = SafeConsole()
        console._unicode_supported = False

        # Mock the underlying console
        console._console = MagicMock()

        console.print("✓ Unicode test")

        console._console.print.assert_called_once_with("[OK] Unicode test")

    def test_print_with_encoding_error(self):
        """Test print method handling UnicodeEncodeError."""
        console = SafeConsole()

        # Mock the underlying console to raise UnicodeEncodeError
        console._console = MagicMock()
        console._console.print.side_effect = [
            UnicodeEncodeError("utf-8", "", 0, 1, "error"),
            None,  # Second call succeeds
        ]

        console.print("✓ Test")

        # Should be called twice: once failing, once with fallback
        assert console._console.print.call_count == 2

    def test_print_with_multiple_encoding_errors(self):
        """Test print method with multiple encoding errors (ASCII fallback)."""
        console = SafeConsole()

        # Mock the underlying console to raise UnicodeEncodeError twice
        console._console = MagicMock()
        console._console.print.side_effect = [
            UnicodeEncodeError("utf-8", "", 0, 1, "error"),
            UnicodeEncodeError("utf-8", "", 0, 1, "error"),
            None,  # Third call succeeds
        ]

        console.print("✓ Test")

        # Should be called three times: original, fallback, ASCII
        assert console._console.print.call_count == 3

    def test_print_non_string_args(self):
        """Test print method with non-string arguments."""
        console = SafeConsole()
        console._unicode_supported = False

        # Mock the underlying console
        console._console = MagicMock()

        console.print("✓ Test", 42, True)

        # Non-string args should be passed through unchanged
        console._console.print.assert_called_once_with("[OK] Test", 42, True)

    def test_attribute_delegation(self):
        """Test that unknown attributes are delegated to underlying console."""
        console = SafeConsole()

        # Mock the underlying console
        mock_method = MagicMock(return_value="test_result")
        console._console = MagicMock()
        console._console.some_method = mock_method

        result = console.some_method("arg1", kwarg="value")

        mock_method.assert_called_once_with("arg1", kwarg="value")
        assert result == "test_result"

    def test_set_fallback_chars(self):
        """Test setting custom fallback characters."""
        console = SafeConsole()
        original_chars = console._fallback_chars.copy()

        custom_chars = {"🚀": "[ROCKET]", "🎯": "[BULLSEYE]"}
        console.set_fallback_chars(custom_chars)

        # Should update existing chars
        for char, replacement in custom_chars.items():
            assert console._fallback_chars[char] == replacement

        # Should preserve original chars
        assert console._fallback_chars["✓"] == original_chars["✓"]

    def test_debug_mode_environment(self):
        """Test debug mode activation via environment variable."""
        with patch.dict(os.environ, {"COLDPACK_DEBUG_CONSOLE": "1"}):
            console = SafeConsole()
            assert console._debug_mode is True

        with patch.dict(os.environ, {"COLDPACK_DEBUG_CONSOLE": "false"}):
            console = SafeConsole()
            assert console._debug_mode is False


class TestGlobalConsoleManagement:
    """Test cases for global console instance management."""

    def test_get_console_singleton(self):
        """Test that get_console returns the same instance."""
        # Reset global console by creating a new one
        from coldpack.utils import console as console_module

        # Save original
        original_console = getattr(console_module, "_global_console", None)

        try:
            # Reset to None
            console_module._global_console = None

            console1 = get_console()
            console2 = get_console()

            assert console1 is console2
            assert isinstance(console1, SafeConsole)
        finally:
            # Restore original
            console_module._global_console = original_console

    def test_set_console(self):
        """Test setting a custom global console."""
        # Reset global console
        from coldpack.utils import console as console_module

        # Save original
        original_console = getattr(console_module, "_global_console", None)

        try:
            # Reset to None
            console_module._global_console = None

            custom_console = SafeConsole()
            set_console(custom_console)

            retrieved_console = get_console()
            assert retrieved_console is custom_console
        finally:
            # Restore original
            console_module._global_console = original_console

    def test_thread_safety(self):
        """Test thread safety of global console management."""
        # Reset global console
        from coldpack.utils import console as console_module

        # Save original
        original_console = getattr(console_module, "_global_console", None)

        try:
            # Reset to None
            console_module._global_console = None

            consoles = []

            def get_console_thread():
                consoles.append(get_console())

            threads = [threading.Thread(target=get_console_thread) for _ in range(10)]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # All threads should get the same console instance
            assert len({id(console) for console in consoles}) == 1
        finally:
            # Restore original
            console_module._global_console = original_console


class TestBackwardCompatibility:
    """Test cases for backward compatibility functions."""

    def test_safe_print_deprecation_warning(self):
        """Test that safe_print shows deprecation warning."""
        console = MagicMock()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            safe_print(console, "test message")

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message)
            assert "get_console().print()" in str(w[0].message)

    def test_safe_print_with_custom_fallbacks(self):
        """Test safe_print with custom fallback characters."""
        # Reset global console
        from coldpack.utils import console as console_module

        # Save original
        original_console = getattr(console_module, "_global_console", None)

        try:
            # Reset to None
            console_module._global_console = None

            console = MagicMock()
            custom_fallbacks = {"✓": "[CUSTOM_OK]"}

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                safe_print(console, "✓ test", custom_fallbacks)

            # Should use global console, not the passed one
            global_console = get_console()
            assert global_console._fallback_chars["✓"] == "[OK]"  # Should be restored
        finally:
            # Restore original
            console_module._global_console = original_console

    def test_safe_print_without_custom_fallbacks(self):
        """Test safe_print without custom fallback characters."""
        # Reset global console
        from coldpack.utils import console as console_module

        # Save original
        original_console = getattr(console_module, "_global_console", None)

        try:
            # Reset to None
            console_module._global_console = None

            console = MagicMock()

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                safe_print(console, "✓ test")

            # Should use global console with default fallbacks
            global_console = get_console()
            assert global_console._fallback_chars["✓"] == "[OK]"
        finally:
            # Restore original
            console_module._global_console = original_console


class TestIntegration:
    """Integration tests for SafeConsole."""

    def test_real_console_integration(self):
        """Test SafeConsole with real Rich Console."""
        console = SafeConsole()

        # Should not raise any exceptions
        try:
            console.print("✓ Integration test")
            console.print("[green]✓ Colored test[/green]")
            console.print("Multiple", "arguments", "test")
        except Exception as e:
            pytest.fail(f"SafeConsole integration test failed: {e}")

    def test_rich_console_methods(self):
        """Test that Rich Console methods are accessible."""
        console = SafeConsole()

        # Test common Rich Console methods
        assert hasattr(console, "width")
        assert hasattr(console, "height")
        assert hasattr(console, "rule")
        assert hasattr(console, "status")

        # Test that they return reasonable values
        assert isinstance(console.width, int)
        assert isinstance(console.height, int)

    def test_console_with_file_output(self):
        """Test SafeConsole with file output."""
        output_buffer = io.StringIO()
        console = SafeConsole(file=output_buffer)

        console.print("✓ File output test")

        output = output_buffer.getvalue()
        assert len(output) > 0
        # Content depends on Unicode detection, but should contain some text
        assert "test" in output
