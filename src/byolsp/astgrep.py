"""Isolated ast-grep subprocess handling (SPEC sections 5, 20).

Every ast-grep invocation lives here: executable resolution, version parsing,
and (for agent-check) JSON scans. No rule-indexing logic. All subprocess
calls pass argv lists, never shell strings (SPEC 19).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from byolsp.errors import AstGrepNotFound

NOT_FOUND_MESSAGE = (
    "ast-grep is required but was not found.\n"
    "\n"
    "Install it, then rerun this command:\n"
    "  brew install ast-grep\n"
    "\n"
    "Other install options:\n"
    "  https://ast-grep.github.io/guide/quick-start.html"
)

VERSION_PATTERN = re.compile(r"\d+(\.\d+)+")


def resolve_ast_grep(command: str = "auto") -> Path:
    """Locate the ast-grep executable (SPEC 5).

    `$BYOLSP_AST_GREP` wins when set. Otherwise a non-`auto` `command` (the
    global config's `ast_grep.command`: a name or absolute path) is used
    exactly, and `auto` tries `ast-grep` then `sg` on PATH.
    """
    override = os.environ.get("BYOLSP_AST_GREP")
    if override:
        candidates: tuple[str, ...] = (override,)
    elif command != "auto":
        candidates = (command,)
    else:
        candidates = ("ast-grep", "sg")
    for candidate in candidates:
        found = shutil.which(candidate)
        if found is not None:
            return Path(found)
    raise AstGrepNotFound(NOT_FOUND_MESSAGE)


def ast_grep_version(executable: Path) -> str:
    """The version `executable --version` reports, e.g. '0.43.0'."""
    try:
        result = subprocess.run(
            [str(executable), "--version"], capture_output=True, text=True
        )
    except OSError as error:
        raise AstGrepNotFound(
            f"could not run `{executable} --version`: {error}"
        ) from error
    match = VERSION_PATTERN.search(result.stdout) if result.returncode == 0 else None
    if match is None:
        raise AstGrepNotFound(
            f"could not read an ast-grep version from `{executable} --version`"
        )
    return match.group(0)
