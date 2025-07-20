<!--
🚨 IMPORTANT: PR Title Convention
Your PR title must follow conventional commits format:
<type>(<scope>): <description>

Examples:
✅ feat: add async operations with progress callbacks
✅ fix: resolve archive verification on Windows systems
✅ docs: add comprehensive CLI reference guide
✅ perf: optimize memory usage for large archive processing

❌ Add async support
❌ Fix Windows bug
❌ Update docs
-->

## What's Changed

<!-- Describe the changes made in this PR -->

## Type of Change

<!-- Check all that apply -->
- [ ] 🚀 New feature (non-breaking change which adds functionality)
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📚 Documentation update
- [ ] 🔧 Code refactoring
- [ ] ⚡ Performance improvement
- [ ] 🧪 Test addition or improvement
- [ ] 🔄 CI/CD changes

## Testing

<!-- Describe the tests that you ran to verify your changes -->
- [ ] Existing tests pass (`uv run pytest`)
- [ ] New tests added (if applicable)
- [ ] Manual testing performed
- [ ] Cross-platform testing (if applicable)

## Code Quality

<!-- Confirm code quality checks -->
- [ ] Code formatted with ruff (`uv run ruff format .`)
- [ ] Linting passes (`uv run ruff check --fix .`)
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] All quality checks pass locally

## Checklist

<!-- Check all that apply -->
- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published in downstream modules

## Archive Format Support

<!-- If this PR affects archive handling, check applicable formats -->
- [ ] tar.zst (coldpack primary format)
- [ ] 7z archives
- [ ] zip archives
- [ ] tar.gz archives
- [ ] Other formats (specify below)

## Cold Storage Features

<!-- If this PR affects cold storage functionality, check applicable areas -->
- [ ] Archive creation and compression
- [ ] Integrity verification (dual hash)
- [ ] PAR2 redundancy generation
- [ ] Archive extraction and validation
- [ ] Cross-platform compatibility
- [ ] Performance optimization

## Related Issues

<!-- Link any related issues here -->
Fixes #(issue number)
Closes #(issue number)
Related to #(issue number)

## Breaking Changes

<!-- If this is a breaking change, describe what breaks and how to migrate -->
- [ ] This PR introduces breaking changes

If yes, describe the breaking changes and migration path:

## Additional Notes

<!-- Any additional information for reviewers -->

## Documentation Updates

<!-- If documentation changes are needed -->
- [ ] README.md updated
- [ ] CLI_REFERENCE.md updated
- [ ] CLAUDE.md updated (if development process changes)
- [ ] Code comments and docstrings updated
