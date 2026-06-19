"""Entry points for [project.scripts] shortcuts."""

import subprocess
import sys


def test() -> None:
    """Run pytest."""
    from pytest import main

    sys.exit(main())


def lint() -> None:
    """Run ruff check."""
    result: subprocess.CompletedProcess[bytes] = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "."], check=False
    )
    sys.exit(result.returncode)


def format_code() -> None:
    """Run ruff format."""
    result: subprocess.CompletedProcess[bytes] = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "."], check=False
    )
    sys.exit(result.returncode)


def typecheck() -> None:
    """Run mypy --strict."""
    result: subprocess.CompletedProcess[bytes] = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "."], check=False
    )
    sys.exit(result.returncode)


def dev() -> None:
    """Start Docker services then the uvicorn dev server with hot-reload on port 8000."""
    import pathlib

    repo_root: pathlib.Path = pathlib.Path(__file__).parent.parent

    subprocess.run(
        ["docker-compose", "up", "-d", "redis", "postgres"],
        cwd=repo_root,
        check=True,
    )

    try:
        result: subprocess.CompletedProcess[bytes] = subprocess.run(
            [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
            check=False,
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(0)
