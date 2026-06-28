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


def _migrate() -> None:
    """Run pending Alembic migrations; retries while Postgres is starting up."""
    import time

    print("Checking for pending migrations…")
    for attempt in range(1, 16):
        result: subprocess.CompletedProcess[bytes] = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], check=False
        )
        if result.returncode == 0:
            return
        if attempt < 15:
            print(f"Postgres not ready yet, retrying in 1 s… ({attempt}/15)")
            time.sleep(1.0)
    print("ERROR: migrations failed — Postgres unavailable after 15 attempts.", file=sys.stderr)
    sys.exit(1)


def dev() -> None:
    """Start Docker services, run any pending migrations, then start uvicorn."""
    import pathlib

    repo_root: pathlib.Path = pathlib.Path(__file__).parent.parent

    subprocess.run(
        ["docker-compose", "up", "-d", "redis", "postgres"],
        cwd=repo_root,
        check=True,
    )

    _migrate()

    try:
        result: subprocess.CompletedProcess[bytes] = subprocess.run(
            [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
            check=False,
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        sys.exit(0)
