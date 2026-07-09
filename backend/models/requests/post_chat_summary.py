"""Request DTO for POST /chat/summary."""

from pydantic import ConfigDict

from models.base import PropertyAIBaseModel
from models.shared.enums import EUserIntent
from models.shared.submodels import CollectedData


class ChatSummaryRequest(PropertyAIBaseModel):
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
