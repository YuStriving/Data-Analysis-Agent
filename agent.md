# Global Agent Governance

## 1. Purpose

This file is the highest-priority repository contract for the Data Analysis Agent project.

All local `agent.md` files must inherit from this file.

If a local `agent.md` conflicts with this file:

- this file wins
- the conflicting local file must be updated in the same workstream

This repository is building a:

- dual-backend data analysis agent platform
- Java monolith for business authority
- Python agent runtime for orchestration and intelligence
- SSE-based streaming user experience

## 2. Global Objectives

The repository should optimize for:

1. correctness
2. safety
3. traceability
4. maintainability
5. stable iteration speed
6. evolvable architecture

The project must not optimize for flashy autonomy at the cost of control.

## 3. Global Architecture Baseline

This repository uses the following fixed baseline:

- `frontend-web`
  - Next.js frontend and SSE consumer
- `backend-java`
  - single Spring Boot monolith
  - source of truth for auth, permissions, task entry, audit, SSE delivery
- `backend-agent`
  - Python LangGraph runtime
  - source of truth for orchestration, tools, memory, MCP, prompts, context, guardrails, evals
- `infra`
  - infrastructure bootstrap and deployment config
- `scripts`
  - developer, CI, and seed helpers
- `docs`
  - architecture and protocol documentation

The system is not a Java microservice architecture.

## 4. Global Technical Stack Baseline

Unless explicitly approved otherwise, the repository standard is:

- `Java 21`
- `Spring Boot 3.5.16`
- `Spring Security`
- `Python 3.12`
- `FastAPI`
- `LangGraph`
- `MySQL 8.4`
- `Redis`
- `MongoDB`
- `Kafka`
- `Next.js`
- `TypeScript`
- `Tailwind CSS`
- `ECharts`

Version policy:

- prefer stable releases over preview releases
- prefer LTS or stable-maintenance lines when available
- do not upgrade major versions automatically
- patch and minor upgrades may be proposed when they improve stability or security

`Spring Boot 3.5.16` is used here for stability. As of August 27, 2026, Spring’s official system requirements page lists `3.5.16` as the stable `3.5.x` line alongside newer `4.x` branches. Source: [Spring Boot System Requirements](https://docs.spring.io/spring-boot/system-requirements.html)

## 5. Global Ownership Rules

### 5.1 Java ownership

`backend-java` owns:

- authentication
- authorization
- tenant isolation
- dataset access control
- task creation entry
- audit logging
- external SSE connections

### 5.2 Python ownership

`backend-agent` owns:

- LangGraph runtime
- tool invocation
- SQL planning and validation orchestration
- memory reads and writes within granted scope
- MCP integration
- prompt and context engineering
- evaluation and runtime guardrails

### 5.3 Frontend ownership

`frontend-web` owns:

- display
- interaction
- task progress visualization
- chart rendering
- approval interaction

## 6. Permission and Safety Model

This repository follows a strict least-privilege model.

Rules:

- Java is the final authority for auth and authorization
- Python must never invent or expand permissions
- frontend permissions are display hints only
- all SQL must remain read-only
- all sensitive operations must be auditable
- all user-visible conclusions must be evidence-backed

Forbidden actions:

- write SQL in analysis flows
- bypassing Java permission checks
- leaking secrets into prompts
- exposing internal Python endpoints directly to untrusted browsers
- silently suppressing security or guardrail failures

## 7. Agent Runtime Rules

The agent is required to:

- understand data questions
- inspect schema and metadata
- assemble scoped context
- generate safe analysis plans
- validate and execute read-only SQL
- run Python post-processing when needed
- generate chart-ready outputs
- stream progress through stable events
- support human review and task resume

The agent is not allowed to:

- modify business data
- fabricate metrics
- expose hidden chain-of-thought
- bypass tool validation
- persist memory outside tenant and user boundaries

## 8. Global Output Contract

All final analysis outputs must be structured and traceable.

Minimum output expectations:

- task id
- trace id
- status
- summary
- SQL used
- datasets used
- warnings
- chart payload when applicable
- evidence-backed insights

Rules:

- no free-form untyped result payloads
- no end-user exposure of raw hidden reasoning
- low-confidence answers must say so explicitly

## 9. SSE Contract

Browser-facing streaming uses `SSE`.

Rules:

- Java owns the external SSE connection
- Python emits internal progress events only
- SSE payloads must be stable JSON
- every event must include `task_id`, `trace_id`, `event_type`, and `timestamp`
- terminal events must be `final_answer` or `task_failed`
- long-running tasks must emit heartbeat events

Recommended event types:

- `task_created`
- `task_queued`
- `task_started`
- `context_ready`
- `plan_ready`
- `tool_started`
- `tool_succeeded`
- `tool_failed`
- `sql_generated`
- `sql_approved`
- `human_review_required`
- `chart_ready`
- `partial_answer`
- `final_answer`
- `task_failed`
- `heartbeat`

## 10. Prompt, Context, Memory, and MCP Rules

### 10.1 Prompt rules

- prompts must be versioned
- prompts must live outside business code where practical
- prompt updates must be regression-tested
- refusal behavior for unsafe requests must be explicit

### 10.2 Context rules

- context must be concise, scoped, and relevant
- context must not include unauthorized tables or columns
- uncertain context must be labeled

### 10.3 Memory rules

- Redis stores only the pending flush queue and hot context for active sessions
- MongoDB is the durable store for memory turns and checkpoints
- memory must be scoped by tenant and user and include source and timestamp metadata
- flush is idempotent, and Redis pending items are cleared only after MongoDB commit
- snapshots are captured at node level, and restore requires manual confirmation
- alerts are written to local daily log files only

### 10.4 MCP rules

- only approved MCP servers may be used
- MCP outputs must be normalized before entering prompts
- MCP failure handling must be explicit

## 11. Global Package and Module Boundaries

### 11.1 Java monolith

`backend-java` should remain isolated by package:

- `common/*`
- `modules/gateway`
- `modules/auth`
- `modules/dataset`
- `modules/job`
- `modules/audit`

Preferred layering inside each module:

- `controller`
- `service`
- `service/impl`
- `repository`
- `domain`
- `dto`
- `config`

Service-layer contract:

- service interfaces must be declared under the module `service` package
- concrete service implementations must be placed under `service/impl`
- controllers and other collaborating classes should depend on service interfaces, not implementation classes
- when a service also satisfies a shared cross-module contract, the implementation class may implement both the module service interface and the shared contract interface

Utility-class rule:

- when a function is reused or is clearly cross-class helper logic, create a dedicated utility package such as `util` under the relevant module
- utility classes must follow normal code standards: single responsibility, explicit naming, stateless behavior where possible, and clear visibility boundaries
- utility classes must remain highly readable and low-coupling; helper logic should be easy to scan, avoid hidden side effects, and should not pull unrelated module dependencies into a shared helper
- module-local utility code should stay inside that module; only cross-module infrastructure-style helpers may move to `common/*`
- do not create vague catch-all utility classes when the behavior belongs in `service`, `domain`, `repository`, or `config`

### 11.2 Python runtime

`backend-agent` follows four layers under `src/agent_backend/`:

- `api`
  - HTTP and Kafka entry adapters
- `orchestration`
  - LangGraph graph, state, node checkpoints, and manual resume logic
- `capabilities`
  - reusable `agent_runtime` services and concrete agents
- `foundation`
  - typed contracts and Redis, MongoDB, MySQL, and file data source adapters

`capabilities/agent_runtime` owns context engineering, prompt engineering,
tool calling, memory service, guardrails, observability, and evals.
`capabilities/data_analysis` owns the current analysis agent and its SQL,
Python, and chart tools.

## 12. Self-Evolution Protocol

All `agent.md` files in this repository are living contracts and must evolve with the codebase.

### 12.1 Automatic evolution goal

Whenever repository structure, stack, ownership, or stable conventions change, the relevant local `agent.md` files must be updated in the same change set.

This is the required behavior for any agent operating in this repository.

### 12.2 Allowed automatic updates

An agent may automatically update the relevant `agent.md` files when any of the following occurs:

- a module is added, removed, renamed, or moved
- a package boundary changes
- a stable development convention is introduced and already reflected in code
- a new approved dependency becomes part of the module baseline
- an API, SSE, or event contract changes
- a permission boundary becomes stricter
- a new guardrail or evaluation rule becomes required
- a prompt, context, memory, or MCP workflow becomes a standard part of the module

### 12.3 Restricted automatic updates

An agent must not automatically change the following without explicit user approval:

- the global architecture style
- the ownership boundary between Java and Python
- the choice to allow write access to production-style data
- the security model becoming weaker
- replacement of the primary framework stack
- major-version upgrades across core frameworks

### 12.4 Evolution workflow

When making changes, the acting agent must:

1. detect whether the change impacts scope, stack, boundaries, permissions, or conventions
2. identify which local `agent.md` files are affected
3. update the affected files in the same change set
4. keep the local file aligned with the actual code and directory structure
5. preserve stricter existing rules unless explicitly relaxed by the user

### 12.5 Progress-driven updates

Local `agent.md` files should evolve from scaffold-level guidance to implementation-level guidance as the project matures.

Examples:

- once `controller / service / repository / dto` appears in Java modules, the local contract should mention that layering
- once SSE DTOs are stabilized, the frontend and Java contracts should document those event types and field rules
- once MCP servers are actually added, the Python contract should document which categories are approved
- once CI checks are added, `scripts/agent.md` and `docs/agent.md` should reflect the real verification flow

### 12.6 Drift policy

If code and local `agent.md` diverge:

- code is not automatically trusted
- documentation is not automatically trusted
- the acting agent must reconcile both before claiming the change is complete

## 13. Documentation Maintenance Policy

Whenever one of the following changes, the related `agent.md` and architecture docs must be updated:

- framework version baseline
- package or module boundaries
- security model
- event model
- prompt or context architecture
- memory strategy
- MCP strategy

Large architectural changes should also update `docs/`.

## 14. Development Quality Rules

All implementation work should prefer:

- typed interfaces
- explicit DTOs and schemas
- module isolation
- idempotent scripts where possible
- non-interactive CI flows
- structured logs and metrics
- tests for key safety and contract behavior

Avoid:

- giant catch-all utility packages
- vague `Utils` dumping grounds; if helper logic is needed, place it in a clearly named utility class under a dedicated utility package
- hidden implicit behavior
- undocumented permission shortcuts
- coupling frontend directly to Python internals
- injecting module service implementation classes directly when a stable service interface should exist

## 15. Git and GitHub Workflow Rules

This repository follows a controlled Git and GitHub workflow.

### 15.1 Branch rules

- `main` is the default integration branch
- do not develop large features directly on `main`
- create a feature branch for non-trivial work
- recommended branch prefixes:
  - `feat/`
  - `fix/`
  - `refactor/`
  - `docs/`
  - `chore/`
  - `test/`

Recommended branch examples:

- `feat/sse-streaming`
- `fix/sql-guard-timeout`
- `refactor/java-module-layering`

### 15.2 Commit rules

Commits should use a Conventional Commits style.

Recommended commit types:

- `feat`
- `fix`
- `refactor`
- `docs`
- `chore`
- `test`
- `build`
- `ci`

Commit format:

```text
type: short summary
type(scope): short summary
```

Examples:

- `feat: add task streaming endpoint`
- `fix(agent): reject unsafe SQL tokens`
- `docs: update architecture baseline`

Commit rules:

- one commit should represent one coherent change set
- do not mix unrelated refactors and feature work in the same commit
- when code changes require `agent.md` or `docs` updates, include them in the same commit
- commit messages must be concise and explain intent, not just implementation detail

### 15.3 Staging rules

- stage only files that belong to the current change
- do not silently include unrelated local changes
- prefer explicit staging when the working tree contains mixed work
- avoid large formatting-only commits unless they were explicitly intended

### 15.4 Push rules

- push feature work to a branch first unless the repository state clearly allows direct `main` updates
- do not force-push shared branches unless explicitly approved
- do not rewrite published history on `main`
- before push, verify that required docs and `agent.md` updates are included

### 15.5 Pull request rules

- prefer pull requests for non-trivial changes
- default to draft pull requests unless the work is clearly ready
- PR title should summarize the user-visible or architecture-visible change
- PR description should cover:
  - what changed
  - why it changed
  - impact
  - validation performed

### 15.6 Validation rules before commit or push

Before publishing code, the acting agent should run the most relevant checks available for the affected modules.

Typical expectations:

- frontend changes:
  - type-check
  - build or lint when available
- Java changes:
  - compile or test relevant modules
- Python changes:
  - unit or integration tests relevant to the change

If checks are not run, the reason must be stated explicitly.

### 15.7 GitHub repository hygiene

- keep `README.md`, root `agent.md`, and affected local `agent.md` files aligned with the current codebase
- do not leave architecture migrations half-reflected between code and docs
- do not merge code that weakens the permission model without explicit approval
- treat GitHub history as part of the project documentation

### 15.8 Automatic evolution of workflow rules

These GitHub workflow rules may be automatically updated when:

- the repository adopts a stable branching model
- CI requirements become concrete
- PR templates or release rules become part of normal development
- commit conventions are tightened by repeated team practice

These workflow rules must not be automatically changed when the change would:

- weaken review discipline
- allow direct unsafe pushes to protected branches
- relax documentation-update requirements

## 16. Non-Goals

The MVP should not attempt:

- unrestricted cross-system federation
- arbitrary code execution without sandboxing
- fully autonomous BI decisions without review
- automatic write-back to operational databases
- architecture churn without clear value

## 17. Definition of Done

A meaningful MVP is done when the repository can:

1. authenticate and authorize users through Java
2. register or upload datasets
3. accept a natural-language analysis task
4. generate safe read-only SQL
5. execute analysis and produce a chart
6. stream progress through SSE
7. persist task, trace, and audit data
8. support review and retry
9. support resumable agent execution
10. keep `agent.md` contracts aligned with the implemented system
