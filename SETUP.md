# MRCIS Setup & Release Pipeline Guide

## Quick Setup Checklist

### Local Development Setup

```bash
# 1. Navigate to project
cd mrcis

# 2. Install dependencies
uv sync --dev

# 3. Install pre-commit hooks
mise run pre-commit-install
# Or directly:
# uv run pre-commit install --install-hooks
# uv run pre-commit install --hook-type commit-msg

# 4. Verify setup
mise run test-fast
mise run check

# 5. Make a test commit to verify hooks
git add .
git commit -m "test(setup): verify pre-commit hooks"
```

### GitHub Repository Setup

#### 1. Update Repository URLs

Edit these files with your actual GitHub repository URL:

- `.releaserc.json` - Update `repositoryUrl` field
- `.github/workflows/release.yml` - Update `if: github.repository_owner == 'YOUR_ORG'`

#### 2. Configure Repository Secrets

Go to GitHub Settings → Secrets and variables → Actions:

**Required for PyPI Publishing:**
- `PYPI_API_TOKEN` - Generate at https://pypi.org/manage/account/token/

**Automatically provided:**
- `GITHUB_TOKEN` - No setup needed

#### 3. Set Branch Protection Rules

For `main` branch (Settings → Branches → Add rule):

- [x] Require a pull request before merging
- [x] Require status checks to pass before merging:
  - `Test Python 3.11 on ubuntu-latest`
  - `Test Python 3.11 on macos-latest`
  - `Pre-commit checks`
  - `Lint commit messages` (for PRs only)
- [x] Require conversation resolution before merging
- [ ] Require linear history (optional but recommended)

## Pre-commit Hooks

### What They Do

On every commit, the following runs automatically:

1. **Ruff** - Linting with auto-fix
2. **Ruff Format** - Code formatting
3. **Mypy** - Type checking on `src/`
4. **Pytest** - Fast tests (excludes slow/integration)
5. **Conventional Commits** - Validates commit message format
6. **Standard checks** - Trailing whitespace, YAML/TOML syntax, etc.

### Manual Execution

```bash
# Run all hooks on all files
mise run pre-commit-run

# Run on staged files only
git add .
uv run pre-commit run

# Update hooks to latest versions
mise run pre-commit-update

# Skip hooks (not recommended)
git commit --no-verify
```

### Troubleshooting

**Hook fails but fix looks correct:**
- Re-stage fixed files: `git add -u`
- Commit again

**Type errors in mypy:**
- Fix errors in source code
- Or add `# type: ignore` comment with explanation

**Tests fail:**
- Fix the failing test
- Or temporarily skip (not recommended): `git commit --no-verify`

## Semantic Release Workflow

### How It Works

1. **Push to `main`** triggers GitHub Actions
2. **Analyze commits** since last release
3. **Determine version** based on commit types:
   - `fix:` → Patch (0.0.X)
   - `feat:` → Minor (0.X.0)
   - `BREAKING CHANGE:` → Major (X.0.0)
4. **Generate CHANGELOG.md** from commits
5. **Update version** in `pyproject.toml`
6. **Create GitHub release** with tag
7. **Publish to PyPI** (if `PYPI_API_TOKEN` set)

### Commit Message Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature → Minor bump
- `fix`: Bug fix → Patch bump
- `docs`: Documentation → Patch bump
- `refactor`: Code refactoring → Patch bump
- `perf`: Performance → Patch bump
- `test`: Tests only → No bump
- `chore`: Maintenance → No bump
- `ci`: CI/CD → No bump

**Scopes:**
- `core`, `extractors`, `storage`, `services`, `tools`, `prompts`
- `config`, `cli`, `tests`, `deps`, `release`
- `no-release` - prevents release

**Breaking Changes:**

Add `!` after type or `BREAKING CHANGE:` in footer for major bump:

```bash
git commit -m "feat(storage)!: change RelationGraphPort API

BREAKING CHANGE: add_entity() now returns UUID instead of string"
```

### Examples

```bash
# Feature - triggers 0.X.0 release
git commit -m "feat(extractors): add Swift language support"

# Bug fix - triggers 0.0.X release
git commit -m "fix(storage): handle null entity IDs"

# Documentation - triggers 0.0.X release
git commit -m "docs: update CLAUDE.md with Neo4j patterns"

# Chore - no release triggered
git commit -m "chore(deps): update tree-sitter to 0.24.1"

# Breaking change - triggers X.0.0 release
git commit -m "feat(storage)!: replace StateDB with ports

BREAKING CHANGE: All services must use StatePort instead of StateDB"
```

### First Release

To trigger the first release:

```bash
# Create initial tag manually (one-time only)
git tag -a v0.1.0 -m "Initial release"
git push origin v0.1.0

# Future releases will be automatic
```

### Preventing Accidental Releases

Use `no-release` scope or `[skip ci]` in commit message:

```bash
git commit -m "chore(no-release): update internal tooling"
git commit -m "docs: update README [skip ci]"
```

## CI/CD Pipeline

### GitHub Actions Workflows

#### `.github/workflows/ci.yml`

Runs on every push and PR:

| Job | Runs On | Actions |
|-----|---------|---------|
| **Test** | Ubuntu/macOS × Python 3.11/3.12 | Lint, format, typecheck, tests, coverage |
| **Lint Commits** | PRs only | Validates conventional commit format |
| **Pre-commit** | Ubuntu × Python 3.11 | Runs all pre-commit hooks |

#### `.github/workflows/release.yml`

Runs on push to `main`:

| Job | Trigger | Actions |
|-----|---------|---------|
| **Semantic Release** | Every push | Analyze commits, bump version, create release |
| **Build & Publish** | After release created | Build wheel, publish to PyPI |

### Monitoring

**View workflows:**
- Go to repository → Actions tab
- Click on workflow run to see logs

**Common issues:**

| Issue | Solution |
|-------|----------|
| Tests fail in CI but not locally | Run `mise run test` locally, check test isolation |
| Type errors in CI but not locally | Run `uv run mypy src/` exactly as CI does |
| Release not triggered | Check commit format, ensure type triggers release |
| PyPI publish fails | Verify `PYPI_API_TOKEN` is set correctly |

## Local Testing of Release

To test the release process locally (requires Node.js):

```bash
# Install semantic-release
npm install -g semantic-release @semantic-release/changelog \
  @semantic-release/git @semantic-release/github

# Dry-run (no actual release)
npx semantic-release --dry-run
```

## Version Management

### Current Version

Check current version:

```bash
grep 'version =' mrcis/pyproject.toml
```

### Version History

```bash
# List all releases
git tag -l

# View CHANGELOG
cat CHANGELOG.md
```

### Manual Version Override

If you need to manually set version (not recommended):

```bash
cd mrcis
# Edit pyproject.toml
sed -i 's/version = ".*"/version = "0.2.0"/' pyproject.toml

# Commit and tag
git add pyproject.toml
git commit -m "chore(release): manual version bump to 0.2.0"
git tag -a v0.2.0 -m "Release 0.2.0"
git push origin main --tags
```

## Publishing to PyPI

### First-Time Setup

1. Create PyPI account: https://pypi.org/account/register/
2. Verify email
3. Enable 2FA (recommended)
4. Create API token: https://pypi.org/manage/account/token/
5. Add token as `PYPI_API_TOKEN` in GitHub secrets

### Manual Publishing (if needed)

```bash
cd mrcis

# Build package
uv build

# Check package
uv run twine check dist/*

# Upload to Test PyPI (optional)
uv publish --repository testpypi

# Upload to PyPI
uv publish
```

### Verify Published Package

```bash
# Install from PyPI
pip install mrcis

# Check version
python -c "import mrcis; print(mrcis.__version__)"
```

## Rollback

If a release has issues:

1. **Revert the release commit:**
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **Delete the tag locally and remotely:**
   ```bash
   git tag -d v0.2.0
   git push origin :refs/tags/v0.2.0
   ```

3. **Delete the GitHub release:**
   - Go to Releases → Click release → Delete release

4. **Yank from PyPI** (keeps version but marks as broken):
   - Go to https://pypi.org/project/mrcis/
   - Manage → Options → Yank

## Resources

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [semantic-release docs](https://semantic-release.gitbook.io/)
- [GitHub Actions docs](https://docs.github.com/en/actions)
- [uv docs](https://docs.astral.sh/uv/)
- [pre-commit docs](https://pre-commit.com/)
