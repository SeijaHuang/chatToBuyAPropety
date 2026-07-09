"""M1–M4 sub-models and the flat CollectedData/CompletionStatus accumulators."""

from typing import cast

from pydantic import BaseModel, Field, computed_field

from models.base import PropertyAIBaseModel
from models.shared.enums import (
    ECommuteMode,
    EIntendedUse,
    ELifestyleVibe,
    EModule,
    EPropertyType,
    ESubmodel,
    ETargetTenant,
)


class M1PropertyNeeds(PropertyAIBaseModel):
    """Collected fields for module 1: property type and physical requirements."""

    property_type: EPropertyType | None = None
    min_bedrooms: int | None = None
    max_bedrooms: int | None = None
    min_bathrooms: int | None = None
    min_carspaces: int | None = None
    min_land_size: int | None = None
    max_land_size: int | None = None
    wants_pool: bool | None = None
    wants_outdoor: bool | None = None
    wants_study: bool | None = None
    intended_use: EIntendedUse | None = None


class M2Lifestyle(PropertyAIBaseModel):
    """Collected fields for module 2: lifestyle and household requirements."""

    household_size: int | None = None
    has_children: bool | None = None
    needs_school_zone: bool | None = None
    has_pets: bool | None = None
    work_from_home: bool | None = None
    target_tenant: ETargetTenant | None = None


class M3SuburbPreference(PropertyAIBaseModel):
    """Collected fields for module 3: suburb and commute preferences."""

    commute_destination: str | None = None
    commute_max_mins: int | None = None
    commute_mode: ECommuteMode | None = None
    preferred_suburbs: list[str] | None = None
    excluded_suburbs: list[str] | None = None
    lifestyle_vibe: ELifestyleVibe | None = None


class M4Budget(PropertyAIBaseModel):
    """Collected fields for module 4: budget and financial readiness."""

    budget_min: int | None = None
    budget_max: int | None = None
    deposit_amount: int | None = None
    pre_tax_salary: int | None = None
    partner_salary: int | None = None
    is_joint: bool | None = None
    first_home_buyer: bool | None = None
    loan_term_years: int | None = None


TSubmodel = M1PropertyNeeds | M2Lifestyle | M3SuburbPreference | M4Budget


class CollectedData(PropertyAIBaseModel):
    """Flat accumulator for all extracted fields across all modules."""

    m1: M1PropertyNeeds = Field(default_factory=M1PropertyNeeds)
    m2: M2Lifestyle = Field(default_factory=M2Lifestyle)
    m3: M3SuburbPreference = Field(default_factory=M3SuburbPreference)
    m4: M4Budget = Field(default_factory=M4Budget)

    def __getitem__(self, key: ESubmodel) -> TSubmodel:
        """Return the sub-model for the given module key."""
        return cast(TSubmodel, getattr(self, key))


class CompletionStatus(BaseModel):
    """Tracks which modules have had all required fields collected.

    Intentionally does NOT inherit PropertyAIBaseModel — to_camel would
    lowercase M1→m1, breaking the API contract for completionStatus keys.
    """

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
