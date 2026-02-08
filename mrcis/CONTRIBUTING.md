# Contributing to MRCIS

Thank you for your interest in contributing to the Multi-Repository Code Intelligence System (MRCIS)!

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- [mise](https://mise.jdx.dev/) task runner (optional but recommended)
- Git

### Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/OWNER/REPO.git
   cd rag-indexing/mrcis
   ```

2. **Install dependencies**

   ```bash
   uv sync --dev
   ```

3. **Install pre-commit hooks**

   ```bash
   mise run pre-commit-install
   # Or directly:
   uv run pre-commit install --install-hooks
   uv run pre-commit install --hook-type commit-msg
   ```

4. **Verify setup**

   ```bash
   mise run test-fast
   mise run check
   ```

## Development Workflow

### Making Changes

1. **Create a feature branch**

   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make your changes**

   Follow the architecture guidelines in `CLAUDE.md`:
   - Adhere to SOLID principles
   - Add tests for new functionality
   - Update documentation as needed

3. **Run quality checks**

   ```bash
   mise run fix          # Auto-fix lint and formatting
   mise run typecheck    # Run mypy
   mise run test-fast    # Run tests
   ```

4. **Commit with conventional commits**

   ```bash
   git commit -m "feat(extractors): add Swift language extractor"
   ```

   See [Commit Message Format](#commit-message-format) below.

5. **Push and create PR**

   ```bash
   git push origin feat/my-feature
   ```

### Running Tests

```bash
# Fast tests (excludes slow/integration)
mise run test-fast

# All tests
mise run test

# Unit tests only
mise run test-unit

# Integration tests only
mise run test-integration

# With coverage
mise run test-cov

# Stop on first failure
mise run test-x
```

### Code Quality

```bash
# Run all checks
mise run check

# Fix auto-fixable issues
mise run fix

# Individual checks
mise run lint          # Ruff linter
mise run format-check  # Ruff formatter
mise run typecheck     # Mypy type checker
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`:
- Ruff linting and formatting
- Mypy type checking
- Fast tests (skip slow/integration)
- Conventional commit message validation
- File quality checks (trailing whitespace, etc.)

To run manually:

```bash
mise run pre-commit-run
```

To skip hooks (not recommended):

```bash
git commit --no-verify
```

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) for automated versioning and changelog generation.

### Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature (minor version bump)
- `fix`: Bug fix (patch version bump)
- `docs`: Documentation only (patch version bump)
- `refactor`: Code refactoring (patch version bump)
- `perf`: Performance improvement (patch version bump)
- `style`: Code style/formatting (patch version bump)
- `test`: Adding/updating tests (no version bump)
- `build`: Build system or dependencies (no version bump)
- `ci`: CI/CD configuration (no version bump)
- `chore`: Maintenance (no version bump)
- `revert`: Revert previous commit (patch version bump)

### Scopes

- `core`, `extractors`, `storage`, `services`, `tools`, `prompts`
- `config`, `cli`, `tests`, `deps`, `release`
- `no-release` - prevents triggering a release

### Breaking Changes

Add `!` after type/scope or `BREAKING CHANGE:` in footer for major version bump:

```bash
git commit -m "feat(storage)!: replace StateDB with port interface

BREAKING CHANGE: Services must now depend on StatePort protocol"
```

### Examples

```bash
# Feature
git commit -m "feat(extractors): add Swift language support"

# Bug fix
git commit -m "fix(storage): handle null entity IDs correctly"

# Documentation
git commit -m "docs: update architecture guide with Neo4j patterns"

# Refactoring
git commit -m "refactor(services): extract pipeline into separate modules"

# Chore (no release)
git commit -m "chore(deps): update tree-sitter to 0.24.1"
```

## Architecture Guidelines

### SOLID Principles

MRCIS follows SOLID principles strictly. See `CLAUDE.md` for detailed guidelines.

**Quick rules:**

1. **SRP**: Each module has one reason to change
2. **OCP**: Extend via new classes, don't modify existing ones
3. **LSP**: All port implementations must be interchangeable
4. **ISP**: Depend on the narrowest port you need
5. **DIP**: Depend on ports, not concrete storage classes

### Common Changes

- **Adding a language extractor**: Use skill `mrcis-add-extractor` (see `.claude/skills/`)
- **Adding a storage backend**: Use skill `mrcis-add-storage-backend`
- **General architecture**: Use skill `mrcis-architecture-guide`

### Code Style

- Line length: 100 characters
- Type hints required on all public functions
- All I/O operations must be async
- All imports at module level (except TYPE_CHECKING blocks)
- Follow existing patterns in the codebase

## Pull Request Process

1. **Ensure all checks pass**
   - CI pipeline must be green
   - All tests passing
   - No type errors
   - Code formatted and linted

2. **Update documentation**
   - Update `CLAUDE.md` if architecture changes
   - Add docstrings to new classes/functions
   - Update relevant guides

3. **Write descriptive PR description**
   - Explain the motivation for the change
   - Describe what was changed
   - Note any breaking changes

4. **Request review**
   - Wait for maintainer review
   - Address feedback
   - Keep commits clean (squash if requested)

## Release Process

Releases are automated via semantic-release:

1. **Commits to `main`** trigger semantic-release
2. **Version determined** by conventional commit types
3. **CHANGELOG.md generated** automatically
4. **GitHub release created** with assets
5. **PyPI package published** (if version bumped)

You don't need to manually bump versions or create releases.

## Questions?

- Read `CLAUDE.md` for architecture details
- Check `.claude/skills/` for specific task guides
- Open an issue for questions or discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
