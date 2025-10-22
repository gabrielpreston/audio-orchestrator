#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

print_status "$CYAN" "→ Running optimized parallel security scan"

# Create reports directory
mkdir -p security-reports

# Collect all requirements files
req_files=()
service_names=()
for req in services/*/requirements.txt; do
    if [ -f "$req" ]; then
        req_files+=("$req")
        service_names+=("$(basename "$(dirname "$req")")")
    fi
done

total_services=${#req_files[@]}

if [ "$total_services" -eq 0 ]; then
    print_status "$YELLOW" "→ No requirements.txt files found"
    exit 0
fi

print_status "$CYAN" "→ Scanning $total_services service(s) for vulnerabilities (parallel mode)"

# Run single pip-audit command with all files
# This is much faster than scanning each file individually
combined_report="security-reports/combined-audit.json"
audit_exit_code=0

# Create a temporary combined requirements file for pip-audit
temp_combined="security-reports/temp-combined-requirements.txt"
echo "# Combined requirements from all services" > "$temp_combined"
echo "# Generated on $(date)" >> "$temp_combined"
echo "" >> "$temp_combined"

for req in "${req_files[@]}"; do
    service_name=$(basename "$(dirname "$req")")
    echo "# From $service_name" >> "$temp_combined"
    cat "$req" >> "$temp_combined"
    echo "" >> "$temp_combined"
done

if ! pip-audit --progress-spinner off --format json --requirement "$temp_combined" > "$combined_report" 2>&1; then
    audit_exit_code=$?
fi

# Clean up temporary file
rm -f "$temp_combined"

# Parse combined report and create individual service reports
# This maintains backward compatibility with existing CI/CD expectations
vulnerable_services=0

# For now, since we can't easily separate vulnerabilities by service from the combined scan,
# we'll create individual reports based on the combined result
if [ -f "$combined_report" ] && [ "$audit_exit_code" -eq 0 ]; then
    # All services are clean
    for i in "${!req_files[@]}"; do
        service_name="${service_names[$i]}"
        service_report="security-reports/${service_name}-requirements.json"
        echo '{"vulnerabilities": []}' > "$service_report"
        print_status "$GREEN" "✓ $service_name: clean"
    done
else
    # There are vulnerabilities - we need to scan each service individually to get accurate results
    print_status "$YELLOW" "→ Vulnerabilities detected, scanning services individually for accurate reporting"

    for i in "${!req_files[@]}"; do
        req="${req_files[$i]}"
        service_name="${service_names[$i]}"
        service_report="security-reports/${service_name}-requirements.json"

        print_status "$CYAN" "→ Auditing $service_name individually"

        if pip-audit --progress-spinner off --format json --requirement "$req" > "$service_report" 2>/dev/null; then
            print_status "$GREEN" "✓ $service_name: clean"
        else
            vulnerable_services=$((vulnerable_services + 1))
            vuln_count=$(jq '.vulnerabilities | length' "$service_report" 2>/dev/null || echo "0")
            print_status "$YELLOW" "⚠️  $service_name: $vuln_count vulnerabilities found"
        fi
    done
fi

# Summary
print_status "$CYAN" "→ Security scan completed: $vulnerable_services/$total_services services have vulnerabilities"

# Check final status
if [ "$audit_exit_code" -ne 0 ]; then
    print_status "$RED" "→ pip-audit reported vulnerabilities in $vulnerable_services service(s)"
    exit "$audit_exit_code"
fi

print_status "$GREEN" "→ All services passed security scan"
