"""`byolsp agent-check`: ast-grep diagnostics rendered for AI agents (SPEC 15.9)."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from byolsp.astgrep import ScanMatch, resolve_ast_grep, scan_files
from byolsp.config import load_global_config
from byolsp.paths import display_path, global_config_dir, resolve_repo_root

DIAGNOSTICS_EXIT_CODE = 2
DEFAULT_RENDER_LIMIT = 20


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
    if args.stdin_hook:
        hook_files = _hook_payload_files()
        if not hook_files:
            return 0
    else:
        hook_files = list(args.files)
    config_dir = global_config_dir()
    executable = resolve_ast_grep(load_global_config(config_dir).ast_grep_command)
    files = [file.resolve() for file in hook_files]
    result = scan_files(executable, repo_root, files, max_results=args.max_results)
    if result.warnings:
        print(result.warnings, file=sys.stderr)
    diagnostics = collect_diagnostics(result.matches, repo_root)
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
            line=match.line + 1,
            column=match.column + 1,
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
