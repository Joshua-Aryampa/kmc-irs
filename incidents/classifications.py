"""Classification options grouped by Involves category."""

INVOLVE_GROUPS = {
    "person": {
        "label": "Person(s)",
        "field": "involves_person",
        "classifications": [
            ("classification_injury", "Injury"),
            ("classification_accident", "Accident"),
            ("classification_assault", "Assault"),
            ("classification_loss", "Loss"),
        ],
        "other_bool": "other_person",
        "other_text": "other_person_text",
    },
    "premises": {
        "label": "Premises",
        "field": "involves_premises",
        "classifications": [
            ("classification_damage", "Damage"),
            ("classification_fire", "Fire"),
            ("classification_power_outage", "Power Outage"),
            ("classification_water_shortage", "Water Shortage"),
        ],
        "other_bool": "other_premises",
        "other_text": "other_premises_text",
    },
    "property": {
        "label": "Property",
        "field": "involves_property",
        "classifications": [
            ("classification_damage", "Damage"),
            ("classification_accident", "Accident"),
            ("classification_theft_vandalism", "Theft/Vandalism"),
            ("classification_fire", "Fire"),
        ],
        "other_bool": "other_property",
        "other_text": "other_property_text",
    },
    "product": {
        "label": "Product(s)",
        "field": "involves_product",
        "classifications": [
            ("classification_breakdown", "Breakdown"),
            ("classification_fault", "Fault"),
            ("classification_accident", "Accident"),
            ("classification_theft_vandalism", "Theft/Vandalism"),
        ],
        "other_bool": "other_product",
        "other_text": "other_product_text",
    },
}

ALL_CLASSIFICATION_FIELDS = sorted(
    {name for group in INVOLVE_GROUPS.values() for name, _ in group["classifications"]}
    | {group["other_bool"] for group in INVOLVE_GROUPS.values()}
)
