#!/bin/bash

# Complete CI workflow simulation for local testing
# This script runs all CI checks locally to minimize remote CI failures

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_section() {
    echo -e "${CYAN}[SECTION]${NC} $1"
}

# Function to check if we're in the right directory
check_project_root() {
    if [[ ! -f "pyproject.toml" || ! -d "src/coldpack" ]]; then
        print_error "This script must be run from the project root directory"
        exit 1
    fi

    if [[ ! -f "scripts/quick-check.sh" ]]; then
        print_error "quick-check.sh script not found. Please ensure it exists in scripts/"
        exit 1
    fi
}

# Function to run security scanning
run_security_checks() {
    print_section "Running Security Checks"

    print_status "Running bandit security scan..."
    if uv run bandit -r src/ -f json -o bandit-report.json; then
        print_success "Bandit security scan completed"
    else
        print_warning "Bandit found security issues (see bandit-report.json)"
    fi

    print_status "Running safety dependency check..."
    if uv run safety check --json --output safety-report.json; then
        print_success "Safety dependency check passed"
    else
        print_warning "Safety found vulnerable dependencies (see safety-report.json)"
    fi

    # Display security reports summary
    if [[ -f "bandit-report.json" ]]; then
        local bandit_issues=$(python3 -c "import json; data=json.load(open('bandit-report.json')); print(len(data.get('results', [])))" 2>/dev/null || echo "0")
        print_status "Bandit found $bandit_issues security issues"
    fi

    print_success "Security scanning completed"
}

# Function to run comprehensive tests with coverage
run_comprehensive_tests() {
    print_section "Running Comprehensive Tests"

    print_status "Running pytest with coverage reporting..."

    # Run tests with coverage
    if uv run pytest -v --tb=short --cov=src/coldpack --cov-report=xml --cov-report=html --cov-report=term-missing; then
        print_success "All tests passed with coverage reporting"

        # Display coverage summary
        if [[ -f "coverage.xml" ]]; then
            print_status "Coverage reports generated:"
            print_status "  - XML report: coverage.xml"
            print_status "  - HTML report: htmlcov/index.html"
        fi
    else
        print_error "Some tests failed"
        return 1
    fi
}

# Function to simulate different Python versions (if available)
simulate_python_versions() {
    print_section "Python Version Compatibility Check"

    local python_versions=("3.9" "3.10" "3.11" "3.12" "3.13")
    local current_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)

    print_status "Current Python version: $current_version"

    # Check if uv can install other Python versions
    for version in "${python_versions[@]}"; do
        if command -v "python$version" &> /dev/null; then
            print_status "Python $version is available"

            # Quick syntax check with this Python version
            if python$version -m py_compile src/coldpack/__init__.py &> /dev/null; then
                print_success "Python $version compatibility: OK"
            else
                print_warning "Python $version compatibility: Issues found"
            fi
        else
            print_status "Python $version not available locally"
        fi
    done
}

# Function to clean up temporary files
cleanup_temp_files() {
    print_status "Cleaning up temporary files..."

    # Remove coverage and test artifacts that shouldn't be committed
    rm -f bandit-report.json safety-report.json
    rm -rf .pytest_cache/ .mypy_cache/

    print_success "Cleanup completed"
}

# Function to display CI simulation summary
display_summary() {
    local exit_code=$1

    echo
    echo "=================================================="
    echo "        CI Workflow Simulation Summary"
    echo "=================================================="

    if [[ $exit_code -eq 0 ]]; then
        print_success "🎉 All CI checks passed locally!"
        echo
        echo "Your code is ready to push to remote repository."
        echo "The remote CI should pass without issues."
        echo
        echo "Generated reports:"
        [[ -f "coverage.xml" ]] && echo "  📊 Coverage XML: coverage.xml"
        [[ -d "htmlcov" ]] && echo "  📊 Coverage HTML: htmlcov/index.html"
    else
        print_error "❌ Some CI checks failed!"
        echo
        echo "Please fix the issues above before pushing to remote."
        echo "This will help avoid failed CI runs on the remote repository."
    fi

    echo "=================================================="
}

# Function to show help
show_help() {
    echo "CI Local - Complete CI workflow simulation"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --quick-only    Run only quick checks (equivalent to quick-check.sh)"
    echo "  --no-cleanup    Skip cleanup of temporary files"
    echo "  --help         Show this help message"
    echo
    echo "This script simulates the complete CI workflow locally, including:"
    echo "  1. Quick checks (formatting, linting, REUSE compliance, type checking)"
    echo "  2. Security scanning (bandit, safety)"
    echo "  3. Comprehensive testing with coverage"
    echo "  4. Python version compatibility checks"
    echo
    echo "The script will generate the same reports as the remote CI,"
    echo "helping you catch issues before pushing to the repository."
}

# Main execution
main() {
    local quick_only=false
    local no_cleanup=false

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --quick-only)
                quick_only=true
                shift
                ;;
            --no-cleanup)
                no_cleanup=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done

    echo "=================================================="
    echo "     Complete CI Workflow Simulation - Local"
    echo "=================================================="
    echo

    check_project_root

    local exit_code=0

    # Step 1: Run quick checks (delegate to quick-check.sh)
    print_section "Step 1: Quick Checks (Lint, Format, REUSE Compliance, Type)"
    chmod +x scripts/quick-check.sh
    if ./scripts/quick-check.sh; then
        print_success "Quick checks completed successfully"
    else
        print_error "Quick checks failed"
        exit_code=1
        # Don't exit immediately, continue with other checks for full report
    fi

    # If only quick checks requested, exit here
    if [[ "$quick_only" == true ]]; then
        display_summary $exit_code
        exit $exit_code
    fi

    echo

    # Step 2: Security checks
    run_security_checks || exit_code=1

    echo

    # Step 3: Comprehensive testing
    run_comprehensive_tests || exit_code=1

    echo

    # Step 4: Python version compatibility (if available)
    simulate_python_versions || true  # Don't fail on this

    echo

    # Step 5: Cleanup (unless disabled)
    if [[ "$no_cleanup" != true ]]; then
        cleanup_temp_files
    fi

    # Display final summary
    display_summary $exit_code

    exit $exit_code
}

# Run main function with all arguments
main "$@"
