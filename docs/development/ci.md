# GitHub CI

## Scope

The repository uses GitHub Actions for module-level continuous integration.

The current CI workflow is defined in `.github/workflows/ci.yml` and runs on
`push` and `pull_request`.

## Jobs

- `frontend-web`
  - Node.js 22
  - `npm ci`
  - `npm run build`
  - npm dependency cache based on `frontend-web/package-lock.json`
  - timeout: 15 minutes

- `backend-java`
  - Java 21
  - `mvn -B test`
  - Maven dependency cache
  - timeout: 20 minutes

- `backend-agent`
  - Python 3.12
  - `python -m pip install -e ".[dev]"`
  - `ruff check .`
  - `pytest`
  - pip dependency cache based on `backend-agent/pyproject.toml`
  - timeout: 20 minutes

## Local Verification

Use `scripts/ci/verify.ps1` from the repository root to run the same core
verification steps locally.

```powershell
.\scripts\ci\verify.ps1
```

Module checks can be skipped when the change is intentionally scoped:

```powershell
.\scripts\ci\verify.ps1 -SkipFrontend
.\scripts\ci\verify.ps1 -SkipJava
.\scripts\ci\verify.ps1 -SkipPython
```

## Design Notes

- CI jobs are split by module so failures identify the affected area clearly.
- Each job has an explicit timeout to avoid stuck runners.
- Dependency caches are module-specific and use the module lock or project file.
- The workflow uses read-only repository permissions.
- Repeated pushes to the same ref cancel older in-progress CI runs.
- Path-based job skipping is intentionally deferred until CI runtime becomes a
  real bottleneck.

## Pull Request Template

The repository uses `.github/pull_request_template.md` as the default GitHub PR
template.

PR titles should follow the same Conventional Commits style used by commits:

```text
<type>(<scope>): <subject>
```

The PR body should describe the change content, change type, validation result,
impact scope, documentation sync, risk notes, and linked issue.
