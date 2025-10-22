#!/bin/bash
# Comprehensive audio pipeline validation script

set -e  # Exit on any error

echo "=== Audio Pipeline Validation ==="
echo "Timestamp: $(date)"
echo ""

# Configuration
STT_URL=${STT_URL:-"http://localhost:9000"}
OUTPUT_DIR=${OUTPUT_DIR:-"./validation_output"}
BASELINE_FILE=${BASELINE_FILE:-"baseline_results.json"}

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Function to run command and capture output
run_command() {
    local cmd="$1"
    local output_file="$2"
    local description="$3"
    
    echo "Running: $description"
    echo "Command: $cmd"
    echo "---"
    
    if eval "$cmd" > "$output_file" 2>&1; then
        echo "✅ SUCCESS: $description"
        echo "Output saved to: $output_file"
    else
        echo "❌ FAILED: $description"
        echo "Error output:"
        cat "$output_file"
        return 1
    fi
    echo ""
}

# Function to check service health
check_service_health() {
    echo "=== Service Health Check ==="
    
    # Check if STT service is running
    if curl -s "$STT_URL/health/ready" > /dev/null 2>&1; then
        echo "✅ STT service is running at $STT_URL"
        
        # Get health details
        curl -s "$STT_URL/health/ready" | jq '.' > "$OUTPUT_DIR/health_check.json"
        echo "Health details saved to: $OUTPUT_DIR/health_check.json"
    else
        echo "❌ STT service is not running at $STT_URL"
        echo "Please start the STT service before running validation"
        exit 1
    fi
    echo ""
}

# Function to run baseline measurements
run_baseline_measurements() {
    echo "=== Baseline Measurements ==="
    
    run_command \
        "python -m services.tests.measure_baseline --stt-url $STT_URL" \
        "$OUTPUT_DIR/baseline_measurements.log" \
        "Baseline performance measurements"
    
    # Check if baseline results were generated
    if [ -f "$BASELINE_FILE" ]; then
        echo "✅ Baseline results generated: $BASELINE_FILE"
        cp "$BASELINE_FILE" "$OUTPUT_DIR/"
    else
        echo "⚠️  Baseline results file not found: $BASELINE_FILE"
    fi
    echo ""
}

# Function to run component tests
run_component_tests() {
    echo "=== Component Tests ==="
    
    run_command \
        "make test-component SERVICE=stt" \
        "$OUTPUT_DIR/component_tests.log" \
        "Component tests for STT service"
    
    # Run specific enhancement component tests
    run_command \
        "pytest services/tests/component/test_enhancement_*.py -v" \
        "$OUTPUT_DIR/enhancement_component_tests.log" \
        "Enhancement component tests"
    echo ""
}

# Function to run integration tests
run_integration_tests() {
    echo "=== Integration Tests ==="
    
    run_command \
        "make test-integration SERVICE=stt" \
        "$OUTPUT_DIR/integration_tests.log" \
        "Integration tests for STT service"
    
    # Run specific enhancement integration tests
    run_command \
        "pytest services/tests/integration/test_stt_enhancement_integration.py -v" \
        "$OUTPUT_DIR/enhancement_integration_tests.log" \
        "Enhancement integration tests"
    echo ""
}

# Function to run quality tests
run_quality_tests() {
    echo "=== Quality Tests ==="
    
    run_command \
        "pytest services/tests/quality/test_audio_quality.py -v" \
        "$OUTPUT_DIR/quality_tests.log" \
        "Audio quality tests"
    
    # Run WER calculator tests
    run_command \
        "pytest services/tests/quality/wer_calculator.py -v" \
        "$OUTPUT_DIR/wer_calculator_tests.log" \
        "WER calculator tests"
    echo ""
}

# Function to run performance tests
run_performance_tests() {
    echo "=== Performance Tests ==="
    
    run_command \
        "pytest services/tests/component/test_enhancement_performance.py -v" \
        "$OUTPUT_DIR/performance_tests.log" \
        "Enhancement performance tests"
    echo ""
}

# Function to run error handling tests
run_error_tests() {
    echo "=== Error Handling Tests ==="
    
    run_command \
        "pytest services/tests/component/test_enhancement_errors.py -v" \
        "$OUTPUT_DIR/error_tests.log" \
        "Enhancement error handling tests"
    
    run_command \
        "pytest services/tests/component/test_enhancement_config.py -v" \
        "$OUTPUT_DIR/config_tests.log" \
        "Enhancement configuration tests"
    echo ""
}

# Function to run audio format tests
run_audio_format_tests() {
    echo "=== Audio Format Tests ==="
    
    run_command \
        "pytest services/tests/component/test_enhancement_audio_formats.py -v" \
        "$OUTPUT_DIR/audio_format_tests.log" \
        "Audio format edge case tests"
    echo ""
}

# Function to generate summary report
generate_summary_report() {
    echo "=== Generating Summary Report ==="
    
    local report_file="$OUTPUT_DIR/validation_summary.md"
    
    cat > "$report_file" << EOF
# Audio Pipeline Validation Summary

**Timestamp**: $(date)
**STT URL**: $STT_URL
**Output Directory**: $OUTPUT_DIR

## Test Results

### Service Health
- **Status**: $(curl -s "$STT_URL/health/ready" | jq -r '.status' 2>/dev/null || echo "Unknown")
- **Enhancer Loaded**: $(curl -s "$STT_URL/health/ready" | jq -r '.components.enhancer_loaded' 2>/dev/null || echo "Unknown")
- **Enhancer Enabled**: $(curl -s "$STT_URL/health/ready" | jq -r '.components.enhancer_enabled' 2>/dev/null || echo "Unknown")

### Test Categories

#### Baseline Measurements
- **Status**: $(if [ -f "$OUTPUT_DIR/baseline_measurements.log" ]; then echo "✅ Completed"; else echo "❌ Failed"; fi)
- **Output**: $OUTPUT_DIR/baseline_measurements.log

#### Component Tests
- **Status**: $(if [ -f "$OUTPUT_DIR/component_tests.log" ]; then echo "✅ Completed"; else echo "❌ Failed"; fi)
- **Output**: $OUTPUT_DIR/component_tests.log

#### Integration Tests
- **Status**: $(if [ -f "$OUTPUT_DIR/integration_tests.log" ]; then echo "✅ Completed"; else echo "❌ Failed"; fi)
- **Output**: $OUTPUT_DIR/integration_tests.log

#### Quality Tests
- **Status**: $(if [ -f "$OUTPUT_DIR/quality_tests.log" ]; then echo "✅ Completed"; else echo "❌ Failed"; fi)
- **Output**: $OUTPUT_DIR/quality_tests.log

#### Performance Tests
- **Status**: $(if [ -f "$OUTPUT_DIR/performance_tests.log" ]; then echo "✅ Completed"; else echo "❌ Failed"; fi)
- **Output**: $OUTPUT_DIR/performance_tests.log

#### Error Handling Tests
- **Status**: $(if [ -f "$OUTPUT_DIR/error_tests.log" ]; then echo "✅ Completed"; else echo "❌ Failed"; fi)
- **Output**: $OUTPUT_DIR/error_tests.log

#### Audio Format Tests
- **Status**: $(if [ -f "$OUTPUT_DIR/audio_format_tests.log" ]; then echo "✅ Completed"; else echo "❌ Failed"; fi)
- **Output**: $OUTPUT_DIR/audio_format_tests.log

## Files Generated

EOF

    # List all generated files
    find "$OUTPUT_DIR" -type f -name "*.log" -o -name "*.json" -o -name "*.md" | sort >> "$report_file"
    
    echo "✅ Summary report generated: $report_file"
    echo ""
}

# Function to check dependencies
check_dependencies() {
    echo "=== Checking Dependencies ==="
    
    # Check required commands
    local required_commands=("python" "pytest" "make" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        if command -v "$cmd" > /dev/null 2>&1; then
            echo "✅ $cmd is available"
        else
            echo "❌ $cmd is not available"
            exit 1
        fi
    done
    
    # Check Python packages
    if python -c "import services.tests.fixtures.audio_samples" 2>/dev/null; then
        echo "✅ Audio test fixtures available"
    else
        echo "❌ Audio test fixtures not available"
        exit 1
    fi
    
    echo ""
}

# Main execution
main() {
    echo "Starting audio pipeline validation..."
    echo ""
    
    # Check dependencies
    check_dependencies
    
    # Check service health
    check_service_health
    
    # Run all test categories
    run_baseline_measurements
    run_component_tests
    run_integration_tests
    run_quality_tests
    run_performance_tests
    run_error_tests
    run_audio_format_tests
    
    # Generate summary report
    generate_summary_report
    
    echo "=== Validation Complete ==="
    echo "Results saved to: $OUTPUT_DIR"
    echo "Summary report: $OUTPUT_DIR/validation_summary.md"
    echo ""
    
    # Check if any tests failed
    local failed_tests=0
    for log_file in "$OUTPUT_DIR"/*.log; do
        if [ -f "$log_file" ] && grep -q "FAILED\|ERROR\|❌" "$log_file"; then
            failed_tests=$((failed_tests + 1))
        fi
    done
    
    if [ $failed_tests -eq 0 ]; then
        echo "🎉 All tests passed!"
        exit 0
    else
        echo "⚠️  $failed_tests test categories had failures"
        echo "Check the log files in $OUTPUT_DIR for details"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --stt-url)
            STT_URL="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --baseline-file)
            BASELINE_FILE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --stt-url URL        STT service URL (default: http://localhost:9000)"
            echo "  --output-dir DIR     Output directory (default: ./validation_output)"
            echo "  --baseline-file FILE Baseline results file (default: baseline_results.json)"
            echo "  --help               Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  STT_URL              STT service URL"
            echo "  OUTPUT_DIR           Output directory"
            echo "  BASELINE_FILE         Baseline results file"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main "$@"
