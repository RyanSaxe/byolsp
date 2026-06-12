"""AI agent integration files, shared by init and hook install/uninstall (SPEC 16)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from byolsp.fsio import write_text_atomic

AGENT_CHOICES = ("generic", "claude-code", "codex", "copilot")

MANAGED_MARKER = "<!-- Managed by BYOLSP. Manual edits may be overwritten. -->"

AGENT_INSTRUCTIONS_RELPATH = ".byolsp/agents/README.md"

GENERIC_AGENT_INSTRUCTIONS = f"""{MANAGED_MARKER}

# BYOLSP Agent Instructions

This repository uses BYOLSP to expose custom ast-grep diagnostics.

After writing or editing code, run:

```bash
byolsp agent-check --files <changed files>
```

If BYOLSP reports a diagnostic, fix it before continuing.

If a rule says an exception is allowed with a comment, only keep the violating
code when the code is genuinely necessary and add a concise comment explaining why.
"""


def install_agent_instructions(repo_root: Path, agents: Sequence[str]) -> list[str]:
    """Write instruction files for the requested agents; returns summary lines.

    Every install writes the generic README; per-agent adapters arrive with
    `byolsp hook install` (SPEC 15.10) and will branch on `agents` here.
    """
    path = repo_root / AGENT_INSTRUCTIONS_RELPATH
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if MANAGED_MARKER not in existing:
            return [
                f"{AGENT_INSTRUCTIONS_RELPATH} exists without the BYOLSP marker; "
                "left untouched."
            ]
        if existing == GENERIC_AGENT_INSTRUCTIONS:
            return []
    write_text_atomic(path, GENERIC_AGENT_INSTRUCTIONS)
    return [f"Wrote {AGENT_INSTRUCTIONS_RELPATH}"]
