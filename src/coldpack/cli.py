"""Typer-based CLI interface for coldpack cold storage archiver."""

import sys
from pathlib import Path
from typing import Any, Optional

import typer
from loguru import logger
from rich.table import Table

from . import __version__
from .config.constants import (
    SUPPORTED_INPUT_FORMATS,
    ExitCodes,
)
from .config.settings import ProcessingOptions
from .core.archiver import ColdStorageArchiver
from .core.extractor import MultiFormatExtractor
from .core.lister import ArchiveLister, ListingError, UnsupportedFormatError
from .core.repairer import ArchiveRepairer
from .core.verifier import ArchiveVerifier
from .utils.console import create_windows_compatible_console, safe_print
from .utils.filesystem import format_file_size, get_file_size
from .utils.par2 import PAR2Manager, check_par2_availability, install_par2_instructions
from .utils.progress import ProgressTracker
from .utils.windows_compat import check_par2_related_paths_compatibility

# Initialize Typer app
app = typer.Typer(
    name="cpack",
    help="coldpack - Cross-platform cold storage CLI package for standardized 7z archives with PAR2 recovery",
    add_completion=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Initialize Rich console with Windows compatibility
console = create_windows_compatible_console()


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        console.print(f"coldpack version {__version__}")
        raise typer.Exit()


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Setup logging configuration."""
    logger.remove()  # Remove default handler

    if quiet:
        level = "WARNING"
        format_str = "<level>{message}</level>"
    elif verbose:
        level = "DEBUG"
        format_str = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    else:
        level = "INFO"
        format_str = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"

    logger.add(sys.stderr, level=level, format=format_str, colorize=True)


def get_global_options(ctx: typer.Context) -> tuple[bool, bool]:
    """Get global verbose and quiet options from context."""
    if ctx.obj is None:
        return False, False
    return ctx.obj.get("verbose", False), ctx.obj.get("quiet", False)


def _load_coldpack_metadata(
    archive: Path, verbose: bool = False
) -> tuple[Optional[Any], Optional[str]]:
    """Load metadata.toml for coldpack standard archives.

    For coldpack standard compliance, metadata.toml must be in the standard location:
    archive_directory/metadata/metadata.toml

    Args:
        archive: Path to the archive file
        verbose: Enable verbose logging

    Returns:
        Tuple of (ArchiveMetadata object if found, error message if corrupted)
        - (metadata, None): Successfully loaded metadata
        - (None, None): No metadata file found (not a coldpack archive)
        - (None, error_msg): Metadata file exists but is corrupted
    """
    from .config.settings import ArchiveMetadata

    # Standard coldpack structure: archive_dir/metadata/metadata.toml
    metadata_path = archive.parent / "metadata" / "metadata.toml"

    if metadata_path.exists():
        try:
            metadata = ArchiveMetadata.load_from_toml(metadata_path)
            if verbose:
                logger.debug(f"Loading metadata from: {metadata_path}")
            return metadata, None
        except Exception as e:
            # If metadata.toml exists but is corrupted, return error but don't raise
            error_msg = f"Corrupted metadata.toml at {metadata_path}: {e}"
            logger.warning(error_msg)
            return None, error_msg

    if verbose:
        logger.debug(
            f"No coldpack metadata found for {archive} (not a coldpack archive)"
        )
    return None, None


@app.callback()
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output (increase log level)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Quiet output (decrease log level)",
    ),
) -> None:
    """coldpack - Cross-platform cold storage CLI package for 7z archives."""
    # Validate that verbose and quiet are not used together
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    # Store global options in context
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@app.command()
def create(
    ctx: typer.Context,
    source: Path,
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory",
        show_default="current directory",
        rich_help_panel="Output Options",
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Archive name",
        show_default="source name",
        rich_help_panel="Output Options",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force overwrite existing files",
        rich_help_panel="Output Options",
    ),
    threads: int = typer.Option(
        0,
        "--threads",
        "-t",
        help="Number of threads (0=all cores)",
        show_default="auto-detect",
        rich_help_panel="Compression Options",
    ),
    # 7Z compression options
    level: Optional[int] = typer.Option(
        None,
        "--level",
        "-l",
        help="Compression level (0-9)",
        show_default="dynamic",
        rich_help_panel="Compression Options",
    ),
    dict_size: Optional[str] = typer.Option(
        None,
        "--dict",
        "-d",
        help="Dictionary size (128k, 1m, 4m, 16m, 64m, 256m, 512m)",
        show_default="dynamic",
        rich_help_panel="Compression Options",
    ),
    no_par2: bool = typer.Option(
        False,
        "--no-par2",
        help="Skip PAR2 recovery file generation",
        rich_help_panel="PAR2 Options",
    ),
    no_verify: bool = typer.Option(
        False,
        "--no-verify",
        help="Skip all integrity verification (overrides individual controls)",
        rich_help_panel="Verification Options",
    ),
    # Individual verification layer controls for archive creation
    no_verify_7z: bool = typer.Option(
        False,
        "--no-verify-7z",
        help="Skip 7z integrity verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    no_verify_sha256: bool = typer.Option(
        False,
        "--no-verify-sha256",
        help="Skip SHA-256 hash verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    no_verify_blake3: bool = typer.Option(
        False,
        "--no-verify-blake3",
        help="Skip BLAKE3 hash verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    no_verify_par2: bool = typer.Option(
        False,
        "--no-verify-par2",
        help="Skip PAR2 recovery verification during archive creation",
        rich_help_panel="Verification Options",
    ),
    par2_redundancy: int = typer.Option(
        10,
        "--par2-redundancy",
        "-r",
        help="PAR2 redundancy percentage",
        show_default=True,
        rich_help_panel="PAR2 Options",
    ),
    # Global Options
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Create a cold storage 7z archive with comprehensive verification.

    Args:
        ctx: Typer context
        source: Source file, directory, or archive to process
        output_dir: Output directory (default: current directory)
        name: Archive name (default: source name)
        force: Force overwrite existing files
        threads: Number of threads (0=auto)
        level: 7z compression level (0-9, dynamic optimization if not specified)
        dict_size: 7z dictionary size (128k-512m, dynamic optimization if not specified)
        no_par2: Skip PAR2 recovery file generation
        no_verify: Skip all integrity verification (overrides individual controls)
        no_verify_7z: Skip 7z integrity verification during archive creation
        no_verify_sha256: Skip SHA-256 hash verification during archive creation
        no_verify_blake3: Skip BLAKE3 hash verification during archive creation
        no_verify_par2: Skip PAR2 recovery verification during archive creation
        par2_redundancy: PAR2 redundancy percentage
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate 7z compression parameters
    if level is not None and (level < 0 or level > 9):
        console.print("[red]Error: --level must be between 0 and 9[/red]")
        raise typer.Exit(ExitCodes.INVALID_FORMAT)

    if dict_size is not None:
        valid_dict_sizes = {"128k", "1m", "4m", "16m", "64m", "256m", "512m"}
        if dict_size.lower() not in valid_dict_sizes:
            console.print(
                f"[red]Error: --dict must be one of: {', '.join(sorted(valid_dict_sizes))}[/red]"
            )
            raise typer.Exit(ExitCodes.INVALID_FORMAT)

    # Validate verification parameters
    if no_verify and any(
        [
            no_verify_7z,
            no_verify_sha256,
            no_verify_blake3,
            no_verify_par2,
        ]
    ):
        console.print(
            "[red]Error: --no-verify cannot be used with individual --no-verify-* options[/red]"
        )
        console.print(
            "[yellow]Use either --no-verify to skip all verification, or specific --no-verify-* options[/yellow]"
        )
        raise typer.Exit(1)

    # Validate source
    if not source.exists():
        console.print(f"[red]Error: Source not found: {source}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Set default output directory
    if output_dir is None:
        output_dir = Path.cwd()

    # Check Windows PAR2 Unicode compatibility for PAR2-related operations
    if not no_par2:
        check_par2_related_paths_compatibility(source, output_dir, console)

    try:
        # Check PAR2 availability if needed
        if not no_par2 and not check_par2_availability():
            console.print(
                "[yellow]Warning: PAR2 tools not found, recovery files will not be generated[/yellow]"
            )
            console.print(install_par2_instructions())
            no_par2 = True

        # Configure processing options for 7z format
        # Handle verification settings: no_verify overrides individual controls
        if no_verify:
            # Skip all verification
            final_verify_integrity = False
            final_verify_sha256 = False
            final_verify_blake3 = False
            final_verify_par2 = False
        else:
            # Use individual controls
            final_verify_integrity = True
            final_verify_sha256 = not no_verify_sha256
            final_verify_blake3 = not no_verify_blake3
            final_verify_par2 = not no_verify_par2

        processing_options = ProcessingOptions(
            verify_integrity=final_verify_integrity,
            verify_sha256=final_verify_sha256,
            verify_blake3=final_verify_blake3,
            verify_par2=final_verify_par2,
            generate_par2=not no_par2,
            par2_redundancy=par2_redundancy,
            verbose=final_verbose,
            force_overwrite=force,
        )

        # Configure PAR2 settings
        from .config.settings import PAR2Settings

        par2_settings = PAR2Settings(redundancy_percent=par2_redundancy)

        # Configure 7z settings
        from .config.settings import SevenZipSettings

        # Convert CLI threads parameter (0 = all cores for backward compatibility)
        settings_threads = True if threads == 0 else threads

        # Check if manual 7z parameters are provided
        if level is not None or dict_size is not None:
            # Manual configuration - disable dynamic optimization
            manual_level = level if level is not None else 5  # 7z default
            manual_dict = (
                dict_size.lower() if dict_size is not None else "16m"
            )  # 7z default

            sevenzip_settings = SevenZipSettings(
                level=manual_level,
                dictionary_size=manual_dict,
                threads=settings_threads,
                manual_settings=True,  # Mark as manual to disable dynamic optimization
            )
            console.print(
                f"[cyan]Using manual 7z settings: level={manual_level}, dict={manual_dict}[/cyan]"
            )
            console.print(
                "[cyan]Dynamic optimization disabled due to manual parameters[/cyan]"
            )
        else:
            # Automatic configuration - will use dynamic optimization
            # Create default settings that will be overridden by dynamic optimization
            sevenzip_settings = SevenZipSettings(
                level=5,  # Will be overridden
                dictionary_size="16m",  # Will be overridden
                threads=settings_threads,
            )
            console.print(
                "[cyan]Using dynamic 7z optimization based on source size[/cyan]"
            )

        archiver = ColdStorageArchiver(
            processing_options=processing_options,
            par2_settings=par2_settings,
            sevenzip_settings=sevenzip_settings,
        )

        # Create progress tracker
        with ProgressTracker(console):
            console.print(
                f"[cyan]Creating cold storage 7z archive from: {source}[/cyan]"
            )
            console.print(f"[cyan]Output directory: {output_dir}[/cyan]")

            # Create 7z archive (default and only format)
            result = archiver.create_archive(source, output_dir, name, "7z")

            if result.success:
                safe_print(console, "[green]✓ Archive created successfully![/green]")

                # Display summary
                display_archive_summary(result)

            else:
                safe_print(
                    console, f"[red]✗ Archive creation failed: {result.message}[/red]"
                )
                if verbose and result.error_details:
                    console.print(f"[red]Details: {result.error_details}[/red]")
                raise typer.Exit(ExitCodes.COMPRESSION_FAILED)

    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from None
    except Exception as e:
        logger.error(f"Archive creation failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


@app.command()
def extract(
    ctx: typer.Context,
    archive: Path,
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Output directory",
        show_default="current directory",
        rich_help_panel="Output Options",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force overwrite existing files",
        rich_help_panel="Output Options",
    ),
    verify: bool = typer.Option(
        False,
        "--verify",
        help="Verify archive integrity before extraction",
        rich_help_panel="Verification Options",
    ),
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Extract a cold storage archive or supported archive format.

    For coldpack archives with metadata/metadata.toml:
    - Automatically uses original compression parameters from metadata
    - Falls back to direct extraction if metadata is unavailable
    - Errors if metadata is corrupted or extraction fails without metadata

    Args:
        ctx: Typer context
        archive: Archive file to extract
        output_dir: Output directory (default: current directory)
        force: Force overwrite existing files
        verify: Verify archive integrity before extraction
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate archive
    if not archive.exists():
        console.print(f"[red]Error: Archive not found: {archive}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Set default output directory
    if output_dir is None:
        output_dir = Path.cwd()

    # Check Windows PAR2 Unicode compatibility (extract may use PAR2 for verification)
    check_par2_related_paths_compatibility(archive, output_dir, console)

    try:
        console.print(f"[cyan]Extracting archive: {archive}[/cyan]")
        console.print(f"[cyan]Output directory: {output_dir}[/cyan]")

        # Step 1: Optional pre-extraction verification
        extractor = MultiFormatExtractor()
        if verify:
            console.print("[cyan]Performing pre-extraction verification...[/cyan]")

            # Import verifier for comprehensive verification
            from .core.verifier import ArchiveVerifier

            verifier = ArchiveVerifier()
            try:
                # Use auto verification for comprehensive checking
                results = verifier.verify_auto(archive)

                # Display detailed results
                passed_layers = sum(1 for r in results if r.success)
                total_layers = len(results)

                console.print(
                    f"[cyan]Verification complete: {passed_layers}/{total_layers} layers passed[/cyan]"
                )

                # Show each layer result
                for result in results:
                    status_icon = "[OK]" if result.success else "[FAIL]"
                    status_color = "green" if result.success else "red"
                    console.print(
                        f"[{status_color}]{status_icon} {result.layer}: {result.message}[/{status_color}]"
                    )

                # Overall result
                if passed_layers == total_layers:
                    safe_print(
                        console, "[green]✓ Archive integrity fully verified[/green]"
                    )
                else:
                    console.print(
                        f"[yellow][WARN] Partial verification: {passed_layers}/{total_layers} layers passed[/yellow]"
                    )
                    console.print(
                        "[yellow]Continuing with extraction attempt...[/yellow]"
                    )

            except Exception as e:
                safe_print(console, f"[red]✗ Verification failed: {e}[/red]")
                console.print("[yellow]Continuing with extraction attempt...[/yellow]")

        # Step 2: Try to load coldpack metadata (standard compliant archives)
        metadata, metadata_error = _load_coldpack_metadata(archive, final_verbose)

        if metadata:
            # Step 2a: Standard coldpack archive - use original parameters
            console.print(
                "[cyan]Coldpack archive detected - using original compression parameters[/cyan]"
            )
            # Display 7z compression parameters
            if metadata.sevenzip_settings:
                console.print(
                    f"[cyan]  Compression level: {metadata.sevenzip_settings.level}[/cyan]"
                )
                if metadata.sevenzip_settings.threads is True:
                    threads_display = "all"
                elif metadata.sevenzip_settings.threads is False:
                    threads_display = "1"
                else:
                    threads_display = str(metadata.sevenzip_settings.threads)
                console.print(f"[cyan]  Threads: {threads_display}[/cyan]")
                console.print(
                    f"[cyan]  Method: {metadata.sevenzip_settings.method}[/cyan]"
                )

            # Extract with metadata
            extracted_path = extractor.extract(
                archive, output_dir, force_overwrite=force, metadata=metadata
            )
        else:
            # Step 2b: Non-coldpack archive, missing metadata, or corrupted metadata - attempt direct extraction
            if metadata_error:
                # Warn about corrupted metadata but continue with direct extraction
                console.print(f"[yellow]Warning: {metadata_error}[/yellow]")
                console.print(
                    "[yellow]Attempting direct extraction without metadata...[/yellow]"
                )
            elif final_verbose:
                console.print(
                    "[yellow]No coldpack metadata found - attempting direct extraction[/yellow]"
                )

            try:
                extracted_path = extractor.extract(
                    archive, output_dir, force_overwrite=force, metadata=None
                )
            except Exception as direct_extract_error:
                # Step 3: Direct extraction failed
                logger.error(f"Direct extraction failed: {direct_extract_error}")

                if metadata_error:
                    # Both metadata is corrupted AND direct extraction failed
                    console.print(
                        "[red]Error: Archive extraction failed. The metadata is corrupted and direct extraction also failed.[/red]"
                    )
                    console.print(f"[red]Metadata error: {metadata_error}[/red]")
                    console.print(
                        f"[red]Extraction error: {direct_extract_error}[/red]"
                    )
                else:
                    # No metadata but direct extraction failed
                    console.print(
                        "[red]Error: Archive extraction failed. This may not be a valid coldpack archive or the format is unsupported.[/red]"
                    )
                    console.print(f"[red]Details: {direct_extract_error}[/red]")

                raise typer.Exit(ExitCodes.EXTRACTION_FAILED) from direct_extract_error

        safe_print(console, "[green]✓ Extraction completed successfully![/green]")
        console.print(f"[green]Extracted to: {extracted_path}[/green]")

    except typer.Exit:
        # Re-raise typer.Exit to preserve exit codes
        raise
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.EXTRACTION_FAILED) from e


@app.command()
def verify(
    ctx: typer.Context,
    archive: Path,
    hash_files: Optional[list[Path]] = typer.Option(
        None,
        "--hash-files",
        help="Hash files for verification",
        rich_help_panel="Input Options",
    ),
    par2_file: Optional[Path] = typer.Option(
        None,
        "--par2-file",
        "-p",
        help="PAR2 recovery file",
        rich_help_panel="Input Options",
    ),
    # Individual verification layer controls
    no_sha256: bool = typer.Option(
        False,
        "--no-sha256",
        help="Skip SHA-256 hash verification",
        rich_help_panel="Verification Controls",
    ),
    no_blake3: bool = typer.Option(
        False,
        "--no-blake3",
        help="Skip BLAKE3 hash verification",
        rich_help_panel="Verification Controls",
    ),
    no_par2: bool = typer.Option(
        False,
        "--no-par2",
        help="Skip PAR2 recovery verification",
        rich_help_panel="Verification Controls",
    ),
    # Local verbose/quiet override
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Verify archive integrity using multiple verification layers.

    Args:
        ctx: Typer context
        archive: Archive file to verify
        hash_files: Hash files for verification
        par2_file: PAR2 recovery file
        no_sha256: Skip SHA-256 hash verification
        no_blake3: Skip BLAKE3 hash verification
        no_par2: Skip PAR2 recovery verification
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate archive
    if not archive.exists():
        console.print(f"[red]Error: Archive not found: {archive}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Check Windows PAR2 Unicode compatibility (verify uses PAR2 verification)
    from .utils.windows_compat import check_windows_par2_unicode_compatibility

    check_windows_par2_unicode_compatibility(archive, console)

    try:
        verifier = ArchiveVerifier()

        console.print(f"[cyan]Verifying archive: {archive}[/cyan]")

        # Configure which verification layers to skip
        skip_layers = set()
        if no_sha256:
            skip_layers.add("sha256_hash")
        if no_blake3:
            skip_layers.add("blake3_hash")
        if no_par2:
            skip_layers.add("par2_recovery")

        # Handle explicitly provided files
        if hash_files or par2_file:
            # Build hash file dictionary from explicit files
            hash_file_dict: dict[str, Path] = {}
            if hash_files:
                for hash_file in hash_files:
                    if (
                        hash_file.suffix == ".sha256"
                        and "sha256_hash" not in skip_layers
                    ):
                        hash_file_dict["sha256"] = hash_file
                    elif (
                        hash_file.suffix == ".blake3"
                        and "blake3_hash" not in skip_layers
                    ):
                        hash_file_dict["blake3"] = hash_file

            # Use manual verification with explicitly provided files
            results = verifier.verify_complete(archive, hash_file_dict, par2_file)
        else:
            # Use auto-discovery verification (recommended approach)
            results = verifier.verify_auto(archive, skip_layers)

        # Display results
        display_verification_results(results)

        # Check overall success
        failed_results = [r for r in results if not r.success]
        if failed_results:
            raise typer.Exit(ExitCodes.VERIFICATION_FAILED)

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.VERIFICATION_FAILED) from e


@app.command()
def repair(
    ctx: typer.Context,
    file_path: Path,
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Repair a corrupted archive using PAR2 recovery files.

    Can accept either:
    - PAR2 recovery file directly (.par2)
    - Archive file (will auto-locate corresponding PAR2 files)

    Args:
        ctx: Typer context
        file_path: PAR2 recovery file or archive file
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate file path
    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Check Windows PAR2 Unicode compatibility (repair uses PAR2 tools)
    from .utils.windows_compat import check_windows_par2_unicode_compatibility

    check_windows_par2_unicode_compatibility(file_path, console)

    # Determine if it's a PAR2 file or archive file
    par2_file = None
    if file_path.suffix.lower() == ".par2":
        # Direct PAR2 file
        par2_file = file_path
    else:
        # Archive file - try to find corresponding PAR2 file
        console.print(f"[cyan]Archive file detected: {file_path}[/cyan]")
        console.print("[cyan]Searching for PAR2 recovery files...[/cyan]")

        # Look for PAR2 files in multiple locations
        potential_par2_paths = [
            # Same directory as archive
            file_path.parent / f"{file_path.name}.par2",
            # In metadata subdirectory (coldpack standard)
            file_path.parent / "metadata" / f"{file_path.name}.par2",
        ]

        for par2_path in potential_par2_paths:
            if par2_path.exists():
                par2_file = par2_path
                console.print(f"[green]Found PAR2 file: {par2_file}[/green]")
                break

        if par2_file is None:
            console.print(
                f"[red]Error: No PAR2 recovery files found for {file_path}[/red]"
            )
            console.print("[yellow]Searched locations:[/yellow]")
            for path in potential_par2_paths:
                console.print(f"  - {path}")
            console.print(
                "[yellow]For coldpack archives, PAR2 files should be in the metadata/ directory[/yellow]"
            )
            raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    try:
        # Try to load metadata for PAR2 parameter recovery
        metadata = None
        redundancy_percent = 10  # default

        try:
            from .config.settings import ArchiveMetadata

            # Look for metadata.toml in the same directory as PAR2 file
            metadata_paths = [
                par2_file.parent / "metadata.toml",
                par2_file.parent.parent / "metadata" / "metadata.toml",
            ]

            for metadata_path in metadata_paths:
                if metadata_path.exists():
                    try:
                        metadata = ArchiveMetadata.load_from_toml(metadata_path)
                        redundancy_percent = metadata.par2_settings.redundancy_percent
                        logger.debug(
                            f"Using PAR2 parameters from metadata: {redundancy_percent}% redundancy"
                        )
                        break
                    except Exception as e:
                        logger.debug(
                            f"Could not load metadata from {metadata_path}: {e}"
                        )
        except Exception as e:
            logger.debug(f"Metadata loading failed: {e}")

        repairer = ArchiveRepairer(redundancy_percent=redundancy_percent)

        console.print(f"[cyan]Attempting repair using: {par2_file}[/cyan]")
        if metadata:
            console.print(
                f"[cyan]Using original PAR2 settings: {redundancy_percent}% redundancy[/cyan]"
            )

        # Check repair capability
        capability = repairer.check_repair_capability(par2_file)

        if not capability["can_repair"]:
            console.print(
                "[red]✗ Archive cannot be repaired with available recovery data[/red]"
            )
            raise typer.Exit(ExitCodes.GENERAL_ERROR)

        # Perform repair
        result = repairer.repair_archive(par2_file)

        if result.success:
            safe_print(console, f"[green]✓ {result.message}[/green]")
            if result.repaired_files:
                console.print(
                    f"[green]Repaired files: {', '.join(result.repaired_files)}[/green]"
                )
        else:
            safe_print(console, f"[red]✗ {result.message}[/red]")
            if verbose and result.error_details:
                console.print(f"[red]Details: {result.error_details}[/red]")
            raise typer.Exit(ExitCodes.GENERAL_ERROR)

    except Exception as e:
        logger.error(f"Repair failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


@app.command()
def info(
    ctx: typer.Context,
    path: Path,
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """Display information about an archive or PAR2 recovery files.

    Args:
        ctx: Typer context
        path: Archive file or PAR2 file to analyze
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate path
    if not path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Check Windows PAR2 Unicode compatibility (info may display PAR2 information)
    from .utils.windows_compat import check_windows_par2_unicode_compatibility

    check_windows_par2_unicode_compatibility(path, console)

    try:
        if path.suffix == ".par2":
            # PAR2 file info
            display_par2_info(path)
        else:
            # Archive file info
            display_archive_info(path)

    except Exception as e:
        logger.error(f"Info retrieval failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


def display_archive_summary(result: Any) -> None:
    """Display archive creation summary."""
    if not result.metadata:
        return

    table = Table(
        title="Archive Summary", show_header=True, header_style="bold magenta"
    )
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    metadata = result.metadata

    table.add_row("Archive", str(metadata.archive_path.name))
    table.add_row("Original Size", format_file_size(metadata.original_size))
    table.add_row("Compressed Size", format_file_size(metadata.compressed_size))
    table.add_row("Compression Ratio", f"{metadata.compression_percentage:.1f}%")
    table.add_row("Files", str(metadata.file_count))
    # Display 7z compression level
    if metadata.sevenzip_settings:
        table.add_row("Compression Level", str(metadata.sevenzip_settings.level))

    if metadata.verification_hashes:
        for algorithm, hash_value in metadata.verification_hashes.items():
            table.add_row(f"{algorithm.upper()} Hash", hash_value[:16] + "...")

    if metadata.par2_files:
        table.add_row("PAR2 Files", str(len(metadata.par2_files)))

    console.print(table)


def display_verification_results(results: Any) -> None:
    """Display verification results table with detailed failure information."""
    table = Table(
        title="Verification Results", show_header=True, header_style="bold magenta"
    )
    table.add_column("Layer", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    failed_results = []
    for result in results:
        if result.success:
            status = "[green][OK] PASS[/green]"
        else:
            status = "[red][FAIL] FAIL[/red]"
            failed_results.append(result)

        table.add_row(result.layer.replace("_", " ").title(), status, result.message)

    console.print(table)

    # Summary
    passed = sum(1 for r in results if r.success)
    total = len(results)

    if passed == total:
        console.print(f"[green]All {total} verification layers passed![/green]")
    else:
        console.print(
            f"[red]{total - passed} of {total} verification layers failed![/red]"
        )

        # Display detailed failure information
        if failed_results:
            console.print()
            console.print("[red]Failed Verification Details:[/red]")
            for result in failed_results:
                layer_name = result.layer.replace("_", " ").title()
                safe_print(console, f"[red]• {layer_name}:[/red] {result.message}")

                # Show additional details if available
                if hasattr(result, "details") and result.details:
                    for key, value in result.details.items():
                        if isinstance(value, list) and value:
                            console.print(
                                f"  - {key.title()}: {', '.join(map(str, value))}"
                            )
                        elif value:
                            console.print(f"  - {key.title()}: {value}")


def display_archive_info(archive_path: Path) -> None:
    """Display archive information, prioritizing metadata.toml if available."""
    from .config.settings import ArchiveMetadata

    try:
        # First, try to find and load metadata.toml
        metadata = None

        # Determine archive name for path construction
        archive_name = archive_path.stem
        if archive_name.endswith(".tar"):
            archive_name = archive_name[:-4]

        metadata_paths = [
            # Standard coldpack structure: archive_dir/metadata/metadata.toml
            archive_path.parent / "metadata" / "metadata.toml",
            # Alternative: archive_name_dir/metadata/metadata.toml
            archive_path.parent / archive_name / "metadata" / "metadata.toml",
            # Legacy location: same directory as archive
            archive_path.parent / "metadata.toml",
        ]

        for metadata_path in metadata_paths:
            if metadata_path.exists():
                try:
                    metadata = ArchiveMetadata.load_from_toml(metadata_path)
                    break
                except Exception as e:
                    logger.debug(f"Could not load metadata from {metadata_path}: {e}")

        if metadata:
            # Display comprehensive metadata information
            display_metadata_info(archive_path, metadata)
        else:
            # Fallback to basic archive analysis
            display_basic_archive_info(archive_path)

    except Exception as e:
        console.print(f"[red]Could not read archive info: {e}[/red]")


def display_metadata_info(archive_path: Path, metadata: Any) -> None:
    """Display comprehensive archive information from metadata."""
    # Archive Basic Information
    basic_table = Table(
        title=f"Archive: {archive_path.name}",
        show_header=False,
        header_style="bold cyan",
        title_style="bold white",
        border_style="dim",
    )
    basic_table.add_column("Property", style="dim", no_wrap=True, width=20)
    basic_table.add_column("Value", style="white")

    basic_table.add_row("Path", str(archive_path))
    # Display format based on archive format
    if hasattr(metadata, "archive_format") and metadata.archive_format == "7z":
        format_display = "7z Archive"
    else:
        format_display = "TAR + Zstandard"
    basic_table.add_row("Format", format_display)

    # Calculate size display with compression info
    original_size_str = format_file_size(metadata.original_size)
    compressed_size_str = format_file_size(metadata.compressed_size)
    compression_pct = metadata.compression_percentage

    size_info = f"{compressed_size_str} ({original_size_str} -> {compressed_size_str}, {compression_pct:.1f}% compression)"
    basic_table.add_row("Size", size_info)

    console.print(basic_table)

    # Content Summary
    content_table = Table(
        title="Content Summary",
        show_header=False,
        title_style="bold cyan",
        border_style="dim",
    )
    content_table.add_column("Item", style="dim", no_wrap=True, width=20)
    content_table.add_column("Value", style="green")

    content_table.add_row("├── Files", str(metadata.file_count))
    content_table.add_row("├── Directories", str(metadata.directory_count))
    content_table.add_row("├── Total Size", original_size_str)
    content_table.add_row("└── Compression", f"{compression_pct:.1f}%")

    console.print(content_table)

    # Creation Settings
    creation_table = Table(
        title="Creation Settings",
        show_header=False,
        title_style="bold cyan",
        border_style="dim",
    )
    creation_table.add_column("Setting", style="dim", no_wrap=True, width=20)
    creation_table.add_column("Value", style="yellow")

    # Display 7z compression settings
    if metadata.sevenzip_settings:
        # 7Z format settings
        creation_table.add_row("├── 7z Level", str(metadata.sevenzip_settings.level))
        creation_table.add_row("├── Method", metadata.sevenzip_settings.method)
        creation_table.add_row(
            "├── Dictionary", metadata.sevenzip_settings.dictionary_size
        )
        creation_table.add_row("├── Threads", str(metadata.sevenzip_settings.threads))
        creation_table.add_row(
            "└── Solid", "true" if metadata.sevenzip_settings.solid else "false"
        )

    # No additional settings to display for 7z format

    console.print(creation_table)

    # Integrity information
    if metadata.verification_hashes:
        integrity_table = Table(
            title="Integrity",
            show_header=False,
            title_style="bold cyan",
            border_style="dim",
        )
        integrity_table.add_column("Algorithm", style="dim", no_wrap=True, width=20)
        integrity_table.add_column("Hash", style="bright_blue")

        # Display hashes with checkmark if available
        hash_algorithms = ["sha256", "blake3"]
        for i, algorithm in enumerate(hash_algorithms):
            if algorithm in metadata.verification_hashes:
                hash_value = metadata.verification_hashes[algorithm]
                # Truncate hash for display
                display_hash = f"{hash_value[:16]}... [OK]"
                prefix = "├──" if i < len(hash_algorithms) - 1 else "├──"
                integrity_table.add_row(f"{prefix} {algorithm.upper()}", display_hash)

        # Add PAR2 info if available
        if metadata.par2_settings:
            par2_info = f"{metadata.par2_settings.redundancy_percent}% redundancy"
            if metadata.par2_files:
                par2_info += f", {len(metadata.par2_files)} recovery file{'s' if len(metadata.par2_files) > 1 else ''} [OK]"
            else:
                par2_info += " (no files generated)"
            integrity_table.add_row("└── PAR2", par2_info)

        console.print(integrity_table)

    # Metadata information
    metadata_table = Table(
        title="Metadata",
        show_header=False,
        title_style="bold cyan",
        border_style="dim",
    )
    metadata_table.add_column("Property", style="dim", no_wrap=True, width=20)
    metadata_table.add_column("Value", style="magenta")

    metadata_table.add_row(
        "├── Created", metadata.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    metadata_table.add_row("├── coldpack", f"v{metadata.coldpack_version}")

    # Check for related files and show their status
    related_files = []
    archive_dir = archive_path.parent

    # Check for hash files
    sha256_file = archive_dir / f"{archive_path.name}.sha256"
    blake3_file = archive_dir / f"{archive_path.name}.blake3"

    # Check for PAR2 files (can be in same directory or metadata subdirectory)
    par2_file = archive_dir / f"{archive_path.name}.par2"
    metadata_par2_file = archive_dir / "metadata" / f"{archive_path.name}.par2"

    if sha256_file.exists():
        related_files.append(f"{archive_path.name}.sha256")
    if blake3_file.exists():
        related_files.append(f"{archive_path.name}.blake3")
    if par2_file.exists():
        related_files.append(f"{archive_path.name}.par2")
    elif metadata_par2_file.exists():
        related_files.append(f"metadata/{archive_path.name}.par2")

    if related_files:
        related_files_str = ", ".join(related_files)
        metadata_table.add_row("└── Related Files", related_files_str)
    else:
        metadata_table.add_row("└── Related Files", "[dim]None found[/dim]")

    console.print(metadata_table)


def display_basic_archive_info(archive_path: Path) -> None:
    """Display basic archive information when metadata is not available."""
    try:
        extractor = MultiFormatExtractor()
        info = extractor.get_archive_info(archive_path)

        # Archive basic information
        basic_table = Table(
            title=f"Archive: {archive_path.name}",
            show_header=False,
            title_style="bold white",
            border_style="dim",
        )
        basic_table.add_column("Property", style="dim", no_wrap=True, width=20)
        basic_table.add_column("Value", style="white")

        basic_table.add_row("Path", str(archive_path))

        # Determine format based on file extension
        if archive_path.suffix.lower() == ".zst" and archive_path.stem.endswith(".tar"):
            format_display = "TAR + Zstandard"
        else:
            format_display = info["format"].upper()

        basic_table.add_row("Format", format_display)
        basic_table.add_row("Size", format_file_size(info["size"]))

        console.print(basic_table)

        # Content summary (limited info available)
        content_table = Table(
            title="Content Summary",
            show_header=False,
            title_style="bold cyan",
            border_style="dim",
        )
        content_table.add_column("Item", style="dim", no_wrap=True, width=20)
        content_table.add_column("Value", style="green")

        content_table.add_row("├── Files", str(info["file_count"]))
        content_table.add_row(
            "├── Single Root", "Yes" if info["has_single_root"] else "No"
        )
        if info.get("root_name"):
            content_table.add_row("└── Root Directory", info["root_name"])
        else:
            content_table.add_row("└── Root Directory", "[dim]Multiple roots[/dim]")

        console.print(content_table)

        # Warning about limited information
        console.print(
            "\n[yellow][WARN] Limited information available - no metadata file found.[/yellow]"
        )
        console.print(
            "[dim]For complete archive information, ensure the metadata/ directory is present.[/dim]"
        )
        console.print("[dim]Use 'cpack list' to view archive contents.[/dim]")

    except Exception as e:
        console.print(f"[red]Could not read basic archive info: {e}[/red]")


def display_par2_info(par2_path: Path) -> None:
    """Display PAR2 recovery file information."""
    try:
        par2_manager = PAR2Manager()
        info = par2_manager.get_recovery_info(par2_path)

        # PAR2 Recovery Information
        par2_table = Table(
            title=f"PAR2 Recovery: {par2_path.name}",
            show_header=False,
            title_style="bold white",
            border_style="dim",
        )
        par2_table.add_column("Property", style="dim", no_wrap=True, width=20)
        par2_table.add_column("Value", style="green")

        par2_table.add_row("Path", str(par2_path))
        par2_table.add_row("Redundancy", f"{info['redundancy_percent']}%")
        par2_table.add_row("Recovery Files", str(info["file_count"]))
        par2_table.add_row("Total Size", format_file_size(info["total_size"]))

        console.print(par2_table)

        # Recovery files list with tree-like display
        if info["par2_files"]:
            files_table = Table(
                title="Recovery Files",
                show_header=False,
                title_style="bold cyan",
                border_style="dim",
            )
            files_table.add_column("File", style="dim", no_wrap=True, width=30)
            files_table.add_column("Size", style="yellow", justify="right")

            for i, par2_file in enumerate(info["par2_files"]):
                file_path = Path(par2_file)
                if file_path.exists():
                    size = format_file_size(get_file_size(file_path))
                    prefix = "├──" if i < len(info["par2_files"]) - 1 else "└──"
                    files_table.add_row(f"{prefix} {file_path.name}", size)
                else:
                    prefix = "├──" if i < len(info["par2_files"]) - 1 else "└──"
                    files_table.add_row(
                        f"{prefix} {file_path.name}", "[red]Missing[/red]"
                    )

            console.print(files_table)

    except Exception as e:
        console.print(f"[red]Could not read PAR2 info: {e}[/red]")


def display_archive_listing(result: dict, verbose: bool = False) -> None:
    """Display archive listing results in a formatted table.

    Args:
        result: Dictionary containing listing results from ArchiveLister
        verbose: Whether to show verbose output
    """

    archive_path = result["archive_path"]
    archive_format = result["format"]
    files = result["files"]

    # Display header information
    console.print(f"\n[bold]Archive:[/bold] {Path(archive_path).name}")
    console.print(f"[bold]Path:[/bold] {archive_path}")
    console.print(f"[bold]Format:[/bold] {archive_format}")

    # Display summary statistics
    summary_table = Table(title="Summary", show_header=False, box=None)
    summary_table.add_column("Property", style="dim", width=20)
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Total Files", f"{result['total_files']:,}")
    summary_table.add_row("Total Directories", f"{result['total_directories']:,}")
    summary_table.add_row("Total Entries", f"{result['total_entries']:,}")

    if result["total_size"] > 0:
        summary_table.add_row("Total Size", format_file_size(result["total_size"]))
        if result["total_compressed_size"] > 0:
            summary_table.add_row(
                "Compressed Size", format_file_size(result["total_compressed_size"])
            )
            summary_table.add_row("Compression", f"{result['compression_ratio']:.1f}%")

    if result["showing_range"]:
        summary_table.add_row("Showing", result["showing_range"])

    console.print(summary_table)

    # If summary-only mode, stop here
    if not files:
        if result.get("has_more", False):
            console.print(
                f"\n[dim]Use --limit and --offset to paginate through all {result['total_entries']} entries[/dim]"
            )
        return

    # Display file listing table
    file_table = Table(
        title="Contents", show_header=True, header_style="bold cyan", border_style="dim"
    )

    file_table.add_column("Type", width=4, justify="center")
    file_table.add_column("Name", style="white", no_wrap=False)
    file_table.add_column("Size", justify="right", width=12)
    file_table.add_column("Modified", width=19)

    # Files are already sorted by the lister for consistent pagination
    # Display files in a simple, clean format
    for file in files:
        # Type indicator - use text instead of icons
        type_indicator = "DIR" if file.is_directory else "FILE"

        # Clean file path display (just show the full path as-is)
        name_display = file.path.rstrip(
            "/"
        )  # Remove trailing slash for cleaner display

        # Size formatting
        size_display = (
            "-"
            if file.is_directory
            else (format_file_size(file.size) if file.size > 0 else "-")
        )

        # Modified time formatting
        if file.modified:
            modified_display = file.modified.strftime("%Y-%m-%d %H:%M:%S")
        else:
            modified_display = "-"

        file_table.add_row(type_indicator, name_display, size_display, modified_display)

    console.print(file_table)

    # Show pagination info and tips
    if result.get("has_more", False):
        console.print(
            "\n[yellow]More entries available. Use --limit and --offset to see more.[/yellow]"
        )
        console.print(
            f'[dim]Example: cpack list --limit 50 --offset {len(files)} "{archive_path}"[/dim]'
        )

    if result["total_entries"] > 100 and not result.get("showing_range", "").startswith(
        "All"
    ):
        console.print("\n[dim]Tips:[/dim]")
        safe_print(
            console, "[dim]  • Use --filter '*.ext' to filter by file type[/dim]"
        )
        safe_print(console, "[dim]  • Use --dirs-only to show only directories[/dim]")
        safe_print(console, "[dim]  • Use --summary-only for overview[/dim]")


def list_archive(
    ctx: typer.Context,
    path: Path,
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="Maximum number of entries to show", min=1
    ),
    offset: int = typer.Option(
        0, "--offset", "-o", help="Number of entries to skip", min=0
    ),
    filter_pattern: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Glob pattern to filter entries (e.g., '*.txt')"
    ),
    dirs_only: bool = typer.Option(
        False, "--dirs-only", "-d", help="Show only directories"
    ),
    files_only: bool = typer.Option(
        False, "--files-only", help="Show only files (exclude directories)"
    ),
    summary_only: bool = typer.Option(
        False, "--summary-only", "-s", help="Show only summary statistics"
    ),
    verbose: Optional[bool] = typer.Option(
        None, "--verbose", "-v", help="Verbose output"
    ),
    quiet: Optional[bool] = typer.Option(None, "--quiet", "-q", help="Quiet output"),
) -> None:
    """List contents of an archive without extracting it.

    Shows the file and directory structure within supported archive formats.
    Only works with formats that can be read directly (7z, zip, rar, tar, etc.).

    Examples:
        cpack list archive.7z
        cpack list --limit 50 archive.zip
        cpack list --filter "*.txt" --dirs-only archive.tar.gz
        cpack list --summary-only large-archive.7z

    Args:
        ctx: Typer context
        path: Archive file to list contents of
        limit: Maximum number of entries to show
        offset: Number of entries to skip (for pagination)
        filter_pattern: Glob pattern to filter entries
        dirs_only: Show only directories
        files_only: Show only files (exclude directories)
        summary_only: Show only summary statistics
        verbose: Local verbose override
        quiet: Local quiet override
    """
    # Handle verbose/quiet precedence: local overrides global
    global_verbose, global_quiet = get_global_options(ctx)

    # Local parameters override global if specified
    if verbose is not None and quiet is not None and verbose and quiet:
        console.print("[red]Error: --verbose and --quiet cannot be used together[/red]")
        raise typer.Exit(1)

    # Validate mutually exclusive options
    if dirs_only and files_only:
        console.print(
            "[red]Error: --dirs-only and --files-only cannot be used together[/red]"
        )
        raise typer.Exit(1)

    final_verbose = verbose if verbose is not None else global_verbose
    final_quiet = quiet if quiet is not None else global_quiet

    setup_logging(final_verbose, final_quiet)

    # Validate path
    if not path.exists():
        console.print(f"[red]Error: Archive not found: {path}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Check Windows PAR2 Unicode compatibility (list may access PAR2 metadata)
    from .utils.windows_compat import check_windows_par2_unicode_compatibility

    check_windows_par2_unicode_compatibility(path, console)

    try:
        lister = ArchiveLister()

        # Handle large archives with automatic warnings
        if limit is None and not summary_only:
            # Get quick info first to check archive size
            try:
                quick_info = lister.get_quick_info(path)
                total_entries = quick_info.get("total_entries", 0)

                # Warn for large archives
                if total_entries > 10000:
                    console.print(
                        f"[yellow]Warning: Archive contains {total_entries:,} entries.[/yellow]"
                    )
                    console.print(
                        "[yellow]Consider using --limit to avoid overwhelming output.[/yellow]"
                    )
                    console.print(
                        "[yellow]Use --summary-only for overview or Ctrl+C to cancel.[/yellow]"
                    )
                    console.print()
                elif total_entries > 1000:
                    console.print(
                        f"[yellow]Info: Archive contains {total_entries:,} entries.[/yellow]"
                    )
                    console.print()

            except Exception:
                # If quick info fails, proceed anyway
                pass

        # List archive contents
        result = lister.list_archive(
            archive_path=path,
            limit=limit,
            offset=offset,
            filter_pattern=filter_pattern,
            dirs_only=dirs_only,
            files_only=files_only,
            summary_only=summary_only,
        )

        # Display results
        display_archive_listing(result, final_verbose)

    except UnsupportedFormatError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("\n[dim]Tip: Use 'cpack formats' to see supported formats[/dim]")
        raise typer.Exit(ExitCodes.INVALID_FORMAT) from e
    except ListingError as e:
        logger.error(f"Archive listing failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e
    except Exception as e:
        logger.error(f"Unexpected listing error: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


# Register list command
app.command(name="list", help="List contents of an archive without extracting it.")(
    list_archive
)


@app.command()
def formats() -> None:
    """List supported archive formats."""
    console.print("[bold]Supported Input Formats:[/bold]")

    for fmt in sorted(SUPPORTED_INPUT_FORMATS):
        console.print(f"  {fmt}")

    console.print(
        f"\n[bold]Total:[/bold] {len(SUPPORTED_INPUT_FORMATS)} formats supported"
    )
    console.print(
        "[bold]Output Format:[/bold] .7z (7-Zip archive with LZMA2 compression)"
    )


def cli_main() -> None:
    """Main entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(ExitCodes.GENERAL_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(ExitCodes.GENERAL_ERROR)


if __name__ == "__main__":
    cli_main()
