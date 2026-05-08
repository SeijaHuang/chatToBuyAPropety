"""Single source of truth for all Pydantic request/response models and domain DTOs."""

from enum import StrEnum
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel


class EModule(StrEnum):
    """Active conversation module driving field collection."""

    M1_PROPERTY_NEEDS = "M1_PROPERTY_NEEDS"
    M2_LIFESTYLE = "M2_LIFESTYLE"
    M3_SUBURB_PREFERENCE = "M3_SUBURB_PREFERENCE"
    M4_BUDGET = "M4_BUDGET"
    COMPLETE = "COMPLETE"


class EStatus(StrEnum):
    """High-level status of a conversation session."""

    IN_PROGRESS = "IN_PROGRESS"
    REQUIREMENTS_COMPLETE = "REQUIREMENTS_COMPLETE"


class ESubmodel(StrEnum):
    """Attribute names for each module's sub-model on CollectedData."""

    M1 = "m1"
    M2 = "m2"
    M3 = "m3"
    M4 = "m4"


class ESubmodelLabel(StrEnum):
    """Human-readable display labels for each sub-model."""

    M1 = "Property needs"
    M2 = "Lifestyle"
    M3 = "Suburb preference"
    M4 = "Budget"


class M1PropertyNeeds(BaseModel):
    """Collected fields for module 1: property type and physical requirements."""

    property_type: Literal["house", "townhouse", "unit", "apartment", "villa", "any"] | None = None
    min_bedrooms: int | None = None
    max_bedrooms: int | None = None
    min_bathrooms: int | None = None
    min_carspaces: int | None = None
    min_land_size: int | None = None
    max_land_size: int | None = None
    wants_pool: bool | None = None
    wants_outdoor: bool | None = None
    wants_study: bool | None = None
    intended_use: Literal["owner_occupier", "investment", "both"] | None = None


class M2Lifestyle(BaseModel):
    """Collected fields for module 2: lifestyle and household requirements."""

    household_size: int | None = None
    has_children: bool | None = None
    needs_school_zone: bool | None = None
    has_pets: bool | None = None
    work_from_home: bool | None = None
    target_tenant: Literal["family", "professional", "student", "any"] | None = None


class M3SuburbPreference(BaseModel):
    """Collected fields for module 3: suburb and commute preferences."""

    commute_destination: str | None = None
    commute_max_mins: int | None = None
    commute_mode: Literal["train", "car", "tram", "bus", "any"] | None = None
    preferred_suburbs: list[str] | None = None
    excluded_suburbs: list[str] | None = None
    lifestyle_vibe: Literal["inner_city", "suburban", "leafy", "coastal", "any"] | None = None


class M4Budget(BaseModel):
    """Collected fields for module 4: budget and financial readiness."""

    budget_min: int | None = None
    budget_max: int | None = None
    deposit_amount: int | None = None
    pre_tax_salary: int | None = None
    partner_salary: int | None = None
    is_joint: bool | None = None
    first_home_buyer: bool | None = None


TSubmodel = M1PropertyNeeds | M2Lifestyle | M3SuburbPreference | M4Budget


class CollectedData(BaseModel):
    """Flat accumulator for all extracted fields across all modules."""

    m1: M1PropertyNeeds = Field(default_factory=M1PropertyNeeds)
    m2: M2Lifestyle = Field(default_factory=M2Lifestyle)
    m3: M3SuburbPreference = Field(default_factory=M3SuburbPreference)
    m4: M4Budget = Field(default_factory=M4Budget)

    def __getitem__(self, key: ESubmodel) -> TSubmodel:
        """Return the sub-model for the given module key."""
        return cast(TSubmodel, getattr(self, key))


class CompletionStatus(BaseModel):
    """Tracks which modules have had all required fields collected."""

    M1: bool = False
    M2: bool = False
    M3: bool = False
    M4: bool = False

    def __getitem__(self, key: ESubmodel) -> bool:
        """Return the completion flag for the given module key.

        Uses key.name ("M1", "M2", …) to map ESubmodel values ("m1", "m2", …)
        to the uppercase field names on this model.
        """
        return cast(bool, getattr(self, key.name))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_complete(self) -> bool:
        """True when every module has been completed."""
        return self.M1 and self.M2 and self.M3 and self.M4

    @computed_field  # type: ignore[prop-decorator]
    @property
    def current_module(self) -> EModule:
        """Return the first incomplete module in M1 → M2 → M3 → M4 order."""
        if not self.M1:
            return EModule.M1_PROPERTY_NEEDS
        if not self.M2:
            return EModule.M2_LIFESTYLE
        if not self.M3:
            return EModule.M3_SUBURB_PREFERENCE
        if not self.M4:
            return EModule.M4_BUDGET
        return EModule.COMPLETE


class ConversationStateDTO(BaseModel):
    """Full session state for a single user conversation.

    Serialises to camelCase JSON for API transport while retaining
    snake_case access internally via populate_by_name.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    session_id: str
    status: EStatus = EStatus.IN_PROGRESS
    current_module: EModule = EModule.M1_PROPERTY_NEEDS
    completion_status: CompletionStatus = Field(default_factory=CompletionStatus)
    collected_data: CollectedData = Field(default_factory=CollectedData)
    conversation_history: list[dict[str, object]] = Field(default_factory=list)
    final_needs: CollectedData | None = None


class SummaryRequest(BaseModel):
    """Inbound payload for the summary endpoint."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
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


class RoutingPayload(BaseModel):
    """Bundled routing context passed between conversation layers."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    intent: str
    collected_data: CollectedData
    session_id: str


class ChatRequest(BaseModel):
    """Inbound payload for a single conversation turn.

    Attributes:
        message: The user's message text. Must be non-empty.
        state: The full current conversation state held by the client.
    """

    message: str = Field(min_length=1)
    state: ConversationStateDTO


class ChatResponse(BaseModel):
    """Outbound payload returned after processing a conversation turn.

    Attributes:
        reply: The assistant's reply text.
        extracted: Full LLM tool call fields including control keys.
        updated_state: Conversation state after merging extracted fields and advancing modules.
        routing: Populated when the state is complete or a routing keyword is detected.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    reply: str
    extracted: dict[str, object]
    updated_state: ConversationStateDTO
    routing: RoutingPayload | None = None
