"""Typer-based CLI interface for coldpack cold storage archiver."""

import sys
from pathlib import Path
from typing import Any, Optional

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from . import __version__
from .config.constants import SUPPORTED_INPUT_FORMATS, ExitCodes
from .config.settings import CompressionSettings, ProcessingOptions
from .core.archiver import ColdStorageArchiver
from .core.extractor import MultiFormatExtractor
from .core.repairer import ArchiveRepairer
from .core.verifier import ArchiveVerifier
from .utils.filesystem import format_file_size, get_file_size
from .utils.par2 import PAR2Manager, check_par2_availability, install_par2_instructions
from .utils.progress import ProgressTracker

# Initialize Typer app
app = typer.Typer(
    name="cpack",
    help="coldpack - Cross-platform cold storage CLI package for standardized tar.zst archives",
    add_completion=False,
    rich_markup_mode="rich",
)

# Initialize Rich console
console = Console()


def version_callback(value: bool) -> None:
    """Show version information."""
    if value:
        console.print(f"coldpack version {__version__}")
        raise typer.Exit()


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    logger.remove()  # Remove default handler

    if verbose:
        level = "DEBUG"
        format_str = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    else:
        level = "INFO"
        format_str = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"

    logger.add(sys.stderr, level=level, format=format_str, colorize=True)


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """coldpack - Cross-platform cold storage CLI package."""
    pass


@app.command()
def archive(
    source: Path,
    output: Optional[Path] = None,
    name: Optional[str] = None,
    level: int = 19,
    threads: int = 0,
    no_long: bool = False,
    no_par2: bool = False,
    no_verify: bool = False,
    par2_redundancy: int = 10,
    verbose: bool = False,
) -> None:
    """Create a cold storage archive with comprehensive verification.

    Args:
        source: Source file, directory, or archive to process
        output: Output directory (default: current directory)
        name: Archive name (default: source name)
        level: Compression level (1-22)
        threads: Number of threads (0=auto)
        no_long: Disable long-distance matching
        no_par2: Skip PAR2 recovery file generation
        no_verify: Skip integrity verification
        par2_redundancy: PAR2 redundancy percentage
        verbose: Verbose output
    """
    setup_logging(verbose)

    # Validate source
    if not source.exists():
        console.print(f"[red]Error: Source not found: {source}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Set default output directory
    if output is None:
        output = Path.cwd()

    try:
        # Check PAR2 availability if needed
        if not no_par2 and not check_par2_availability():
            console.print(
                "[yellow]Warning: PAR2 tools not found, recovery files will not be generated[/yellow]"
            )
            console.print(install_par2_instructions())
            no_par2 = True

        # Configure compression settings
        compression_settings = CompressionSettings(
            level=level,
            threads=threads,
            long_mode=not no_long,
            ultra_mode=(level >= 20),
        )

        # Configure processing options
        processing_options = ProcessingOptions(
            verify_integrity=not no_verify,
            generate_par2=not no_par2,
            par2_redundancy=par2_redundancy,
            verbose=verbose,
        )

        # Create archiver
        archiver = ColdStorageArchiver(compression_settings, processing_options)

        # Create progress tracker
        with ProgressTracker(console):
            console.print(f"[cyan]Creating cold storage archive from: {source}[/cyan]")
            console.print(f"[cyan]Output directory: {output}[/cyan]")

            # Create archive
            result = archiver.create_archive(source, output, name)

            if result.success:
                console.print("[green]✓ Archive created successfully![/green]")

                # Display summary
                display_archive_summary(result)

            else:
                console.print(f"[red]✗ Archive creation failed: {result.message}[/red]")
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
    archive: Path,
    output: Optional[Path] = None,
    verbose: bool = False,
) -> None:
    """Extract a cold storage archive or supported archive format.

    Args:
        archive: Archive file to extract
        output: Output directory (default: current directory)
        verbose: Verbose output
    """
    setup_logging(verbose)

    # Validate archive
    if not archive.exists():
        console.print(f"[red]Error: Archive not found: {archive}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    # Set default output directory
    if output is None:
        output = Path.cwd()

    try:
        extractor = MultiFormatExtractor()

        console.print(f"[cyan]Extracting archive: {archive}[/cyan]")
        console.print(f"[cyan]Output directory: {output}[/cyan]")

        # Extract archive
        extracted_path = extractor.extract(archive, output)

        console.print("[green]✓ Extraction completed successfully![/green]")
        console.print(f"[green]Extracted to: {extracted_path}[/green]")

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.EXTRACTION_FAILED) from e


@app.command()
def verify(
    archive: Path,
    hash_files: Optional[list[Path]] = None,
    par2_file: Optional[Path] = None,
    quick: bool = False,
    verbose: bool = False,
) -> None:
    """Verify archive integrity using multiple verification layers.

    Args:
        archive: Archive file to verify
        hash_files: Hash files for verification
        par2_file: PAR2 recovery file
        quick: Quick verification (zstd integrity only)
        verbose: Verbose output
    """
    setup_logging(verbose)

    # Validate archive
    if not archive.exists():
        console.print(f"[red]Error: Archive not found: {archive}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    try:
        verifier = ArchiveVerifier()

        console.print(f"[cyan]Verifying archive: {archive}[/cyan]")

        if quick:
            # Quick verification
            success = verifier.verify_quick(archive)

            if success:
                console.print("[green]✓ Quick verification passed[/green]")
            else:
                console.print("[red]✗ Quick verification failed[/red]")
                raise typer.Exit(ExitCodes.VERIFICATION_FAILED)
        else:
            # Full verification
            hash_file_dict = {}
            if hash_files:
                for hash_file in hash_files:
                    if hash_file.suffix == ".sha256":
                        hash_file_dict["sha256"] = hash_file
                    elif hash_file.suffix == ".blake3":
                        hash_file_dict["blake3"] = hash_file

            # Auto-detect hash files if not provided
            if not hash_file_dict:
                sha256_file = archive.with_suffix(archive.suffix + ".sha256")
                blake3_file = archive.with_suffix(archive.suffix + ".blake3")

                if sha256_file.exists():
                    hash_file_dict["sha256"] = sha256_file
                if blake3_file.exists():
                    hash_file_dict["blake3"] = blake3_file

            # Auto-detect PAR2 file if not provided
            if not par2_file:
                par2_candidate = archive.with_suffix(archive.suffix + ".par2")
                if par2_candidate.exists():
                    par2_file = par2_candidate

            # Perform verification
            results = verifier.verify_complete(archive, hash_file_dict, par2_file)

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
    par2_file: Path,
    verbose: bool = False,
) -> None:
    """Repair a corrupted archive using PAR2 recovery files.

    Args:
        par2_file: PAR2 recovery file
        verbose: Verbose output
    """
    setup_logging(verbose)

    # Validate PAR2 file
    if not par2_file.exists():
        console.print(f"[red]Error: PAR2 file not found: {par2_file}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

    try:
        repairer = ArchiveRepairer()

        console.print(f"[cyan]Attempting repair using: {par2_file}[/cyan]")

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
            console.print(f"[green]✓ {result.message}[/green]")
            if result.repaired_files:
                console.print(
                    f"[green]Repaired files: {', '.join(result.repaired_files)}[/green]"
                )
        else:
            console.print(f"[red]✗ {result.message}[/red]")
            if verbose and result.error_details:
                console.print(f"[red]Details: {result.error_details}[/red]")
            raise typer.Exit(ExitCodes.GENERAL_ERROR)

    except Exception as e:
        logger.error(f"Repair failed: {e}")
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(ExitCodes.GENERAL_ERROR) from e


@app.command()
def info(
    path: Path,
    verbose: bool = False,
) -> None:
    """Display information about an archive or PAR2 recovery files.

    Args:
        path: Archive file or PAR2 file to analyze
        verbose: Verbose output
    """
    setup_logging(verbose)

    # Validate path
    if not path.exists():
        console.print(f"[red]Error: File not found: {path}[/red]")
        raise typer.Exit(ExitCodes.FILE_NOT_FOUND)

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
    table.add_row("Compression Level", str(metadata.compression_settings.level))

    if metadata.verification_hashes:
        for algorithm, hash_value in metadata.verification_hashes.items():
            table.add_row(f"{algorithm.upper()} Hash", hash_value[:16] + "...")

    if metadata.par2_files:
        table.add_row("PAR2 Files", str(len(metadata.par2_files)))

    console.print(table)


def display_verification_results(results: Any) -> None:
    """Display verification results table."""
    table = Table(
        title="Verification Results", show_header=True, header_style="bold magenta"
    )
    table.add_column("Layer", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Message", style="dim")

    for result in results:
        status = "[green]✓ PASS[/green]" if result.success else "[red]✗ FAIL[/red]"
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


def display_archive_info(archive_path: Path) -> None:
    """Display archive information."""
    try:
        extractor = MultiFormatExtractor()
        info = extractor.get_archive_info(archive_path)

        table = Table(
            title=f"Archive Information: {archive_path.name}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("File Path", str(archive_path))
        table.add_row("Format", info["format"])
        table.add_row("File Size", format_file_size(info["size"]))
        table.add_row("Files Count", str(info["file_count"]))
        table.add_row("Has Single Root", "Yes" if info["has_single_root"] else "No")

        if info.get("root_name"):
            table.add_row("Root Directory", info["root_name"])

        console.print(table)

        # Show some file names
        if info["files"]:
            console.print("\n[bold]Sample Files:[/bold]")
            for file_name in info["files"][:10]:
                console.print(f"  {file_name}")

            if len(info["files"]) > 10:
                console.print(f"  ... and {len(info['files']) - 10} more files")

    except Exception as e:
        console.print(f"[red]Could not read archive info: {e}[/red]")


def display_par2_info(par2_path: Path) -> None:
    """Display PAR2 recovery file information."""
    try:
        par2_manager = PAR2Manager()
        info = par2_manager.get_recovery_info(par2_path)

        table = Table(
            title=f"PAR2 Recovery Information: {par2_path.name}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Property", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Main PAR2 File", info["main_par2_file"])
        table.add_row("Recovery Files", str(info["file_count"]))
        table.add_row("Total Size", format_file_size(info["total_size"]))
        table.add_row("Redundancy", f"{info['redundancy_percent']}%")

        console.print(table)

        # Show recovery files
        if info["par2_files"]:
            console.print("\n[bold]Recovery Files:[/bold]")
            for par2_file in info["par2_files"]:
                file_path = Path(par2_file)
                if file_path.exists():
                    size = format_file_size(get_file_size(file_path))
                    console.print(f"  {file_path.name} ({size})")

    except Exception as e:
        console.print(f"[red]Could not read PAR2 info: {e}[/red]")


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
        "[bold]Output Format:[/bold] .tar.zst (TAR archive compressed with Zstandard)"
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
