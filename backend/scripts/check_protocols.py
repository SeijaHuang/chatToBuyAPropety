"""Protocol compliance checker.

Verifies that every registered concrete class implements all methods declared
in its corresponding Protocol. Add a new (module_path, ProtocolName, ImplName)
entry to PAIRS whenever a new Protocol / implementation pair is introduced.

Exit 0  — all implementations are complete.
Exit 1  — one or more implementations are missing Protocol methods.

Run from the backend/ directory:
    uv run python scripts/check_protocols.py
"""

from __future__ import annotations

import sys
import typing
from importlib import import_module
from pathlib import Path
from types import ModuleType

# Ensure the backend package root is importable when the script is run directly
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Registry — update this table whenever a new Protocol/implementation is added
# ---------------------------------------------------------------------------
PAIRS: list[tuple[str, str, str]] = [
    ("domain.llm_client", "ILLMClient", "OpenRouterClient"),
    ("redis_store.session_store", "ISessionStore", "RedisSessionStore"),
    ("db.repositories.user", "IUserRepository", "SqlAlchemyUserRepository"),
    ("db.repositories.chat", "IChatRepository", "SqlAlchemyChatRepository"),
    ("services.chat_service", "IChatService", "ChatService"),
]


def _protocol_members(protocol_cls: type) -> frozenset[str]:
    """Return the set of member names declared on the Protocol."""
    # Python 3.13+ ships typing.get_protocol_members
    if hasattr(typing, "get_protocol_members"):
        return typing.get_protocol_members(protocol_cls)  # type: ignore[no-any-return]
    # Python 3.12 — _ProtocolMeta sets __protocol_attrs__ on every Protocol class
    if hasattr(protocol_cls, "__protocol_attrs__"):
        return frozenset(protocol_cls.__protocol_attrs__)
    # Fallback: scan the Protocol's own __dict__, skipping dunder and base-Protocol attrs
    base_attrs: frozenset[str] = frozenset(dir(typing.Protocol))
    return frozenset(
        name
        for name in vars(protocol_cls)
        if not name.startswith("_")
        and name not in base_attrs
        and callable(getattr(protocol_cls, name))
    )


def check_all() -> list[str]:
    """Check every (Protocol, implementation) pair and return error strings."""
    errors: list[str] = []
    for module_path, protocol_name, impl_name in PAIRS:
        module: ModuleType = import_module(module_path)
        protocol_cls: type = getattr(module, protocol_name)
        impl_cls: type = getattr(module, impl_name)

        required: frozenset[str] = _protocol_members(protocol_cls)
        missing: list[str] = sorted(
            member for member in required if not callable(getattr(impl_cls, member, None))
        )
        if missing:
            errors.append(
                f"  {impl_name} is missing {len(missing)} method(s) from "
                f"{protocol_name}: {', '.join(missing)}"
            )
    return errors


def main() -> None:
    errors: list[str] = check_all()
    if errors:
        print("Protocol compliance FAILED:", file=sys.stderr)
        for err in errors:
            print(err, file=sys.stderr)
        sys.exit(1)
    print(f"Protocol compliance OK — {len(PAIRS)} pair(s) checked.")


if __name__ == "__main__":
    main()
