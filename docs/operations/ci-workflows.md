---
title: CI/CD Workflow Architecture
author: Audio Orchestrator Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Operations ▸ CI/CD Workflows

# CI/CD Workflow Architecture

## Overview

The audio-orchestrator project uses a modern multi-workflow CI architecture designed for fast feedback and efficient resource utilization.

## Workflow Structure

### Main CI (Orchestrator)

-  **Purpose**: Change detection and workflow routing
-  **Triggers**: Push to main, pull requests, manual dispatch
-  **Runtime**: ~2-3 minutes (change detection only)

### Core CI (Python Focus)

-  **Purpose**: Fast Python feedback
-  **Triggers**: Python file changes, pyproject.toml changes
-  **Jobs**: lint, test-unit, test-component
-  **Runtime**: ~5-10 minutes

### Docker CI (Infrastructure Focus)

-  **Purpose**: Base image building and service validation
-  **Triggers**: Dockerfile changes, base image changes
-  **Jobs**: build-base-images (9 images), test-integration, docker-smoke (9 services)
-  **Runtime**: ~20-30 minutes

### Docs CI (Documentation Focus)

-  **Purpose**: Documentation validation
-  **Triggers**: Documentation changes
-  **Jobs**: docs-verify
-  **Runtime**: ~2-3 minutes

### Security CI (Security Focus)

-  **Purpose**: Dependency vulnerability scanning
-  **Triggers**: Dependency file changes
-  **Jobs**: security-scan
-  **Runtime**: ~5-10 minutes

## Auto-Fix Integration

The auto-fix workflow monitors all new workflows and provides workflow-specific analysis and fixes.

## Benefits

-  **Fast feedback**: Core CI completes in ~5-10 minutes vs 15-30 minutes
-  **Parallel execution**: Independent workflows run simultaneously
-  **Better maintainability**: ~200-400 lines per workflow vs 1100+ lines
-  **Workflow-aware auto-fix**: Targeted analysis and fixes per workflow type
-  **Resource efficiency**: Only build what's needed based on changes
-  **Clear separation**: Each workflow has single responsibility
-  **Complete coverage**: All 9 base images and 9 services properly tested
