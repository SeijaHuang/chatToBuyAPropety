"""Entry points for [project.scripts] shortcuts."""

import subprocess
import sys


def test() -> None:
    """Run pytest."""
    from pytest import main

    sys.exit(main())


def lint() -> None:
    """Run ruff check."""
    result = subprocess.run([sys.executable, "-m", "ruff", "check", "."], check=False)
    sys.exit(result.returncode)


def format_code() -> None:
    """Run ruff format."""
    result = subprocess.run([sys.executable, "-m", "ruff", "format", "."], check=False)
    sys.exit(result.returncode)


def typecheck() -> None:
    """Run mypy --strict."""
    result = subprocess.run([sys.executable, "-m", "mypy", "--strict", "."], check=False)
    sys.exit(result.returncode)


def dev() -> None:
    """Start the uvicorn dev server with hot-reload on port 8000."""
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
        check=False,
    )
    sys.exit(result.returncode)
