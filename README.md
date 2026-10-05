# Agent Data Platform Monorepo

This repository contains a dual-backend data analysis agent platform:

- `frontend-web`: Vue 3 / Vite UI for dataset upload, task views, and chart rendering
- `backend-java`: single Spring Boot monolith with isolated module packages for auth, dataset, job, audit, and gateway concerns
- `backend-agent`: FastAPI and LangGraph runtime for agent execution, tools, memory, MCP, and guardrails
- `infra`: local infrastructure bootstrap files
- `docs`: architecture, human/AI workflow, specifications, plans, and verification records
- module docs: local implementation details and runtime contracts

## Project and module guidance

- [Repository agent guidance](AGENTS.md)
- [Documentation index](docs/README.md)
- [Architecture map](docs/architecture/README.md)
- [Overall design constraints](docs/DESIGN.md)
- [Detailed design index](docs/design-docs/index.md)
- [Human and AI execution workflow](docs/WORKFLOW.md)
- [Agent backend](backend-agent/README.md)
- [Java backend](backend-java/README.md)
- [Frontend](frontend-web/README.md)
- [Development specifications](docs/spec/README.md)
- [Task planning workflow](docs/exec-plans/README.md)
- [Quality Skills](skills/quality/README.md)

## Development notes

- Java owns authentication, authorization, audit, task entry, and external SSE connections.
- Python owns agent orchestration and internal execution events.
- All SQL execution is read-only by policy.
