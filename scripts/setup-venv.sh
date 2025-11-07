#!/bin/bash
# Setup virtual environment with all required packages from requirements.txt files
# Follows Docker build patterns for consistent dependency resolution
set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function for colored output
info() {
	echo -e "${BLUE}ℹ${NC} $1"
}

success() {
	echo -e "${GREEN}✓${NC} $1"
}

warning() {
	echo -e "${YELLOW}⚠${NC} $1"
}

error() {
	echo -e "${RED}❌${NC} $1"
}

# Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
	error "Python 3 is required but not found. Please install Python 3 first."
	exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
info "Found Python $PYTHON_VERSION"

# Create .venv if it doesn't exist
if [ ! -d "./.venv" ]; then
	info "Creating virtual environment at ./.venv"
	python3 -m venv .venv
	success "Virtual environment created"
else
	info "Virtual environment already exists at ./.venv"
fi

# Use .venv Python
PYTHON="./.venv/bin/python3"
PIP="./.venv/bin/pip"

# Upgrade pip first
info "Upgrading pip to latest version"
"$PIP" install --upgrade pip setuptools wheel --quiet

# Function to install requirements with error handling for optional dependencies
install_requirements() {
	local req_file="$1"
	local description="${2:-$req_file}"
	local optional="${3:-false}"

	if [ ! -f "$req_file" ]; then
		warning "  Requirements file not found: $req_file (skipping)"
		return 0
	fi

	info "  Installing from $req_file"

	# Capture stderr to check for specific errors
	local install_output
	local install_status=0

	# Install and capture output
	install_output=$("$PIP" install -r "$req_file" 2>&1) || install_status=$?

	# Check for specific known issues with optional dependencies
	if [ $install_status -ne 0 ]; then
		# Check if it's a tflite-runtime error (optional dependency for openwakeword on Linux)
		# This happens when installing discord requirements which include openwakeword
		if echo "$install_output" | grep -qi "tflite-runtime" && \
		   echo "$install_output" | grep -qiE "No matching distribution|Could not find a version"; then
			warning "  tflite-runtime not available for this platform (Linux x86_64)"
			warning "  This is an optional dependency for openwakeword - it will use ONNX runtime instead"
			info "  Installing openwakeword without tflite-runtime dependency..."

			# Install openwakeword with --no-deps to skip tflite-runtime
			# Then install its other dependencies manually
			"$PIP" install --no-deps openwakeword==0.6.0 2>/dev/null || {
				warning "  Could not install openwakeword - wake word detection may be limited"
			}

			# Install openwakeword's required dependencies (excluding tflite-runtime)
			# These are needed for ONNX inference and signal processing
			# Note: We install these normally (not --no-deps) so their dependencies are included
			info "  Installing openwakeword dependencies (onnxruntime, scipy, etc.)..."
			"$PIP" install \
				"onnxruntime>=1.16.0,<2.0" \
				"scipy>=1.9.0,<2.0" \
				2>/dev/null || {
				warning "  Some openwakeword dependencies may have failed to install"
			}
			# Note: numpy is usually already installed, but if not, it will be installed as a dependency

			# Install other dependencies from the requirements file (excluding openwakeword)
			# Create a temp file without openwakeword to avoid re-triggering the error
			local temp_req=$(mktemp)
			grep -v "^openwakeword" "$req_file" > "$temp_req" 2>/dev/null || cp "$req_file" "$temp_req"

			# Install remaining dependencies
			if "$PIP" install -r "$temp_req" 2>/dev/null; then
				success "  Installed other requirements from $req_file (openwakeword installed separately)"
			else
				warning "  Some dependencies may have failed to install"
			fi
			rm -f "$temp_req"
			return 0
		fi

		# Check for version conflicts (warn but continue - these are often non-fatal)
		if echo "$install_output" | grep -q "dependency conflicts\|incompatible"; then
			warning "  Version conflicts detected (this is normal when combining requirements)"
			warning "  Attempting to resolve with --upgrade..."
			# Try to continue with --upgrade to resolve conflicts
			if "$PIP" install -r "$req_file" --upgrade 2>&1 | tee /dev/stderr | grep -q "Successfully installed\|Requirement already satisfied"; then
				success "  Installed requirements from $req_file (with conflict resolution)"
				return 0
			fi
			# If upgrade also fails, continue anyway (conflicts may be non-fatal)
			warning "  Continuing despite conflicts (packages may have version mismatches)"
			return 0
		fi

		# If optional, warn and continue; otherwise fail
		if [ "$optional" = "true" ]; then
			warning "  Failed to install optional requirements from $req_file (continuing)"
			return 0
		else
			error "  Failed to install requirements from $req_file"
			echo "$install_output" | head -20
			return 1
		fi
	fi

	success "  Installed requirements from $req_file"
	return 0
}

# Install base requirements first (order matters - matches Docker build pattern)
# Tier 1: Base requirements (shared across all services)
BASE_REQUIREMENTS=(
	"services/requirements-base.txt"
)

info "Installing base requirements (Tier 1)..."
for req_file in "${BASE_REQUIREMENTS[@]}"; do
	install_requirements "$req_file" "$req_file" false || exit 1
done

# Tier 2: Development requirements
if [ -f "services/requirements-dev.txt" ]; then
	info "Installing development requirements (Tier 2)..."
	install_requirements "services/requirements-dev.txt" "development tools" false || exit 1
fi

# Tier 3: Service-specific requirements
# Note: Service requirements.txt files use `-r ../requirements-base.txt` which pip resolves
# Pip will skip already-installed packages, so this is safe
info "Finding service-specific requirements.txt files..."
SERVICE_REQUIREMENTS=()

# Define service installation order (matching Docker build patterns)
# Core services first, then supporting services
SERVICE_ORDER=(
	"services/common"  # Not a service, but check for requirements
	"services/discord"
	"services/stt"
	"services/orchestrator"
	"services/flan"
	"services/bark"
	"services/guardrails"
	"services/testing"
)

# Find service requirements in order
for service_dir in "${SERVICE_ORDER[@]}"; do
	if [ -f "$service_dir/requirements.txt" ]; then
		SERVICE_REQUIREMENTS+=("$service_dir/requirements.txt")
	fi
done

# Find any remaining service requirements not in the ordered list
while IFS= read -r -d '' file; do
	# Check if file is already in our list
	found=false
	for req in "${SERVICE_REQUIREMENTS[@]}"; do
		if [ "$req" = "$file" ]; then
			found=true
			break
		fi
	done
	if [ "$found" = "false" ]; then
		SERVICE_REQUIREMENTS+=("$file")
	fi
done < <(find services -maxdepth 2 -name "requirements.txt" -type f -print0 | sort -z)

# Install service-specific requirements
if [ ${#SERVICE_REQUIREMENTS[@]} -eq 0 ]; then
	warning "No service-specific requirements.txt files found"
else
	info "Installing service-specific requirements (Tier 3, ${#SERVICE_REQUIREMENTS[@]} files)..."
	for req_file in "${SERVICE_REQUIREMENTS[@]}"; do
		# Make discord requirements optional if tflite-runtime fails (it's optional)
		if [[ "$req_file" == *"discord"* ]]; then
			install_requirements "$req_file" "$req_file" false || {
				warning "  Discord requirements had issues (some dependencies may be optional)"
				warning "  Continuing with other services..."
			}
		else
			install_requirements "$req_file" "$req_file" false || exit 1
		fi
	done
fi

# Tier 4: Tool requirements (linter, tester, security)
TOOL_SERVICES=(
	"services/linter"
	"services/tester"
	"services/security"
)

info "Installing tool requirements (Tier 4)..."
for tool_dir in "${TOOL_SERVICES[@]}"; do
	if [ -f "$tool_dir/requirements.txt" ]; then
		install_requirements "$tool_dir/requirements.txt" "$tool_dir" false || {
			warning "  Tool requirements from $tool_dir had issues (continuing)"
		}
	fi
done

# Tier 5: Test requirements (installed last)
if [ -f "services/requirements-test.txt" ]; then
	info "Installing test requirements (Tier 5)..."
	install_requirements "services/requirements-test.txt" "test framework" false || exit 1
fi

# Verify installation
info "Verifying installation..."
INSTALLED_PACKAGES=$("$PIP" list --format=freeze | wc -l)
success "Virtual environment setup complete!"
info "Installed packages: $INSTALLED_PACKAGES"
echo ""
info "To activate the virtual environment, run:"
echo "  source .venv/bin/activate"
echo ""
info "Or use the Python interpreter directly:"
echo "  ./.venv/bin/python3"

