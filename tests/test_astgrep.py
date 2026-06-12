from pathlib import Path

import pytest

from byolsp.astgrep import (
    NOT_FOUND_MESSAGE,
    VERSION_PATTERN,
    ast_grep_version,
    resolve_ast_grep,
)
from byolsp.errors import AstGrepNotFound


def fake_executable(path: Path, script: str = 'echo "ast-grep 9.9.9"') -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{script}\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def bin_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """An initially empty PATH, with $BYOLSP_AST_GREP unset."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.delenv("BYOLSP_AST_GREP", raising=False)
    return bin_dir


def test_env_override_wins_over_path(
    bin_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_executable(bin_dir / "ast-grep")
    override = fake_executable(tmp_path / "elsewhere" / "my-sg")
    monkeypatch.setenv("BYOLSP_AST_GREP", str(override))

    assert resolve_ast_grep() == override


def test_path_resolution_prefers_ast_grep_over_sg(bin_dir: Path) -> None:
    sg = fake_executable(bin_dir / "sg")

    assert resolve_ast_grep() == sg

    ast_grep = fake_executable(bin_dir / "ast-grep")
    assert resolve_ast_grep() == ast_grep


def test_configured_command_is_used_exactly(bin_dir: Path, tmp_path: Path) -> None:
    fake_executable(bin_dir / "ast-grep")
    configured = fake_executable(tmp_path / "custom" / "ast-grep")

    assert resolve_ast_grep(command=str(configured)) == configured

    with pytest.raises(AstGrepNotFound):
        resolve_ast_grep(command=str(tmp_path / "custom" / "missing"))


def test_missing_executable_raises_the_exact_install_message(bin_dir: Path) -> None:
    with pytest.raises(AstGrepNotFound) as excinfo:
        resolve_ast_grep()

    assert str(excinfo.value) == NOT_FOUND_MESSAGE
    assert "brew install ast-grep" in NOT_FOUND_MESSAGE


def test_version_is_parsed_from_version_output(bin_dir: Path) -> None:
    executable = fake_executable(bin_dir / "ast-grep")

    assert ast_grep_version(executable) == "9.9.9"


def test_version_of_the_real_ast_grep_is_readable() -> None:
    version = ast_grep_version(resolve_ast_grep())

    assert VERSION_PATTERN.fullmatch(version)


def test_unreadable_version_fails_cleanly(bin_dir: Path) -> None:
    broken = fake_executable(bin_dir / "ast-grep", script="exit 1")

    with pytest.raises(AstGrepNotFound, match="could not read an ast-grep version"):
        ast_grep_version(broken)
