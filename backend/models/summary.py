"""Request/response DTOs for the requirements summary endpoint."""

from pydantic import ConfigDict

from models.base import PropertyAIBaseModel
from models.conversation_state import CollectedData, EUserIntent
from models.user_needs import UserNeeds


class SummaryRequest(PropertyAIBaseModel):
    """Inbound payload for the summary endpoint."""

    # Extends parent config with an OpenAPI example; alias_generator and
    # populate_by_name are inherited from PropertyAIBaseModel.
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "collectedData": {
                    "m1": {
                        "propertyType": "house",
                        "minBedrooms": 3,
                        "intendedUse": "owner_occupier",
                    },
                    "m2": {"householdSize": 2, "hasChildren": False},
                    "m3": {"commuteDestination": "Melbourne CBD", "commuteMaxMins": 40},
                    "m4": {"budgetMax": 850000},
                },
                "sessionId": "abc123",
                "initialIntent": "open_ended_query",
            }
        }
    )

    collected_data: CollectedData
    session_id: str
    initial_intent: EUserIntent = EUserIntent.OPEN_ENDED_QUERY


class SummaryResponse(PropertyAIBaseModel):
    """Outbound payload from the summary endpoint."""

    summary_text: str
    structured: UserNeeds
