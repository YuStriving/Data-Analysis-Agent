# Scripts Agent Contract

## 1. Scope

`scripts` contains helper scripts for development, CI, and seed workflows.

This directory is responsible for:

- local startup helpers
- verification helpers
- seed and bootstrap helpers

This directory is not responsible for:

- core business logic
- hidden deployment logic that is undocumented elsewhere
- replacing proper application code

## 2. Subdirectory Responsibilities

- `dev/`
  - local environment startup and developer shortcuts
- `ci/`
  - lint, test, build, and verification commands
- `seed/`
  - demo data and initial bootstrap actions

## 3. Development Rules

- scripts should be idempotent whenever possible
- scripts should print clear progress and failure messages
- scripts should avoid destructive actions by default
- scripts should be safe for repeated local execution
- prefer PowerShell in this repository unless there is a strong reason otherwise

## 4. Security Rules

- never hardcode secrets in scripts
- never run destructive database or filesystem actions implicitly
- any cleanup script must make targets explicit
- seed scripts must use demo-safe data only

## 5. Usage Rules

- `dev/` scripts may assume local developer context
- `ci/` scripts must be non-interactive
- `seed/` scripts must document what records they create
- `ci/verify.ps1` is the local aggregate verification entrypoint
- `ci/verify.ps1` runs frontend npm build, Java Maven tests, and Python lint/tests unless explicitly skipped

## 6. Self-Evolution Rules

This local contract must evolve whenever the repository automation flow becomes more concrete.

Automatic updates are required when:

- new standard startup scripts are added
- CI verification steps become stable
- seed flows change materially
- naming conventions for helper scripts stabilize

Automatic updates are not allowed for:

- adding hidden destructive behavior
- embedding credentials
- replacing documented app behavior with opaque scripts

## 7. Non-Goals

- no long-term business workflows
- no application-layer permission engine
- no hidden production deploy logic
