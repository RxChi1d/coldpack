<!--
SPDX-FileCopyrightText: 2025 coldpack contributors
SPDX-License-Identifier: MIT
-->

# GitHub Repository Setup Guide

This document provides instructions for setting up the coldpack GitHub repository with all necessary configurations for automated workflows, security, and community features.

## Prerequisites

- Repository owner/admin access to coldpack repository
- PyPI account with permissions to manage coldpack package
- Understanding of GitHub repository settings

## Required Repository Settings

### 1. Branch Protection Rules

Navigate to **Settings > Branches** and create protection rules for the `main` branch:

#### Main Branch Protection
- **Branch name pattern**: `main`
- **Require a pull request before merging**: ✅
  - **Require approvals**: 1
  - **Dismiss stale PR approvals when new commits are pushed**: ✅
  - **Require review from code owners**: ✅
- **Require status checks to pass before merging**: ✅
  - **Require branches to be up to date before merging**: ✅
  - **Required status checks**:
    - `lint (3.9)`, `lint (3.10)`, `lint (3.11)`, `lint (3.12)`, `lint (3.13)`
    - `test (ubuntu-latest, 3.9)` through `test (windows-latest, 3.13)`
    - `CodeQL / Analyze Python Code`
- **Require conversation resolution before merging**: ✅
- **Require signed commits**: ⚠️ (Optional but recommended)
- **Require linear history**: ✅
- **Do not allow bypassing the above settings**: ✅

### 2. PyPI Trusted Publisher Setup

#### On PyPI (pypi.org)
1. Log into your PyPI account
2. Go to "Your projects" → "coldpack" → "Settings" → "Publishing"
3. Add a new trusted publisher with these details:
   - **PyPI project name**: `coldpack`
   - **Owner**: `rxchi1d`
   - **Repository name**: `coldpack`
   - **Workflow filename**: `release.yml`
   - **Environment name**: `pypi`

#### In GitHub Repository
1. Go to **Settings > Environments**
2. Create new environment named `pypi`
3. Add protection rules:
   - **Required reviewers**: Add yourself
   - **Wait timer**: 0 minutes
   - **Deployment branches**: Only selected branches: `main`

### 3. Repository Secrets and Variables

Navigate to **Settings > Secrets and variables > Actions**:

#### Repository Secrets
No manual secrets are required (we use OIDC for PyPI publishing).

#### Repository Variables
- `PYTHON_VERSION_MATRIX`: `["3.9", "3.10", "3.11", "3.12", "3.13"]`

### 4. Code Security Settings

Navigate to **Settings > Code security and analysis**:

#### Dependency Graph
- **Enable dependency graph**: ✅

#### Dependabot
- **Enable Dependabot alerts**: ✅
- **Enable Dependabot security updates**: ✅
- **Enable Dependabot version updates**: ✅ (configured via `.github/dependabot.yml`)

#### Code Scanning
- **Enable CodeQL analysis**: ✅
- **Default setup**: Use advanced setup (we have custom `.github/workflows/codeql.yml`)

#### Secret Scanning
- **Enable secret scanning**: ✅
- **Enable push protection**: ✅

### 5. Repository Features

Navigate to **Settings > General**:

#### Features
- **Wikis**: ❌ (use docs/ directory instead)
- **Issues**: ✅
- **Sponsorships**: ⚠️ (optional)
- **Preserve this repository**: ✅
- **Discussions**: ✅

#### Pull Requests
- **Allow merge commits**: ❌
- **Allow squash merging**: ✅
  - **Default to pull request title and commit details**: ✅
- **Allow rebase merging**: ✅
- **Always suggest updating pull request branches**: ✅
- **Allow auto-merge**: ✅
- **Automatically delete head branches**: ✅

## Webhook Configuration (Optional)

For advanced integrations, you may want to configure webhooks:

### Discord/Slack Notifications
1. Navigate to **Settings > Webhooks**
2. Add webhook URL for your Discord/Slack channel
3. Select events: `push`, `pull_request`, `release`

## Testing the Setup

### 1. Create a Test PR
```bash
# Create a test branch
git checkout -b test/github-setup
echo "# Test" > TEST.md
git add TEST.md
git commit -m "test: verify GitHub configuration"
git push origin test/github-setup
```

### 2. Verify CI Pipeline
- Open the PR and ensure all status checks run
- Verify that branch protection prevents direct merge
- Check that CodeQL analysis completes

### 3. Test Release Process
```bash
# Create a test tag (remove after testing)
git tag v0.0.1-test
git push origin v0.0.1-test
```

- Verify build workflow runs
- Check that PyPI publishing fails gracefully (due to test tag)
- Verify GitHub release is created

### 4. Clean Up Test Artifacts
```bash
# Remove test tag and branch
git tag -d v0.0.1-test
git push origin :refs/tags/v0.0.1-test
git branch -D test/github-setup
git push origin :test/github-setup
```

## Troubleshooting

### Common Issues

#### PyPI Publishing Fails
- Verify trusted publisher configuration on PyPI
- Check that environment name matches exactly: `pypi`
- Ensure branch protection allows the pypi environment

#### Status Checks Not Required
- Verify status check names match exactly
- Run workflows once to populate available checks
- Check that branch protection is applied to `main`

#### Dependabot PRs Failing
- Check that Python version constraints in dependabot.yml are correct
- Verify CI supports all Python versions specified

#### CodeQL Analysis Fails
- Check that CodeQL workflow has correct permissions
- Verify Python dependencies install correctly in CI

### Support

If you encounter issues during setup:

1. Check GitHub's official documentation for the specific feature
2. Review the Actions logs for detailed error messages
3. Open an issue in the coldpack repository with setup questions

## Maintenance

### Regular Tasks

#### Monthly
- Review Dependabot PRs and merge approved updates
- Check CodeQL analysis results for new security issues
- Update branch protection rules if workflow names change

#### Quarterly
- Review and update trusted publisher configuration
- Audit repository access and permissions
- Update this setup documentation if procedures change

#### Annually
- Review security settings and enable new GitHub features
- Update Python version matrix as new versions are released
- Audit and clean up old workflow runs and artifacts

---

**Note**: This configuration provides a robust foundation for coldpack development. Adjust settings based on project needs and GitHub's evolving feature set.
