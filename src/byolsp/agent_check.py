"""`byolsp agent-check`: ast-grep diagnostics rendered for AI agents (SPEC 15.9)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from byolsp.astgrep import ScanMatch, resolve_ast_grep, scan_files
from byolsp.config import load_global_config
from byolsp.errors import ByolspError
from byolsp.linescope import Range, diff_ranges, overlaps
from byolsp.paths import display_path, global_config_dir, resolve_repo_root

DIAGNOSTICS_EXIT_CODE = 2
DEFAULT_RENDER_LIMIT = 20

Scope = Literal["edit", "diff", "file"]


@dataclass
class Diagnostic:
    """One diagnostic ready to render: 1-based position, repo-relative path."""

    file: str
    line: int
    column: int
    rule_id: str
    severity: str
    message: str
    code: str
    instruction: str
    """metadata.byolsp.agent_prompt, falling back to the rule message."""


def run_agent_check(args: argparse.Namespace) -> int:
    repo_root = resolve_repo_root(explicit=args.repo)
    scope = _resolve_scope(args)
    if args.stdin_hook:
        hook_files = _hook_payload_files()
        if not hook_files:
            return 0
    else:
        hook_files = list(args.files)
    files = [file.resolve() for file in hook_files]
    if scope != "file" and files:
        # An edit/diff-scoped target deleted since the edit has no lines left.
        files = [file for file in files if file.is_file()]
        if not files:
            return 0
    config_dir = global_config_dir()
    executable = resolve_ast_grep(load_global_config(config_dir).ast_grep_command)
    result = scan_files(executable, repo_root, files, max_results=args.max_results)
    if result.warnings:
        print(result.warnings, file=sys.stderr)
    matches = result.matches
    if scope != "file":
        matches = _matches_in_scope(matches, repo_root)
    diagnostics = collect_diagnostics(matches, repo_root)
    if args.format == "json":
        payload = {"issues": [asdict(diagnostic) for diagnostic in diagnostics]}
        print(json.dumps(payload, indent=2))
    else:
        limit = (
            args.max_results if args.max_results is not None else DEFAULT_RENDER_LIMIT
        )
        for line in render_diagnostics(diagnostics, limit):
            print(line)
    return DIAGNOSTICS_EXIT_CODE if diagnostics else 0


def _resolve_scope(args: argparse.Namespace) -> Scope:
    """The diagnostic scope (SPEC 28.3): explicit flag wins, else per mode.

    Hook mode defaults to file until the per-harness payload parsers land;
    they will carry edit contents and flip the default to edit.
    """
    scope: str | None = args.scope
    if scope == "edit":
        if not args.stdin_hook:
            raise ByolspError(
                "--scope edit needs a hook payload; use --stdin-hook, or --scope diff"
            )
        return "edit"
    if scope == "diff":
        return "diff"
    return "file"


def _matches_in_scope(matches: list[ScanMatch], repo_root: Path) -> list[ScanMatch]:
    """Matches overlapping their file's uncommitted-diff line ranges.

    Edit scope filters here too: until hook payloads carry edit contents it
    falls back to diff, whose own fallback (None ranges: untracked file,
    non-git repo, unborn HEAD) keeps every match — file scope (SPEC 28.3).
    """
    ranges_by_file: dict[str, list[Range] | None] = {}
    in_scope = []
    for match in matches:
        if match.file not in ranges_by_file:
            file = (repo_root / match.file).resolve()
            ranges_by_file[match.file] = diff_ranges(repo_root, file)
        ranges = ranges_by_file[match.file]
        if ranges is None or overlaps(match.line, match.end_line, ranges):
            in_scope.append(match)
    return in_scope


def _hook_payload_files() -> list[Path]:
    """The edited file in a Claude Code PostToolUse payload on stdin (SPEC 15.10).

    Payloads without one — including malformed ones, which must never block
    the agent loop — yield [] so the caller scans nothing.
    """
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    file_path = tool_input.get("file_path")
    if isinstance(file_path, str) and file_path:
        return [Path(file_path)]
    return []


def collect_diagnostics(matches: list[ScanMatch], repo_root: Path) -> list[Diagnostic]:
    """1-based diagnostics grouped by file, sorted by line then rule ID."""
    diagnostics = [
        Diagnostic(
            file=display_path(Path(match.file), repo_root),
            line=match.line,
            column=match.column,
            rule_id=match.rule_id,
            severity=match.severity,
            message=match.message,
            code=match.lines.rstrip("\n"),
            instruction=(match.agent_prompt or match.message).strip(),
        )
        for match in matches
    ]
    diagnostics.sort(key=lambda d: (d.file, d.line, d.rule_id, d.column))
    return diagnostics


def render_diagnostics(diagnostics: list[Diagnostic], limit: int) -> list[str]:
    """The SPEC 15.9 text output; empty when there are no diagnostics."""
    if not diagnostics:
        return []
    total = len(diagnostics)
    noun = "issue" if total == 1 else "issues"
    lines = [f"BYOLSP found {total} {noun} in AI-written code."]
    for diagnostic in diagnostics[:limit]:
        lines += [
            "",
            f"{diagnostic.file}:{diagnostic.line}:{diagnostic.column}",
            f"Rule: {diagnostic.rule_id}",
            f"Severity: {diagnostic.severity}",
            f"Message: {diagnostic.message}",
            f"Code: {diagnostic.code}",
            "",
            "Instruction:",
            diagnostic.instruction,
        ]
    if total > limit:
        lines += [
            "",
            f"...and {total - limit} more diagnostics."
            " Run ast-grep scan for the full list.",
        ]
    return lines
