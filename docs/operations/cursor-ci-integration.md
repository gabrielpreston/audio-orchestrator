---
title: Cursor CI Integration
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ Cursor CI Integration

# Cursor CI Integration

This document describes the integration of Cursor's `fix-ci` functionality into the Discord Voice Lab GitHub Actions workflow, providing automated fixing of common CI failures.

## Overview

The Cursor CI integration automatically detects and fixes common issues in CI failures, including:
- Linting errors (Black, isort, Ruff, MyPy)
- Formatting issues
- Import sorting problems
- Dockerfile issues
- YAML formatting problems
- Markdown formatting

## Architecture

### Components

1. **`cursor-fix-ci.yaml`** - Main workflow that triggers on CI failures
2. **`services/cursor-fixer/`** - Analysis service for intelligent failure detection
3. **Makefile targets** - Local development integration
4. **Environment configuration** - Cursor API and behavior settings

### Workflow Triggers

- **Automatic**: Triggers when the main CI workflow fails
- **Manual**: Can be triggered manually via `workflow_dispatch`
- **Scheduled**: Optional scheduled runs for maintenance

## Configuration

### Repository Secrets

Add the following secrets to your GitHub repository:

```bash
CURSOR_API_KEY=your_cursor_api_key_here
```

### Environment Variables

Configure in `.env.sample` and copy to appropriate `.env.*` files:

```bash
# Cursor CI Integration
CURSOR_ENABLED=true
CURSOR_AUTO_COMMIT=true
CURSOR_FIX_TARGETS=lint,test,docker
CURSOR_API_KEY=your_cursor_api_key_here
```

### Workflow Permissions

The workflow requires the following permissions:

```yaml
permissions:
  contents: write      # For committing fixes
  pull-requests: write # For creating PRs with fixes
  issues: write        # For creating issue reports
```

## Usage

### Automatic Fixes

The integration automatically triggers when:
1. The main CI workflow fails
2. Fixable issues are detected
3. High-confidence fixes are available

### Manual Triggers

You can manually trigger fixes using:

```bash
# Fix all issues
make cursor-fix

# Fix specific types
make cursor-fix-lint
make cursor-fix-test
make cursor-fix-docker

# Analyze without fixing
make cursor-analyze
```

### GitHub Actions

Trigger via GitHub Actions UI:
1. Go to Actions → Cursor Fix CI
2. Click "Run workflow"
3. Select target job (lint, test, docker-smoke, all)
4. Optionally force fix even if CI passed

## Fixable Issues

### Linting Issues
- **Black formatting**: Code style violations
- **isort imports**: Import sorting and organization
- **Ruff errors**: Code quality and style issues
- **MyPy errors**: Type hint problems

### Test Issues
- **Import errors**: Missing or incorrect imports
- **Syntax errors**: Python syntax problems
- **Indentation**: Indentation inconsistencies

### Docker Issues
- **Dockerfile**: Hadolint violations
- **docker-compose**: YAML formatting and structure
- **Build errors**: Common build configuration issues

### Documentation Issues
- **Markdown**: Formatting and style violations
- **YAML**: Configuration file formatting

## Safety Features

### Confidence Scoring
- Issues are scored 0.0 to 1.0 based on fix confidence
- Only high-confidence fixes (≥0.8) are applied automatically
- Low-confidence fixes require manual review

### Critical Issue Detection
- Security-related issues are never auto-fixed
- API-breaking changes are flagged for manual review
- Critical errors require human intervention

### Rollback Capability
- All fixes are applied in separate commits
- Easy to revert using standard git commands
- Fix workflow can be disabled at any time

## Monitoring

### Fix Success Metrics
- **Success Rate**: Percentage of successfully fixed issues
- **Time to Resolution**: Reduction in manual intervention time
- **False Positive Rate**: Incorrect fixes requiring correction

### Workflow Artifacts
- **Fix Summary**: Detailed report of applied fixes
- **Pre/Post Analysis**: Before and after comparison
- **Verification Results**: Re-run results after fixes

### GitHub Integration
- **Pull Requests**: Automatic PR creation for fixes
- **Issue Comments**: Notifications on fix application
- **Workflow Runs**: Detailed logs and summaries

## Troubleshooting

### Common Issues

#### Cursor CLI Not Found
```bash
# Install Cursor CLI
make cursor-install

# Add to PATH
export PATH="$HOME/.cursor/bin:$PATH"
```

#### API Key Issues
```bash
# Verify API key is set
echo $CURSOR_API_KEY

# Check GitHub secrets
# Go to Settings → Secrets and variables → Actions
```

#### Fix Not Applied
1. Check confidence scores in logs
2. Verify issue is in fixable patterns
3. Review critical issue detection
4. Check file permissions

### Debug Mode

Enable debug logging:

```bash
# Set debug environment
export CURSOR_DEBUG=true
export LOG_LEVEL=debug

# Run with verbose output
make cursor-analyze
```

### Manual Override

Force fixes even with low confidence:

```bash
# Force fix all issues
cursor fix-ci --target=all --force --auto-commit

# Force fix specific type
cursor fix-ci --target=lint --force --auto-commit
```

## Best Practices

### Development Workflow
1. **Pre-commit**: Run `make cursor-fix-lint` before committing
2. **CI Integration**: Let automatic fixes handle routine issues
3. **Manual Review**: Review high-impact fixes manually
4. **Monitoring**: Check fix success rates regularly

### Configuration Management
1. **Environment Files**: Keep Cursor config in `.env.sample`
2. **Secret Rotation**: Rotate API keys regularly
3. **Version Pinning**: Pin Cursor CLI version for consistency
4. **Documentation**: Keep this guide updated with changes

### Quality Assurance
1. **Test Fixes**: Verify fixes don't break functionality
2. **Code Review**: Review auto-generated PRs
3. **Metrics Tracking**: Monitor fix quality over time
4. **Feedback Loop**: Adjust confidence thresholds based on results

## Future Enhancements

### Planned Features
- **Machine Learning**: Project-specific fix patterns
- **Custom Rules**: User-defined fix rules
- **Multi-Language**: Support for additional languages
- **Integration Tests**: Automated fix validation

### Advanced Configuration
- **Fix Policies**: Granular control over fix types
- **Approval Workflows**: Human approval for sensitive fixes
- **Metrics Dashboard**: Visual fix success tracking
- **API Integration**: External system notifications

## Support

### Documentation
- **Proposal**: `docs/proposals/cursor-ci-integration.md`
- **Implementation**: `.github/workflows/cursor-fix-ci.yaml`
- **Service Code**: `services/cursor-fixer/`

### Getting Help
1. Check workflow logs in GitHub Actions
2. Review fix summaries and verification results
3. Consult this documentation
4. Create an issue for complex problems

### Contributing
1. Follow existing code style and patterns
2. Add tests for new fix patterns
3. Update documentation for changes
4. Submit PRs for improvements