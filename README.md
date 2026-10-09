# Agent Data Platform Monorepo

This repository contains a dual-backend data analysis agent platform:

- `frontend-web`: Vue 3 / Vite UI for dataset upload, task views, and chart rendering
- `backend-java`: single Spring Boot monolith with isolated module packages for auth, dataset, job, audit, and gateway concerns
- `backend-agent`: FastAPI and LangGraph runtime for agent execution, tools, memory, MCP, and guardrails
- `infra`: local infrastructure bootstrap files
- `docs`: current MVP status, architecture decisions, and Agent setup notes
- module docs: local implementation details and runtime contracts

## Project and module guidance

- [Repository agent guidance](AGENTS.md)
- [Documentation index](docs/README.md)
- [MVP project status](docs/PROJECT-STATUS.md)
- [MVP collaboration decision](docs/adr/0001-mvp-agent-collaboration.md)
- [GitHub issue tracker setup](docs/agents/issue-tracker.md)
- [Domain documentation rules](docs/agents/domain.md)
- [Triage label mapping](docs/agents/triage-labels.md)
- [Agent backend](backend-agent/README.md)
- [Java backend](backend-java/README.md)
- [Frontend](frontend-web/README.md)
- [Infrastructure](infra/README.md)
- [Scripts](scripts/README.md)
- [Repository Skills](skills/README.md)
- [Quality Skills](skills/quality/README.md)

## Development notes

- Java owns authentication, authorization, audit, task entry, and external SSE connections.
- Python owns agent orchestration and internal execution events.
- All SQL execution is read-only by policy.
