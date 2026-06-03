# CI Fix for PR #683

## Issues Addressed

### 1. Markdown Linting (MD032)
- **File:** `docs/runbooks/dependency-audit-allowlists.md`
- **Error:** Lists not surrounded by blank lines (MD032 violation)
- **Fix:** Added blank lines before lists at lines 69 and 80

### 2. Docker BuildX Cache Incompatibility
- **File:** `.github/workflows/ci.yml`
- **Error:** "Cache export is not supported for the docker driver"
- **Root Cause:** When using `load: true` with docker/build-push-action, the docker driver doesn't support GHA cache export (`cache-from: type=gha` and `cache-to: type=gha,mode=max`)
- **Fix:** Removed cache-from and cache-to options from base image build job (lines 512-513)

## Verification
- ✅ 199 pytest tests pass locally
- ✅ All pre-commit checks pass locally
- ✅ Docker compose cap_drop validation passes
- ✅ Markdown linting passes
- ✅ Both commits properly GPG-signed

## Status
Both fixes have been committed to branch `dependabot/docker/bases/debian-0104b33` and pushed to remote. The CI checks shown as failing are from runs executed before these commits were applied (timestamps 2026-05-30 and 2026-06-01T02:08/07:31). New CI runs will execute with the fixed code automatically.
