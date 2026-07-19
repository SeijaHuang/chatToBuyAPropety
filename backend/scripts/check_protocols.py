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
PAIRS: list[tuple[str, str, str] | tuple[str, str, str, str]] = [
    # (protocol_module, ProtocolName, ImplName) — Protocol & impl in same module
    ("domain.llm_client", "ILLMClient", "OpenRouterClient"),
    ("redis_store.session_store", "ISessionStore", "RedisSessionStore"),
    ("db.repositories.user", "IUserRepository", "SqlAlchemyUserRepository"),
    ("db.repositories.chat", "IChatRepository", "SqlAlchemyChatRepository"),
    ("services.chat_service", "IChatService", "ChatService"),
    ("agent.tool_registry.registry", "IToolRegistry", "ToolRegistry"),
    ("agent.orchestration.context_resolver", "IContextResolver", "ContextResolver"),
    ("agent.orchestration.orchestrator", "IOrchestrator", "Orchestrator"),
    # (protocol_module, ProtocolName, ImplName, impl_module) — cross-file pairs
    (
        "agent.orchestration.executors.base",
        "IExecutor",
        "CodeDrivenExecutor",
        "agent.orchestration.executors.code_driven_executor",
    ),
    (
        "agent.orchestration.executors.base",
        "IExecutor",
        "LLMDrivenExecutor",
        "agent.orchestration.executors.llm_driven_executor",
    ),
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


def _resolve_entry(
    entry: tuple[str, str, str] | tuple[str, str, str, str],
) -> tuple[type, str, type, str]:
    """Resolve a PAIRS entry to (protocol_class, protocol_name, impl_class, impl_label).

    For 3-tuples the implementation lives in the same module as the Protocol.
    For 4-tuples the fourth element is the implementation's module path.
    """
    protocol_module_path: str = entry[0]
    protocol_name: str = entry[1]
    impl_name: str = entry[2]
    impl_module_path: str = entry[3] if len(entry) == 4 else protocol_module_path

    protocol_module: ModuleType = import_module(protocol_module_path)
    impl_module: ModuleType = import_module(impl_module_path)
    protocol_cls: type = getattr(protocol_module, protocol_name)
    impl_cls: type = getattr(impl_module, impl_name)

    # Label includes module path when different from protocol
    impl_label: str = (
        impl_name if impl_module_path == protocol_module_path else f"{impl_module_path}.{impl_name}"
    )
    return protocol_cls, protocol_name, impl_cls, impl_label


def check_all() -> list[str]:
    """Check every (Protocol, implementation) pair and return error strings."""
    errors: list[str] = []
    for entry in PAIRS:
        protocol_cls, protocol_name, impl_cls, impl_label = _resolve_entry(entry)

        required: frozenset[str] = _protocol_members(protocol_cls)
        missing: list[str] = sorted(
            member for member in required if not callable(getattr(impl_cls, member, None))
        )
        if missing:
            errors.append(
                f"  {impl_label} is missing {len(missing)} method(s) from "
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
