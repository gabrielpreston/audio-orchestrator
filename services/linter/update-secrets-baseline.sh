#!/usr/bin/env bash
set -euo pipefail

echo "Updating secrets baseline..."
echo "This will scan for secrets and update the baseline file."
echo "This should be run manually when you want to update the baseline."
echo ""

# Run detect-secrets to update the baseline
detect-secrets scan --update .secrets.baseline

echo "Secrets baseline updated successfully!"
echo "You can now commit the updated .secrets.baseline file."
