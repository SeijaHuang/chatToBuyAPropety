"""Intent classification — routes user messages to the appropriate downstream handler."""

import re
from collections.abc import Callable

from models.schemas import ConversationStateDTO, RoutingPayload

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

# Each entry is (predicate(lower, original) -> bool, intent_string).
# Checked in order; first match wins. "open_ended_query" is the fallback.
_INTENT_RULES: list[tuple[Callable[[str, str], bool], str]] = [
    (lambda lower, _: any(kw in lower for kw in _SUBURB_KEYWORDS), "recommend_suburbs"),
    (
        lambda _, original: bool(_ADDRESS_RE.search(original) or _PROPERTY_ID_RE.search(original)),
        "property_detail",
    ),
    (lambda lower, _: any(kw in lower for kw in _PROPERTY_KEYWORDS), "list_properties"),
]


def classify_intent(message: str, state: ConversationStateDTO) -> RoutingPayload | None:
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

    Returns:
        RoutingPayload with classified intent and session context, or None.
    """
    lower = message.lower()
    matched = next((intent for pred, intent in _INTENT_RULES if pred(lower, message)), None)

    if matched is None and not state.completion_status.all_complete:
        return None

    return RoutingPayload(
        intent=matched if matched is not None else "open_ended_query",
        collected_data=state.collected_data,
        session_id=state.session_id,
    )
