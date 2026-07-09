"""Intent classification — routes user messages to the appropriate downstream handler."""

import re
from collections.abc import Callable
from datetime import UTC, datetime

from models.shared.conversation_state import ConversationStateDTO
from models.shared.enums import EUserIntent
from models.shared.routing import EExecutionMode, ETriggerSource, RoutingPayload
from models.shared.user_needs import UserNeeds

_SUBURB_KEYWORDS: frozenset[str] = frozenset({"suburb", "area", "recommend", "推荐", "区域"})
_PROPERTY_KEYWORDS: frozenset[str] = frozenset({"property", "listing", "find", "找房", "房源"})
_ADDRESS_RE: re.Pattern[str] = re.compile(
    r"\d+\s+\w+\s+(street|st|road|rd|avenue|ave|drive|dr|lane|ln|court|ct|way|place|pl)\b",
    re.IGNORECASE,
)
_PROPERTY_ID_RE: re.Pattern[str] = re.compile(
    r"\bproperty[_\s-]?id\b|\bprop[_\s-]?id\b",
    re.IGNORECASE,
)

# Each entry is (predicate(lower, original) -> bool, intent). First match wins.
_INTENT_RULES: list[tuple[Callable[[str, str], bool], EUserIntent]] = [
    (lambda lower, _: any(kw in lower for kw in _SUBURB_KEYWORDS), EUserIntent.RECOMMEND_SUBURBS),
    (
        lambda _, original: bool(_ADDRESS_RE.search(original) or _PROPERTY_ID_RE.search(original)),
        EUserIntent.PROPERTY_DETAIL,
    ),
    (lambda lower, _: any(kw in lower for kw in _PROPERTY_KEYWORDS), EUserIntent.LIST_PROPERTIES),
]

# PRD §16.4 — execution mode and agent hints per intent
_ROUTING_CONFIG: dict[EUserIntent, tuple[EExecutionMode, list[str]]] = {
    EUserIntent.RECOMMEND_SUBURBS: (EExecutionMode.CODE_DRIVEN, ["suburb_agent", "price_agent"]),
    EUserIntent.LIST_PROPERTIES: (EExecutionMode.CODE_DRIVEN, ["suburb_agent", "price_agent"]),
    EUserIntent.PROPERTY_DETAIL: (
        EExecutionMode.CODE_DRIVEN,
        [
            "overlay_agent",
            "school_agent",
            "building_agent",
            "price_agent",
            "neighbourhood_agent",
            "transport_agent",
        ],
    ),
    EUserIntent.OPEN_ENDED_QUERY: (EExecutionMode.AGENTIC_LOOP, []),
}


def classify_intent(
    message: str, state: ConversationStateDTO, user_needs: UserNeeds
) -> RoutingPayload | None:
    """Classify the user's message intent and return routing context when appropriate.

    Returns None when all modules are incomplete and no trigger keyword is present.

    Trigger conditions (either is sufficient):
      - state.completion_status.all_complete is True
      - message matches any entry in _INTENT_RULES

    Intent priority (first match in _INTENT_RULES wins):
      1. recommend_suburbs — keyword: suburb, area, recommend, 推荐, 区域
      2. property_detail   — address pattern (number + street keyword) or property ID keyword
      3. list_properties   — keyword: property, listing, find, 找房, 房源
      4. open_ended_query  — fallback when all_complete is True and nothing matched

    Args:
        message: The raw user message text.
        state: Current conversation state.
        user_needs: Full UserNeeds snapshot built from the current state.

    Returns:
        RoutingPayload with classified intent and session context, or None.
    """
    lower: str = message.lower()
    matched: EUserIntent | None = next(
        (intent for pred, intent in _INTENT_RULES if pred(lower, message)), None
    )

    if matched is None and not state.completion_status.all_complete:
        return None

    intent: EUserIntent = matched if matched is not None else EUserIntent.OPEN_ENDED_QUERY
    trigger_source: ETriggerSource = (
        ETriggerSource.KEYWORD if matched is not None else ETriggerSource.AUTO_COMPLETE
    )
    execution_mode: EExecutionMode
    agents_hint: list[str]
    execution_mode, agents_hint = _ROUTING_CONFIG[intent]

    return RoutingPayload(
        intent=intent,
        session_id=state.session_id,
        user_needs=user_needs,
        execution_mode=execution_mode,
        agents_hint=agents_hint,
        triggered_at=datetime.now(tz=UTC),
        trigger_source=trigger_source,
    )
