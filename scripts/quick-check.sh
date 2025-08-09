#!/bin/bash

# Quick CI checks for local development
# This script performs lightweight checks that can be run frequently during development
# Includes: formatting, linting, REUSE compliance, and type checking

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if we're in the right directory
check_project_root() {
    if [[ ! -f "pyproject.toml" || ! -d "src/coldpack" ]]; then
        print_error "This script must be run from the project root directory"
        exit 1
    fi
}

# Function to ensure uv environment is set up
setup_environment() {
    print_status "Setting up development environment..."

    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install uv first."
        exit 1
    fi

    # Ensure dependencies are installed
    uv sync --dev
    uv pip install -e .

    print_success "Environment setup complete"
}

# Function to run code formatting checks
check_formatting() {
    print_status "Checking code formatting with ruff..."

    # Check formatting
    if uv run ruff format --check --diff .; then
        print_success "Code formatting is correct"
    else
        print_warning "Code formatting issues found. Run 'uv run ruff format .' to fix"
        return 1
    fi
}

# Function to run linting
check_linting() {
    print_status "Running linting checks with ruff..."

    if uv run ruff check .; then
        print_success "Linting checks passed"
    else
        print_warning "Linting issues found. Run 'uv run ruff check --fix .' to auto-fix"
        return 1
    fi
}

# Function to run REUSE compliance check
check_reuse_compliance() {
    print_status "Checking REUSE compliance..."

    if uv run reuse lint; then
        print_success "REUSE compliance check passed"
    else
        print_error "REUSE compliance check failed"
        print_warning "Files are missing proper licensing information"
        print_warning "Run 'uv run reuse lint' to see detailed issues"
        return 1
    fi
}

# Function to run type checking
check_types() {
    print_status "Running type checking with mypy..."

    # Uninstall editable package to avoid path conflicts
    uv pip uninstall coldpack > /dev/null 2>&1 || true

    if uv run mypy src/ tests/ --ignore-missing-imports; then
        print_success "Type checking passed"
        # Reinstall editable package
        uv pip install -e . > /dev/null 2>&1
    else
        print_error "Type checking failed"
        # Reinstall editable package even on failure
        uv pip install -e . > /dev/null 2>&1
        return 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "  Quick CI Checks for Local Development"
    echo "=========================================="
    echo

    check_project_root

    local exit_code=0

    # Run checks
    setup_environment || exit_code=1
    check_formatting || exit_code=1
    check_linting || exit_code=1
    check_reuse_compliance || exit_code=1
    check_types || exit_code=1

    echo
    echo "=========================================="
    if [[ $exit_code -eq 0 ]]; then
        print_success "All quick checks passed! ✅"
        echo "Your code is ready for more comprehensive testing."
    else
        print_error "Some checks failed! ❌"
        echo "Please fix the issues above before pushing to remote."
    fi
    echo "=========================================="

    exit $exit_code
}

# Run main function
main "$@"
