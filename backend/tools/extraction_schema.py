"""LLM tool definition used to extract structured property requirements from user messages."""

EXTRACT_REQUIREMENTS_TOOL: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "extract_requirements",
        "description": (
            "Extract structured property requirements from the user's message. "
            "Populate only the fields the user has explicitly mentioned. "
            "Do not infer or guess values that were not clearly stated."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                # M1 — Property Needs
                "property_type": {
                    "type": "string",
                    "enum": ["house", "townhouse", "unit", "apartment", "villa", "any"],
                },
                "min_bedrooms": {"type": "integer"},
                "max_bedrooms": {"type": "integer"},
                "min_bathrooms": {"type": "integer"},
                "min_carspaces": {"type": "integer"},
                "min_land_size": {"type": "integer"},
                "max_land_size": {"type": "integer"},
                "wants_pool": {"type": "boolean"},
                "wants_outdoor": {"type": "boolean"},
                "wants_study": {"type": "boolean"},
                "intended_use": {
                    "type": "string",
                    "enum": ["owner_occupier", "investment", "both"],
                },
                # M2 — Lifestyle
                "household_size": {"type": "integer"},
                "has_children": {"type": "boolean"},
                "needs_school_zone": {"type": "boolean"},
                "has_pets": {"type": "boolean"},
                "work_from_home": {"type": "boolean"},
                "target_tenant": {
                    "type": "string",
                    "enum": ["family", "professional", "student", "any"],
                },
                # M3 — Suburb Preference
                "commute_destination": {"type": "string"},
                "commute_max_mins": {"type": "integer"},
                "commute_mode": {
                    "type": "string",
                    "enum": ["train", "car", "tram", "bus", "any"],
                },
                "preferred_suburbs": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "excluded_suburbs": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "lifestyle_vibe": {
                    "type": "string",
                    "enum": ["inner_city", "suburban", "leafy", "coastal", "any"],
                },
                # M4 — Budget
                "budget_min": {"type": "integer"},
                "budget_max": {"type": "integer"},
                "deposit_amount": {"type": "integer"},
                "pre_tax_salary": {"type": "integer"},
                "is_joint": {"type": "boolean"},
                "partner_salary": {"type": "integer"},
                "first_home_buyer": {"type": "boolean"},
                "loan_term_years": {"type": "integer"},
            },
            "required": [],
        },
    },
}
