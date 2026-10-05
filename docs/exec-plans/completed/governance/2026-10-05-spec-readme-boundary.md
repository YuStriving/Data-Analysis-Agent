# Clarify the Spec README boundary

- Date: 2026-10-05
- Category: governance
- Status: done
- Authorization: user-approved plan to clarify `docs/spec/README.md`
- Spec: pure documentation governance; no business Spec required

## Goal

Make `docs/spec/README.md` the authority for Spec-specific governance. Keep task workflow, Plan lifecycle, test case details, and template field guidance in their respective authoritative documents.

## Scope

- Simplify `docs/spec/README.md` to cover Spec applicability, confirmation, changes and supersession, acceptance criteria and test references, and use of the Spec template.
- Link general task classification and readiness gates to `docs/WORKFLOW.md`, Plan lifecycle to `docs/exec-plans/README.md`, and test cases and evidence to `docs/tests/README.md`.
- Update inbound links that targeted the former applicability heading.
- Label the existing `docs/spec/tool-calling/tasks.md` as a historical implementation record in the README, template, and Spec. Do not move or rewrite that record.
- Add an acceptance record under `docs/tests/` and register it in the test index.

## Out of scope

- Changing behavior requirements or the existing tool-calling implementation history.
- Adding `tasks.md` as a new plan format, migrating documents, or changing unrelated AGENTS files.

## Steps

1. Record acceptance checks in `docs/tests/spec-readme-boundary.md` before editing the governed documents.
2. Rewrite the Spec README around Spec-only governance and authoritative links.
3. Update the template's implementation-plan wording and the tool-calling Spec's link label to identify `tasks.md` as historical.
4. Register the acceptance record and record actual validation results.
5. Run `python scripts/ci/check-docs.py`, inspect related links, run `git diff --check`, and archive this plan after passing checks.

## Acceptance

- The README does not restate generic task classifications, Plan lifecycle, detailed test formats, or the template's field list.
- Spec applicability, confirmation/change/supersession, acceptance criteria/test references, and template use remain explicit.
- Existing `tasks.md` is called historical and is not presented as a new planning option.
- The new test record is linked from `docs/tests/README.md`; repository document and whitespace checks pass.

## Validation record

- Manual review: Spec applicability criteria retained; general workflow, Plan lifecycle, test details, and template field explanations route to their respective authority.
- Ruling: Update the adjacent `core-beliefs.md` sentence that said small tasks never skip Plans; it conflicted with the current Workflow and was in the same Spec applicability navigation area. Replace the duplicated policy with links to the Workflow and Plan authorities. Cost if wrong: the principles page would continue directing readers to an outdated task gate.
- `python scripts/ci/check-docs.py`: passed (129 Markdown files, 345 local links, 0 errors).
- `git diff --check`: exit code 0; Git emitted LF/CRLF conversion notices for the existing dirty worktree. Targeted trailing-whitespace check on touched Markdown passed.
- Final re-run after recording results: `python scripts/ci/check-docs.py` passed after final navigation edits (129 Markdown files, 345 local links, 0 errors); `git diff --check` exited 0.
- Final read-only review: no unresolved findings. `docs/spec/tool-calling/tasks.md` was not modified by this task; it is untracked in the worktree, so no Git baseline was available for an independent before/after comparison.
