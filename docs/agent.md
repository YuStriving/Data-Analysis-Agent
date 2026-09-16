# Docs Agent Contract

## 1. Scope

`docs` stores architecture, protocol, and implementation documentation for the repository.

This directory is responsible for:

- architecture docs
- module responsibility docs
- protocol contracts
- ADR-style technical decisions
- development and integration guides

This directory is not responsible for:

- runtime business logic
- source-of-truth configuration values
- executable code used in production

## 2. Documentation Rules

- docs must match the current repository structure
- docs must be updated when architecture or contracts change
- avoid vague statements without ownership or boundaries
- prefer explicit responsibilities, inputs, outputs, and constraints
- use diagrams only when they improve understanding

## 3. Technical Writing Rules

- use precise names for modules and packages
- document permission boundaries clearly
- document which backend owns which responsibility
- when describing protocols, include field expectations
- when describing stack choices, explain why they are used

## 4. Security Rules

- do not place real secrets in docs
- do not leak internal-only credentials or endpoints
- do not document bypass flows that violate the permission model

## 5. Recommended Document Types

- architecture overview
- API contract
- SSE event contract
- database design
- prompt and context design
- MCP integration notes
- deployment notes
- development workflow notes such as CI verification behavior

## 6. Self-Evolution Rules

This local contract must evolve whenever repository reality changes.

Automatic updates are required when:

- code structure changes
- ownership boundaries change within approved limits
- event contracts or API contracts change
- stack baselines change
- new stable conventions become part of development practice

Automatic updates are not allowed for:

- keeping stale diagrams after a refactor
- documenting unapproved architecture changes as if they were accepted
- weakening security descriptions to match accidental code shortcuts

## 7. Non-Goals

- no placeholder docs that contradict code
- no stale diagrams kept after refactors
- no undocumented large architectural changes
