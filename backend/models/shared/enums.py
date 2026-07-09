"""Domain enums shared across conversation state, prompts, and routing."""

from enum import StrEnum


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


class EPropertyType(StrEnum):
    """Property type options collected in M1."""

    HOUSE = "house"
    TOWNHOUSE = "townhouse"
    UNIT = "unit"
    APARTMENT = "apartment"
    VILLA = "villa"
    ANY = "any"


class EIntendedUse(StrEnum):
    """Intended use of the property collected in M1."""

    OWNER_OCCUPIER = "owner_occupier"
    INVESTMENT = "investment"
    BOTH = "both"


class ETargetTenant(StrEnum):
    """Target tenant type for investment properties collected in M2."""

    FAMILY = "family"
    PROFESSIONAL = "professional"
    STUDENT = "student"
    ANY = "any"


class ECommuteMode(StrEnum):
    """Preferred commute transport mode collected in M3."""

    TRAIN = "train"
    CAR = "car"
    TRAM = "tram"
    BUS = "bus"
    ANY = "any"


class ELifestyleVibe(StrEnum):
    """Preferred lifestyle vibe collected in M3."""

    INNER_CITY = "inner_city"
    SUBURBAN = "suburban"
    LEAFY = "leafy"
    COASTAL = "coastal"
    ANY = "any"


class EUserIntent(StrEnum):
    """Classified routing intent for a conversation turn (PRD §16)."""

    RECOMMEND_SUBURBS = "recommend_suburbs"
    LIST_PROPERTIES = "list_properties"
    PROPERTY_DETAIL = "property_detail"
    OPEN_ENDED_QUERY = "open_ended_query"
    COMPARE_PROPERTIES = "compare_properties"
