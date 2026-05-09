"""Request/response DTOs for the requirements summary endpoint."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from models.conversation_state import CollectedData


class SummaryRequest(BaseModel):
    """Inbound payload for the summary endpoint."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
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
                }
            }
        },
    )

    collected_data: CollectedData


class SummaryResponse(BaseModel):
    """Outbound payload from the summary endpoint."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    summary_text: str
    structured: CollectedData
