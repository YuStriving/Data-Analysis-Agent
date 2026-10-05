"""Check Markdown navigation and declared complete catalogs without dependencies or writes."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.parse import unquote


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "AGENTS.md",
    "README.md",
    "docs/README.md",
    "docs/architecture/README.md",
    "docs/DESIGN.md",
    "docs/design-docs/index.md",
    "docs/design-docs/core-beliefs.md",
    "docs/WORKFLOW.md",
    "docs/spec/README.md",
    "docs/spec/template.md",
    "docs/exec-plans/README.md",
)
LINK = re.compile(r"\[[^\]\n]+\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
PLAN_STATUS = re.compile(r"^\s*-\s*(?:状态|Status)\s*[：:]\s*(\S+)\s*$", re.IGNORECASE)
PLAN_STATUSES = {"draft", "ready", "in_progress", "verify", "done"}
EMPTY_SKILLS = re.compile(r"暂无(?:\s*归档)?\s*Skills?\b", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogRule:
    name: str
    source: str
    include: str
    exclude: tuple[str, ...]
    index: str


def catalog_members(root: Path, documents: set[Path], rule: CatalogRule) -> set[Path]:
    source = root / rule.source
    members = set()
    for document in documents:
        if document.is_relative_to(source):
            name = document.relative_to(source).as_posix()
            if fnmatchcase(name, rule.include) and not any(fnmatchcase(name, pattern) for pattern in rule.exclude):
                members.add(document)
    return members


def is_escaped(line: str, position: int) -> bool:
    prefix = line[:position]
    return (len(prefix) - len(prefix.rstrip("\\"))) % 2 == 1


def local_targets(document: Path, lines: list[tuple[int, str]]) -> set[Path]:
    targets = set()
    for _, line in lines:
        for match in LINK.finditer(line):
            start = match.start()
            if is_escaped(line, start) or (start and line[start - 1] == "!" and not is_escaped(line, start - 1)):
                continue
            target = match[1].strip("<>")
            if not EXTERNAL.match(target) and not target.startswith("//"):
                path = unquote(target.partition("#")[0])
                targets.add((document.parent / path).resolve() if path else document.resolve())
    return targets


def check_catalog(root: Path, documents: set[Path], rule: CatalogRule,
                  lines: list[tuple[int, str]] | None = None) -> list[str]:
    index = root / rule.index
    if index not in documents:
        return [f"[{rule.name}] Missing index: {rule.index} (scope: {rule.source})"]
    targets = local_targets(index, list(visible_lines(index)) if lines is None else lines)
    return [f"[{rule.name}] Missing registration: {entry.relative_to(root).as_posix()} -> index {rule.index}; use inline [label](path)"
            for entry in sorted(catalog_members(root, documents, rule) - targets)]


def check_catalogs(root: Path, documents: set[Path]) -> list[str]:
    errors = []
    summary = root / "skills/README.md"
    if summary not in documents:
        errors.append("[skills-summary] Missing index: skills/README.md (scope: skills)")
    rows = []
    if summary in documents:
        for number, line in visible_lines(summary):
            if line.lstrip().startswith("|"):
                cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                if len(cells) >= 3:
                    rows.append((number, cells))
    categories = set()
    for document in documents:
        parts = document.relative_to(root).parts
        if parts[0] == "skills" and parts[-1] == "SKILL.md" and len(parts) != 4:
            errors.append(f"[skills-layout] Invalid Skill path: {document.relative_to(root).as_posix()}; expected skills/<category>/<skill>/SKILL.md")
        if parts[0] == "skills" and ((len(parts) == 3 and parts[-1] == "README.md")
                                     or (len(parts) >= 4 and parts[-1] == "SKILL.md")):
            categories.add(parts[1])
    for category in sorted(categories):
        scope = f"skills/{category}"
        index = f"{scope}/README.md"
        rule = CatalogRule("skills-category", scope, "*/SKILL.md", (), index)
        members = catalog_members(root, documents, rule)
        errors.extend(check_catalog(root, documents, rule))
        if members and root / index in documents:
            for number, line in visible_lines(root / index):
                if EMPTY_SKILLS.search(line):
                    errors.append(f"[skills-category] Nonempty scope {scope}: empty declaration at {index}:{number}")
        if summary not in documents:
            continue
        category_rows = [(number, cells[2]) for number, cells in rows
                         if (root / index).resolve() in local_targets(summary, [(number, cells[0])])]
        if not category_rows:
            errors.append(f"[skills-summary] Missing category row: {index} -> index skills/README.md")
        summary_rule = CatalogRule("skills-summary", scope, "*/SKILL.md", (), "skills/README.md")
        errors.extend(check_catalog(root, documents, summary_rule, category_rows))
        if members:
            for number, content in category_rows:
                if "暂无" in content:
                    errors.append(f"[skills-summary] Nonempty scope {scope}: empty declaration at skills/README.md:{number}")
    return errors


def check_plan_lifecycle(root: Path, documents: set[Path]) -> list[str]:
    """Keep Plan status consistent with its active/completed directory."""
    errors = []
    for document in sorted(documents):
        relative = document.relative_to(root)
        parts = relative.parts
        if len(parts) < 3 or parts[:2] != ("docs", "exec-plans") or parts[2] not in {"active", "completed"}:
            continue
        if document.name.lower() == "readme.md":
            continue
        location = relative.as_posix()
        status_lines = [match[1].lower() for _, line in visible_lines(document)
                        if (match := PLAN_STATUS.match(line))]
        if not status_lines:
            errors.append(f"[plan-state] Missing status: {location}")
            continue
        if len(status_lines) > 1:
            errors.append(f"[plan-state] Multiple status fields: {location}")
            continue
        status = status_lines[0]
        if status not in PLAN_STATUSES:
            errors.append(f"[plan-state] Invalid status '{status}': {location}")
        elif parts[2] == "completed" and status != "done":
            errors.append(f"[plan-state] Completed Plan must be done: {location} (found {status})")
        elif parts[2] == "active" and status == "done":
            errors.append(f"[plan-state] Active Plan cannot be done: {location}")
    return errors


def visible_lines(document: Path, *, strip_inline: bool = True):
    """Inspect inline navigation, excluding code examples and HTML comments."""
    fence = ""
    comment = False
    for number, line in enumerate(document.read_text(encoding="utf-8-sig").splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not line[marker.end():].strip():
                fence = ""
            continue
        if not comment and marker:
            fence = marker[1]
            continue
        if not comment and re.match(r"^(?: {4}|\t)", line):
            continue
        # Preserve label width, so [`name`](path) stays a link while inline
        # examples disappear. Mask before comments; `<!--` is literal code.
        masked = re.sub(r"(`+).*?\1", lambda match: "_" * len(match[0]), line)
        content = masked if strip_inline else line
        pieces = []
        position = 0
        while position < len(masked):
            if comment:
                end = masked.find("-->", position)
                if end < 0:
                    break
                position = end + 3
                comment = False
            else:
                start = masked.find("<!--", position)
                if start < 0:
                    pieces.append(content[position:])
                    break
                pieces.append(content[position:start])
                position = start + 4
                comment = True
        yield number, "".join(pieces)


def heading_ids(document: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for _, line in visible_lines(document, strip_inline=False):
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            text = re.sub(r"<[^>]+>", "", heading[1]).lower()
            slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
            count = counts.get(slug, 0)
            anchors.add(f"{slug}-{count}" if count else slug)
            counts[slug] = count + 1
    return anchors


def check(root: Path) -> tuple[int, int, list[str]]:
    errors = [f"Missing entrypoint: {name}" for name in REQUIRED if not (root / name).is_file()]
    errors.extend(f"Retired root directory exists: {name}/" for name in ("spec", "plans", "tests") if (root / name).exists())
    if (root / "docs/tests").exists():
        errors.append("Retired documentation directory exists: docs/tests/")
    # Git includes deliverable tracked/untracked files and skips ignored dependency trees.
    listing = subprocess.check_output(
        ["git", "-c", "core.quotepath=false", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
    ).decode("utf-8").split("\0")
    nested_agent_maps = sorted(name for name in listing if name.endswith("AGENTS.md") and name != "AGENTS.md")
    errors.extend(f"Nested Agent map is not allowed: {name} (use root AGENTS.md and module README)"
                  for name in nested_agent_maps)
    documents = {root / name for name in listing if name.endswith(".md") and (root / name).is_file()}
    errors.extend(check_catalogs(root, documents))
    errors.extend(check_plan_lifecycle(root, documents))
    anchor_cache: dict[Path, set[str]] = {}
    links = 0
    for document in sorted(documents):
        for number, line in visible_lines(document):
            for match in LINK.finditer(line):
                if is_escaped(line, match.start()):
                    continue
                target = match[1].strip("<>")
                if EXTERNAL.match(target) or target.startswith("//"):
                    continue
                links += 1
                path, _, fragment = target.partition("#")
                path, fragment = unquote(path), unquote(fragment)
                resolved = (document.parent / path).resolve() if path else document.resolve()
                location = f"{document.relative_to(root).as_posix()}:{number} -> {target}"
                if not resolved.is_relative_to(root):
                    errors.append(f"Link leaves repository: {location}")
                elif not resolved.exists():
                    errors.append(f"Missing link target: {location}")
                elif fragment and resolved.suffix.lower() == ".md":
                    if resolved not in anchor_cache:
                        anchor_cache[resolved] = heading_ids(resolved)
                    if fragment not in anchor_cache[resolved]:
                        errors.append(f"Missing heading anchor: {location}")
    return len(documents), links, errors


def main() -> int:
    documents, links, errors = check(REPO_ROOT)
    for error in errors:
        print(error)
    print(f"Checked {documents} Markdown files, {links} local links, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
