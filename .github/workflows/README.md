# GitHub Actions Workflows

## Overview

This project uses GitHub Actions for continuous integration and automated semantic releases.

## Workflows

### CI (`ci.yml`)

Runs on every push to `main`/`develop` and on all pull requests.

**Jobs:**

1. **Test** - Runs on matrix of Python 3.11/3.12 × Ubuntu/macOS
   - Linting with `ruff`
   - Formatting checks with `ruff`
   - Type checking with `mypy`
   - Fast tests (excludes slow/integration tests)
   - Coverage report (uploaded to Codecov on Ubuntu/3.11)

2. **Lint Commits** - Validates commit messages for conventional commits format
   - Only runs on PRs
   - Uses commitlint to enforce format

3. **Pre-commit** - Runs all pre-commit hooks on all files
   - Ensures consistent formatting and style

### Release (`release.yml`)

Runs on every push to `main` branch.

**Jobs:**

1. **Semantic Release**
   - Analyzes commits since last release
   - Determines next version (major.minor.patch) based on conventional commits
   - Generates CHANGELOG.md
   - Creates GitHub release
   - Commits version bump to `main`

2. **Build and Publish** (only if new release)
   - Builds Python wheel and sdist
   - Publishes to PyPI (requires `PYPI_API_TOKEN` secret)
   - Attaches artifacts to GitHub release

## Conventional Commits

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automated versioning.

### Commit Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Types

| Type       | Description                    | Version Bump |
| ---------- | ------------------------------ | ------------ |
| `feat`     | New feature                    | Minor        |
| `fix`      | Bug fix                        | Patch        |
| `perf`     | Performance improvement        | Patch        |
| `docs`     | Documentation only             | Patch        |
| `refactor` | Code refactoring               | Patch        |
| `style`    | Code style (formatting, etc)   | Patch        |
| `test`     | Adding/updating tests          | None         |
| `build`    | Build system or dependencies   | None         |
| `ci`       | CI/CD configuration            | None         |
| `chore`    | Other maintenance              | None         |
| `revert`   | Revert previous commit         | Patch        |

### Breaking Changes

Add `BREAKING CHANGE:` in the commit footer or `!` after type/scope to trigger a major version bump:

```
feat(storage)!: change relation graph API

BREAKING CHANGE: RelationGraphPort.add_entity() now returns UUID instead of string
```

### Scopes

Available scopes (enforced by commitlint):
- `core`, `extractors`, `storage`, `services`, `tools`, `prompts`
- `config`, `cli`, `tests`, `deps`, `release`
- `no-release` - prevents a release from being triggered

### Examples

```bash
# Feature (minor version bump)
git commit -m "feat(extractors): add Swift language extractor"

# Bug fix (patch version bump)
git commit -m "fix(storage): handle null entity IDs in Neo4j backend"

# Breaking change (major version bump)
git commit -m "feat(storage)!: replace StateDB with port-based interface

BREAKING CHANGE: All services must now depend on StatePort instead of StateDB directly"

# Documentation (patch version bump)
git commit -m "docs: update CLAUDE.md with current architecture"

# Chore (no version bump)
git commit -m "chore(deps): update tree-sitter to 0.24.1"

# Prevent release
git commit -m "chore(no-release): update internal tooling"
```

## Setup Requirements

### Repository Secrets

Configure these secrets in GitHub repository settings:

1. **`PYPI_API_TOKEN`** (required for PyPI publishing)
   - Get from https://pypi.org/manage/account/token/
   - Set as repository secret

2. **`GITHUB_TOKEN`** (automatically provided)
   - Used for creating releases
   - No setup needed

### Branch Protection

Recommended branch protection rules for `main`:

- Require pull request reviews before merging
- Require status checks to pass:
  - `Test Python 3.11 on ubuntu-latest`
  - `Test Python 3.11 on macos-latest`
  - `Pre-commit checks`
  - `Lint commit messages` (for PRs)
- Require conversation resolution before merging
- Require linear history (optional)

### PyPI Publishing

To enable PyPI publishing:

1. Create a PyPI account at https://pypi.org
2. Generate an API token: https://pypi.org/manage/account/token/
3. Add token as `PYPI_API_TOKEN` secret in GitHub
4. Update `.releaserc.json` with correct `repositoryUrl`

## Local Development

### Install pre-commit hooks

```bash
uv sync --dev
mise run pre-commit-install
```

### Run pre-commit manually

```bash
mise run pre-commit-run
```

### Update hooks

```bash
mise run pre-commit-update
```

## Troubleshooting

### Commits not triggering release

- Check that commit follows conventional commit format
- Verify commit type triggers a release (see table above)
- Ensure `[skip ci]` is not in commit message
- Check GitHub Actions logs for errors

### Release fails to publish to PyPI

- Verify `PYPI_API_TOKEN` secret is set
- Check token has correct permissions
- Ensure package name is available on PyPI

### Type errors in CI but not locally

- CI runs strict mypy checks
- Run `mise run typecheck` locally
- Check mypy configuration in `pyproject.toml`
