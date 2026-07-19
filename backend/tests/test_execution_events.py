"""Tests for agent.shared.execution_events — EExecutionEvent enum."""

from agent.shared.events import EExecutionEvent


class TestEExecutionEvent:
    """EExecutionEvent StrEnum tests."""

    def test_eleven_members_exist(self) -> None:
        """All 11 event types defined in Architecture PRD §15 are present."""
        members: list[EExecutionEvent] = list(EExecutionEvent)
        assert len(members) == 11

    def test_all_values_are_strings(self) -> None:
        """Every member value is a str (StrEnum guarantees this)."""
        for member in EExecutionEvent:
            assert isinstance(member.value, str)

    def test_each_value_equals_lowercase_member_name(self) -> None:
        """Each member.value is the snake_case version of the member name."""
        for member in EExecutionEvent:
            expected: str = member.name.lower()
            assert member.value == expected, (
                f"{member.name}.value == {member.value!r}, expected {expected!r}"
            )

    def test_no_duplicate_values(self) -> None:
        """All 11 member values are unique."""
        values: list[str] = [member.value for member in EExecutionEvent]
        unique: set[str] = set(values)
        assert len(unique) == 11

    def test_members_are_str_instances(self) -> None:
        """StrEnum members are instances of str, enabling direct JSON serialization."""
        for member in EExecutionEvent:
            assert isinstance(member, str), f"{member.name} is not an instance of str"
