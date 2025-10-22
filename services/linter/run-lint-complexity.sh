#!/usr/bin/env bash
set -euo pipefail

echo "Running complexity analysis..."
# Run radon complexity analysis
radon cc --min B services/
radon mi --min B services/

echo "Complexity analysis complete!"
